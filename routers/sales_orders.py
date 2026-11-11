from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from decimal import Decimal

from database import get_db, CustomerDB, SalesOrderDB, InvoiceDB
from schemas import (
    InvoiceStatus,
    SalesOrderCreate,
    SalesOrderResponse,
    SalesOrderUpdate,
    order_Status,
)
from services.credit_management import CustomerNotFoundError, calculate_credit_exposure
from security import require_api_key


router = APIRouter(
    prefix="/orders",
    tags=["Sales Orders"],
    dependencies=[Depends(require_api_key)],
)

_CREDIT_EXPOSURE_ORDER_STATUSES = (
    order_Status.open,
    order_Status.awaiting_approval,
    order_Status.processed,
)
_VALID_INVOICE_STATUSES = (
    InvoiceStatus.open.value,
    InvoiceStatus.partially_paid.value,
    InvoiceStatus.overdue.value,
    InvoiceStatus.paid.value,
)

@router.post("/",response_model=SalesOrderResponse)
def create_sales_orders(order:SalesOrderCreate,db:Session=Depends(get_db)):
    try:
        exposure = calculate_credit_exposure(order.customer_id, db)
    except CustomerNotFoundError as error:
        raise HTTPException(status_code=404, detail="Customer not found") from error

    projected_exposure = exposure.total_credit_exposure + order.order_amount
    order_status = (
        order_Status.open
        if projected_exposure <= exposure.credit_limit
        else order_Status.blocked
    )

    db_order=SalesOrderDB(
        customer_id=order.customer_id,
        order_date=order.order_date,
        order_amount=order.order_amount,
        order_status=order_status.value,
    )

    db.add(db_order)
    db.commit()
    db.refresh(db_order)

    return db_order

@router.get("/",response_model=list[SalesOrderResponse])
def get_sales_orders(db:Session=Depends(get_db)):
    # Here you would typically retrieve sales orders from a database
    return db.query(SalesOrderDB).all()

@router.get("/{order_id}",response_model=SalesOrderResponse)
def get_sales_order(order_id:int,db:Session=Depends(get_db)):
    # Here you would typically retrieve sales orders from a database
    db_order=db.query(SalesOrderDB).filter(SalesOrderDB.order_id==order_id).first()

    if not db_order:
        raise HTTPException(
            status_code=404,
            detail="Sales order not found")

    return db_order


@router.delete("/{order_id}")
def delete_sales_order(order_id:int,db:Session=Depends(get_db)):

    # Here you would typically delete sales orders from a database

    #Find the sales order in the database
    db_order=db.query(SalesOrderDB).filter(SalesOrderDB.order_id==order_id).first()
    
    #Check if the sales order exists
    if not db_order:
        raise HTTPException(status_code=404,detail="Sales order not found")

    if db.query(InvoiceDB.invoice_id).filter(InvoiceDB.sales_order_id == order_id).first():
        raise HTTPException(status_code=409, detail="Sales order has an invoice and cannot be deleted")

    #Delete the sales order from the database
    db.delete(db_order)

    #Save changes to the database
    db.commit()

    #Return the result after deletion
    return {"message": f"Sales order with id {order_id} has been deleted successfully."}

@router.put("/{order_id}",response_model=SalesOrderResponse)
def update_sales_orders(order_id:int,order:SalesOrderUpdate,db:Session=Depends(get_db)):

    # Here you would typically update sales orders in a database
    db_order=db.query(SalesOrderDB).filter(SalesOrderDB.order_id==order_id).first()

    #Check if the sales order exists
    if not db_order:
        raise HTTPException(status_code=404,detail="Sales order not found")

    customer = db.query(CustomerDB).filter(CustomerDB.id == order.customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    if (
        db_order.order_status == order_Status.blocked
        and order.order_status in _CREDIT_EXPOSURE_ORDER_STATUSES
    ):
        raise HTTPException(
            status_code=409,
            detail="Blocked sales orders cannot be promoted through the generic update endpoint",
        )

    existing_invoices = db.query(InvoiceDB.invoice_amount).filter(InvoiceDB.sales_order_id == order_id).all()
    if existing_invoices and db_order.order_status == "CANCELLED" and order.order_status != "CANCELLED":
        raise HTTPException(status_code=409, detail="Cannot change an invoiced order's status back from cancelled")
    if existing_invoices and order.order_status == "CANCELLED":
        raise HTTPException(status_code=409, detail="An invoiced sales order cannot be cancelled")
    total_invoiced = sum((amount for (amount,) in existing_invoices), Decimal("0"))
    if total_invoiced > order.order_amount:
        raise HTTPException(status_code=409, detail="Order amount cannot be less than its invoiced total")

    valid_invoice_amounts = db.query(InvoiceDB.invoice_amount).filter(
        InvoiceDB.sales_order_id == order_id,
        InvoiceDB.invoice_status.in_(_VALID_INVOICE_STATUSES),
    ).all()
    valid_invoiced_total = sum(
        (amount for (amount,) in valid_invoice_amounts), Decimal("0")
    )

    if order.order_status == order_Status.closed:
        if valid_invoiced_total < order.order_amount:
            raise HTTPException(
                status_code=409,
                detail="Cannot close a sales order until its full amount is invoiced",
            )

    if existing_invoices:
        if db_order.customer_id != order.customer_id:
            raise HTTPException(status_code=409, detail="Cannot change the customer of an invoiced sales order")

    was_exposure_eligible = db_order.order_status in _CREDIT_EXPOSURE_ORDER_STATUSES
    will_be_exposure_eligible = order.order_status in _CREDIT_EXPOSURE_ORDER_STATUSES
    exposure_affecting_change = (
        db_order.customer_id != order.customer_id
        or db_order.order_amount != order.order_amount
        or was_exposure_eligible != will_be_exposure_eligible
    )
    if exposure_affecting_change:
        exposure = calculate_credit_exposure(order.customer_id, db)
        projected_exposure = exposure.total_credit_exposure

        # The service already includes this order when it belongs to the same
        # customer and currently contributes to credit exposure. Remove that
        # contribution before adding the proposed order state.
        if db_order.customer_id == order.customer_id and was_exposure_eligible:
            projected_exposure -= db_order.order_amount - valid_invoiced_total
        if will_be_exposure_eligible:
            projected_exposure += order.order_amount - valid_invoiced_total

        if projected_exposure > exposure.credit_limit:
            raise HTTPException(
                status_code=409,
                detail="Sales order update would exceed the customer's credit limit",
            )

    #Update the existing database object
    db_order.customer_id=order.customer_id
    db_order.order_amount=order.order_amount
    db_order.order_date=order.order_date
    db_order.order_status=order.order_status

    #Save changes to the database
    db.commit()

    #Return the updated sales order
    return db_order
