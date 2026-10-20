from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db, CustomerDB, SalesOrderDB, InvoiceDB
from schemas import InvoiceCreate, InvoiceResponse

router = APIRouter(
    prefix="/invoices",
    tags=["Invoices"]
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

    #Delete the invoice from the database
    db.delete(db_invoice)

    #Save changes to the database
    db.commit()

    #Return the result after deletion
    return {"message": f"Invoice with id {invoice_id} has been deleted successfully."}

@router.put("/{invoice_id}",response_model=InvoiceResponse)
def update_invoice(invoice_id:int,invoice:InvoiceCreate,db:Session=Depends(get_db)):

    db_invoice=db.query(InvoiceDB).filter(InvoiceDB.invoice_id==invoice_id).first()

    if not db_invoice:
        raise HTTPException(status_code=404,detail="Invoice not found")

    db_invoice.invoice_date=invoice.invoice_date
    db_invoice.due_date=invoice.due_date
    db_invoice.invoice_amount=invoice.invoice_amount
    db_invoice.invoice_status=invoice.invoice_status


    db.commit()

    return db_invoice