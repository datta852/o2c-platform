from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from decimal import Decimal

from database import get_db, CustomerDB, SalesOrderDB, InvoiceDB
from schemas import SalesOrderCreate, SalesOrderResponse
from security import require_api_key


router = APIRouter(
    prefix="/orders",
    tags=["Sales Orders"],
    dependencies=[Depends(require_api_key)],
)

@router.post("/",response_model=SalesOrderResponse)
def create_sales_orders(order:SalesOrderCreate,db:Session=Depends(get_db)):
    
    customer=db.query(CustomerDB).filter(CustomerDB.id==order.customer_id).first()

    if not customer:
                raise HTTPException(
                    status_code=404,
                    detail="Customer not found")

    db_order=SalesOrderDB(
        customer_id=order.customer_id,
        order_date=order.order_date,
        order_amount=order.order_amount,
        order_status=order.order_status
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
def update_sales_orders(order_id:int,order:SalesOrderCreate,db:Session=Depends(get_db)):

    # Here you would typically update sales orders in a database
    db_order=db.query(SalesOrderDB).filter(SalesOrderDB.order_id==order_id).first()

    #Check if the sales order exists
    if not db_order:
        raise HTTPException(status_code=404,detail="Sales order not found")

    customer = db.query(CustomerDB).filter(CustomerDB.id == order.customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    existing_invoices = db.query(InvoiceDB.invoice_amount).filter(InvoiceDB.sales_order_id == order_id).all()
    if existing_invoices and db_order.order_status == "CANCELLED" and order.order_status != "CANCELLED":
        raise HTTPException(status_code=409, detail="Cannot change an invoiced order's status back from cancelled")
    if existing_invoices and order.order_status == "CANCELLED":
        raise HTTPException(status_code=409, detail="An invoiced sales order cannot be cancelled")
    total_invoiced = sum((amount for (amount,) in existing_invoices), Decimal("0"))
    if total_invoiced > order.order_amount:
        raise HTTPException(status_code=409, detail="Order amount cannot be less than its invoiced total")

    if existing_invoices:
        if db_order.customer_id != order.customer_id:
            raise HTTPException(status_code=409, detail="Cannot change the customer of an invoiced sales order")

    #Update the existing database object
    db_order.customer_id=order.customer_id
    db_order.order_amount=order.order_amount
    db_order.order_date=order.order_date
    db_order.order_status=order.order_status

    #Save changes to the database
    db.commit()

    #Return the updated sales order
    return db_order
