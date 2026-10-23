from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import (
    get_db,
    PaymentDB,
    InvoiceDB,
    PaymentAllocationDB,
)
from schemas import (
    PaymentAllocationCreate,
    PaymentAllocationResponse,
    PaymentAllocationUpdate,
    InvoiceStatus
)

router = APIRouter(
    prefix="/payment_allocations",
    tags=["Payment Allocations"]
)


@router.post("/",response_model=PaymentAllocationResponse)
def create_payment_allocation(allocation:PaymentAllocationCreate,db:Session=Depends(get_db)):

    payment=db.query(PaymentDB).filter(PaymentDB.payment_id==allocation.payment_id).first()

    invoice=db.query(InvoiceDB).filter(InvoiceDB.invoice_id==allocation.invoice_id).first()

    if not payment:
        raise HTTPException(
            status_code=404,
            detail="Payment not found")

    if not invoice:
        raise HTTPException(
            status_code=404,
            detail="Invoice not found")
    
    if invoice.invoice_status in [InvoiceStatus.cancelled,InvoiceStatus.paid]:
        raise HTTPException(
            status_code=400,
            detail="Cannot allocate payment to a cancelled or paid invoice"
    )

    existing_allocations=db.query(PaymentAllocationDB).filter(PaymentAllocationDB.payment_id==allocation.payment_id).all()

    total_allocated_amount=sum(amount.allocated_amount for amount in existing_allocations)

    remaining_amount=payment.payment_amount-total_allocated_amount

    if allocation.allocated_amount > remaining_amount:
        raise HTTPException(
            status_code=400,
            detail=f"Allocated amount exceeds the remaining payment amount. Remaining amount: {remaining_amount}")

    existing_invoice_allocations=db.query(PaymentAllocationDB).filter(PaymentAllocationDB.invoice_id==allocation.invoice_id).all()

    total_invoice_allocated_amount=sum(amount.allocated_amount for amount in existing_invoice_allocations)

    outstanding_balance=invoice.invoice_amount-total_invoice_allocated_amount

    if allocation.allocated_amount > outstanding_balance:
        raise HTTPException(
            status_code=400,
            detail=f"Allocated amount exceeds the outstanding balance of the invoice. Outstanding balance: {outstanding_balance}")

    if payment.customer_id != invoice.customer_id:
        raise HTTPException(
            status_code=400,
            detail="Payment and invoice belong to different customers")

    payment_allocation=PaymentAllocationDB(
        payment_id=allocation.payment_id,
        invoice_id=allocation.invoice_id,
        allocated_amount=allocation.allocated_amount
    )

    db.add(payment_allocation)

    new_total = total_invoice_allocated_amount + allocation.allocated_amount
    
    if new_total == invoice.invoice_amount:
        invoice.invoice_status = InvoiceStatus.paid
    elif new_total < invoice.invoice_amount:
        invoice.invoice_status = InvoiceStatus.partially_paid

    try:
       db.commit()
    except Exception:
        db.rollback()
        raise

    db.refresh(payment_allocation)

    return payment_allocation

@router.get("/",response_model=list[PaymentAllocationResponse])
def get_payment_allocations(db:Session = Depends(get_db)):

    return db.query(PaymentAllocationDB).all()


@router.get("/{payment_allocation_id}",response_model=PaymentAllocationResponse)
def get_payment_allocation(payment_allocation_id:int,db:Session=Depends(get_db)):

    db_payment_allocation=db.query(PaymentAllocationDB).filter(PaymentAllocationDB.allocation_id == payment_allocation_id).first()

    if not db_payment_allocation:
        raise HTTPException(
            status_code=404,
            detail="Payment allocation not found"
        )

    return db_payment_allocation

@router.put("/{payment_allocation_id}",response_model=PaymentAllocationResponse)
def update_payment_allocation(payment_allocation_id:int,payment_allocation:PaymentAllocationUpdate,db:Session=Depends(get_db)):

    db_payment_allocation=db.query(PaymentAllocationDB).filter(PaymentAllocationDB.allocation_id == payment_allocation_id).first()

    payment = db.query(PaymentDB).filter(PaymentDB.payment_id == db_payment_allocation.payment_id).first()
    
    invoice = db.query(InvoiceDB).filter(InvoiceDB.invoice_id == db_payment_allocation.invoice_id).first()

    
    if not db_payment_allocation:
        raise HTTPException(
            status_code=404,
            detail="Payment allocation not found"
        )

    if invoice.invoice_status == InvoiceStatus.cancelled:
        raise HTTPException(
            status_code=400,
            detail="Cannot allocate payment to a cancelled or paid invoice"
        )

    existing_payment_allocations = db.query(PaymentAllocationDB).filter(PaymentAllocationDB.payment_id == db_payment_allocation.payment_id).all()

    total_allocated_amount = sum(item.allocated_amount for item in existing_payment_allocations)

    remaining_amount = (payment.payment_amount - total_allocated_amount + db_payment_allocation.allocated_amount)

    if payment_allocation.allocated_amount > remaining_amount:
        raise HTTPException(
        status_code=400,
        detail=f"Updated allocation exceeds the remaining payment balance. "
               f"Maximum allowed amount: {remaining_amount}"
    )

    existing_invoice_allocations = db.query(PaymentAllocationDB).filter(PaymentAllocationDB.invoice_id == db_payment_allocation.invoice_id).all()

    total_invoice_allocated_amount = sum(item.allocated_amount for item in existing_invoice_allocations)

    outstanding_balance = (invoice.invoice_amount - total_invoice_allocated_amount + db_payment_allocation.allocated_amount)

    if payment_allocation.allocated_amount > outstanding_balance:
        raise HTTPException(
        status_code=400,
        detail=f"Updated allocation exceeds the invoice's outstanding balance. "
               f"Maximum allowed amount: {outstanding_balance}"
    )


    old_amount = db_payment_allocation.allocated_amount

    new_total = (total_invoice_allocated_amount-old_amount + payment_allocation.allocated_amount)

    db_payment_allocation.allocated_amount = payment_allocation.allocated_amount

    if new_total == invoice.invoice_amount:
        invoice.invoice_status = InvoiceStatus.paid
    elif new_total < invoice.invoice_amount:
        invoice.invoice_status = InvoiceStatus.partially_paid

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    db.refresh(db_payment_allocation)

    return db_payment_allocation

@router.delete("/{payment_allocation_id}")
def delete_payment_allocation(payment_allocation_id:int,db:Session=Depends(get_db)):
    
    db_payment_allocation = db.query(PaymentAllocationDB).filter(PaymentAllocationDB.allocation_id == payment_allocation_id).first()

    if not db_payment_allocation:
        raise HTTPException(
            status_code=404,
            detail="Payment allocation not found"
        )
    
    invoice = db.query(InvoiceDB).filter(InvoiceDB.invoice_id == db_payment_allocation.invoice_id).first()

    db.delete(db_payment_allocation)

    remaining_allocations = db.query(PaymentAllocationDB).filter(PaymentAllocationDB.invoice_id == invoice.invoice_id).all()

    new_total = sum(item.allocated_amount for item in remaining_allocations)

    if new_total == 0:
        invoice.invoice_status = InvoiceStatus.open
    elif new_total < invoice.invoice_amount:
        invoice.invoice_status = InvoiceStatus.partially_paid
    else:
        invoice.invoice_status = InvoiceStatus.paid

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    return f"Payment has been successfully deleted with allocation id {payment_allocation_id}."
    