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
    db.commit()
    db.refresh(payment_allocation)

    return payment_allocation
