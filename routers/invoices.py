from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db, CustomerDB, SalesOrderDB, InvoiceDB, PaymentAllocationDB
from schemas import InvoiceCreate, InvoiceResponse
from security import require_api_key

router = APIRouter(
    prefix="/invoices",
    tags=["Invoices"],
    dependencies=[Depends(require_api_key)],
)

@router.post("/",response_model=InvoiceResponse)
def create_invoice(invoice:InvoiceCreate,db:Session=Depends(get_db)):

    customer=db.query(CustomerDB).filter(CustomerDB.id==invoice.customer_id).first()

    order=db.query(SalesOrderDB).filter(SalesOrderDB.order_id==invoice.sales_order_id).first()

    if not customer:
        raise HTTPException(
            status_code=404,
            detail="Customer not found")

    if not order:
            raise HTTPException(
                status_code=404, 
                detail="Sales order not found")

    if order.customer_id != invoice.customer_id:
        raise HTTPException(status_code=400, detail="Invoice and sales order must belong to the same customer")
    if invoice.due_date < invoice.invoice_date:
        raise HTTPException(status_code=400, detail="Invoice due date cannot precede the invoice date")
    if invoice.invoice_status != "OPEN":
        raise HTTPException(status_code=400, detail="New invoices must start with OPEN status")
    if order.order_status not in ("PROCESSED", "CLOSED"):
        raise HTTPException(status_code=409, detail="Only processed or closed sales orders can be invoiced")
    invoiced_total = db.query(InvoiceDB.invoice_amount).filter(
        InvoiceDB.sales_order_id == invoice.sales_order_id
    ).all()
    total_already_invoiced = sum((amount for (amount,) in invoiced_total), Decimal("0"))
    if total_already_invoiced + invoice.invoice_amount > order.order_amount:
        raise HTTPException(status_code=409, detail="Invoice amount exceeds the uninvoiced sales order balance")

    db_invoice=InvoiceDB(
        customer_id=invoice.customer_id,
        invoice_number=invoice.invoice_number,
        sales_order_id=invoice.sales_order_id,
        invoice_date=invoice.invoice_date,
        due_date=invoice.due_date,
        invoice_amount=invoice.invoice_amount,
        invoice_status=invoice.invoice_status
    )
    
    db.add(db_invoice)
    db.commit()
    db.refresh(db_invoice)

    return db_invoice

@router.get("/",response_model=list[InvoiceResponse])
def get_invoices(db:Session=Depends(get_db)):
    # Here you would typically retrieve invoices from a database
    return db.query(InvoiceDB).all()


@router.get("/{invoice_id}",response_model=InvoiceResponse)
def get_invoice(invoice_id:int,db:Session=Depends(get_db)):

    db_invoice=db.query(InvoiceDB).filter(InvoiceDB.invoice_id==invoice_id).first()

    if not db_invoice:
        raise HTTPException(
            status_code=404,
            detail="Invoice not found")

    return db_invoice

@router.delete("/{invoice_id}")
def delete_invoice(invoice_id:int,db:Session=Depends(get_db)):

    # Here you would typically delete invoices from a database
    
    #Find the invoice in the database
    db_invoice=db.query(InvoiceDB).filter(InvoiceDB.invoice_id==invoice_id).first()

    #Check if the invoice exists
    if not db_invoice:
        raise HTTPException(
            status_code=404,
            detail="Invoice not found")

    raise HTTPException(
        status_code=409,
        detail="Invoices are financial records and cannot be deleted; mark an eligible invoice CANCELLED instead",
    )

@router.put("/{invoice_id}",response_model=InvoiceResponse)
def update_invoice(invoice_id:int,invoice:InvoiceCreate,db:Session=Depends(get_db)):

    db_invoice=db.query(InvoiceDB).filter(InvoiceDB.invoice_id==invoice_id).first()

    if not db_invoice:
        raise HTTPException(status_code=404,detail="Invoice not found")

    customer = db.query(CustomerDB).filter(CustomerDB.id == invoice.customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    order = db.query(SalesOrderDB).filter(SalesOrderDB.order_id == invoice.sales_order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Sales order not found")
    if order.customer_id != invoice.customer_id:
        raise HTTPException(status_code=400, detail="Invoice and sales order must belong to the same customer")
    if invoice.due_date < invoice.invoice_date:
        raise HTTPException(status_code=400, detail="Invoice due date cannot precede the invoice date")

    allocations = db.query(PaymentAllocationDB).filter(PaymentAllocationDB.invoice_id == invoice_id).all()
    allocated_total = sum((item.allocated_amount for item in allocations), Decimal("0"))
    if allocated_total > invoice.invoice_amount:
        raise HTTPException(status_code=409, detail="Invoice amount cannot be less than its allocated payments")
    if allocations and (invoice.customer_id != db_invoice.customer_id or invoice.sales_order_id != db_invoice.sales_order_id):
        raise HTTPException(status_code=409, detail="Cannot change invoice ownership while payment allocations exist")
    if invoice.invoice_status == "CANCELLED" and allocated_total > 0:
        raise HTTPException(status_code=409, detail="Cannot cancel an invoice with payment allocations")
    if invoice.invoice_status == "PAID" and allocated_total != invoice.invoice_amount:
        raise HTTPException(status_code=409, detail="Invoice cannot be marked paid unless fully allocated")
    if invoice.invoice_status == "PARTIALLY_PAID" and not (0 < allocated_total < invoice.invoice_amount):
        raise HTTPException(status_code=409, detail="Partially paid status must match the allocated balance")
    if invoice.invoice_status == "OPEN" and allocated_total != 0:
        raise HTTPException(status_code=409, detail="Invoice with allocations cannot be marked open")
    other_invoices = db.query(InvoiceDB.invoice_amount).filter(
        InvoiceDB.sales_order_id == invoice.sales_order_id,
        InvoiceDB.invoice_id != invoice_id,
    ).all()
    other_invoiced_total = sum((amount for (amount,) in other_invoices), Decimal("0"))
    if other_invoiced_total + invoice.invoice_amount > order.order_amount:
        raise HTTPException(status_code=409, detail="Invoice amount exceeds the uninvoiced sales order balance")

    db_invoice.invoice_date=invoice.invoice_date
    db_invoice.due_date=invoice.due_date
    db_invoice.invoice_amount=invoice.invoice_amount
    db_invoice.invoice_status=invoice.invoice_status
    db_invoice.invoice_number=invoice.invoice_number
    db_invoice.customer_id=invoice.customer_id
    db_invoice.sales_order_id=invoice.sales_order_id


    db.commit()

    return db_invoice
