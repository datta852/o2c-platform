import json
from contextlib import contextmanager
from decimal import Decimal
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import (
    get_db,
    PaymentDB,
    InvoiceDB,
    PaymentAllocationDB,
    PaymentReconciliationAuditDB,
)
from reconciliation_state import synchronize_reconciliation_state
from schemas import (
    PaymentAllocationCreate,
    PaymentAllocationResponse,
    PaymentAllocationUpdate,
    InvoiceStatus,
    PaymentStatus,
)
from security import require_api_key

router = APIRouter(
    prefix="/payment_allocations",
    tags=["Payment Allocations"],
    dependencies=[Depends(require_api_key)],
)


@contextmanager
def _rollback_on_error(db: Session):
    try:
        yield
    except Exception:
        db.rollback()
        raise


def _invoice_allocated_total(db: Session, invoice_id: int) -> Decimal:
    amounts = db.query(PaymentAllocationDB.allocated_amount).filter(
        PaymentAllocationDB.invoice_id == invoice_id
    ).all()
    return sum((amount for (amount,) in amounts), Decimal("0"))


def _set_invoice_status(invoice: InvoiceDB, allocated_total: Decimal) -> None:
    if allocated_total == 0:
        invoice.invoice_status = InvoiceStatus.open
    elif allocated_total >= invoice.invoice_amount:
        invoice.invoice_status = InvoiceStatus.paid
    else:
        invoice.invoice_status = InvoiceStatus.partially_paid


@router.post("/",response_model=PaymentAllocationResponse)
def create_payment_allocation(allocation:PaymentAllocationCreate,db:Session=Depends(get_db)):

    payment=db.query(PaymentDB).filter(PaymentDB.payment_id==allocation.payment_id).with_for_update().first()

    invoice=db.query(InvoiceDB).filter(InvoiceDB.invoice_id==allocation.invoice_id).with_for_update().first()

    if not payment:
        raise HTTPException(
            status_code=404,
            detail="Payment not found")

    if not invoice:
        raise HTTPException(
            status_code=404,
            detail="Invoice not found")

    if payment.payment_status != PaymentStatus.completed:
        raise HTTPException(status_code=400, detail="Only completed payments can be allocated")
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

    duplicate = db.query(PaymentAllocationDB).filter(
        PaymentAllocationDB.payment_id == allocation.payment_id,
        PaymentAllocationDB.invoice_id == allocation.invoice_id,
    ).first()
    if duplicate:
        raise HTTPException(
            status_code=409,
            detail="This payment already has an allocation for the invoice; update the existing allocation",
        )

    payment_allocation=PaymentAllocationDB(
        payment_id=allocation.payment_id,
        invoice_id=allocation.invoice_id,
        allocated_amount=allocation.allocated_amount
    )

    with _rollback_on_error(db):
        db.add(payment_allocation)
        db.flush()
        reconciliation, _, exception_cleared = synchronize_reconciliation_state(db, payment)
        db.add(PaymentReconciliationAuditDB(
            payment_id=payment.payment_id,
            action="MANUAL_ALLOCATION_CREATED",
            details=json.dumps({
                "invoice_id": invoice.invoice_id,
                "allocated_amount": str(allocation.allocated_amount),
                "reconciliation_status": reconciliation.status.value,
                "exception_cleared": exception_cleared,
            }),
            occurred_at=datetime.now(timezone.utc).replace(tzinfo=None),
        ))

        new_total = total_invoice_allocated_amount + allocation.allocated_amount
        _set_invoice_status(invoice, new_total)
        db.commit()

    db.refresh(payment_allocation)

    return payment_allocation

@router.get("/",response_model=list[PaymentAllocationResponse])
def get_payment_allocations(db:Session = Depends(get_db)):

    return db.query(PaymentAllocationDB).all()


@router.get("/{payment_allocation_id}",response_model=PaymentAllocationResponse)
def get_payment_allocation(payment_allocation_id:int,db:Session=Depends(get_db)):

    db_payment_allocation=db.query(PaymentAllocationDB).filter(PaymentAllocationDB.allocation_id == payment_allocation_id).with_for_update().first()

    if not db_payment_allocation:
        raise HTTPException(
            status_code=404,
            detail="Payment allocation not found"
        )

    return db_payment_allocation

@router.put("/{payment_allocation_id}",response_model=PaymentAllocationResponse)
def update_payment_allocation(payment_allocation_id:int,payment_allocation:PaymentAllocationUpdate,db:Session=Depends(get_db)):

    db_payment_allocation=db.query(PaymentAllocationDB).filter(PaymentAllocationDB.allocation_id == payment_allocation_id).first()
    if not db_payment_allocation:
        raise HTTPException(
            status_code=404,
            detail="Payment allocation not found"
        )

    payment = db.query(PaymentDB).filter(PaymentDB.payment_id == db_payment_allocation.payment_id).with_for_update().first()
    invoice = db.query(InvoiceDB).filter(InvoiceDB.invoice_id == db_payment_allocation.invoice_id).with_for_update().first()

    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    if payment.payment_status != PaymentStatus.completed:
        raise HTTPException(status_code=400, detail="Only completed payments can be allocated")

    if invoice.invoice_status == InvoiceStatus.cancelled:
        raise HTTPException(
            status_code=400,
            detail="Cannot allocate payment to a cancelled or paid invoice"
        )

    payment_allocated_elsewhere = db.query(PaymentAllocationDB).filter(
        PaymentAllocationDB.payment_id == payment.payment_id,
        PaymentAllocationDB.allocation_id != payment_allocation_id,
    ).all()
    total_allocated_elsewhere = sum(
        (item.allocated_amount for item in payment_allocated_elsewhere), Decimal("0")
    )
    remaining_amount = payment.payment_amount - total_allocated_elsewhere

    if payment_allocation.allocated_amount > remaining_amount:
        raise HTTPException(
        status_code=400,
        detail=f"Updated allocation exceeds the remaining payment balance. "
               f"Maximum allowed amount: {remaining_amount}"
    )

    invoice_allocated_elsewhere = db.query(PaymentAllocationDB).filter(
        PaymentAllocationDB.invoice_id == invoice.invoice_id,
        PaymentAllocationDB.allocation_id != payment_allocation_id,
    ).all()
    total_invoice_allocated_elsewhere = sum(
        (item.allocated_amount for item in invoice_allocated_elsewhere), Decimal("0")
    )
    outstanding_balance = invoice.invoice_amount - total_invoice_allocated_elsewhere

    if payment_allocation.allocated_amount > outstanding_balance:
        raise HTTPException(
        status_code=400,
        detail=f"Updated allocation exceeds the invoice's outstanding balance. "
               f"Maximum allowed amount: {outstanding_balance}"
    )


    if payment.customer_id != invoice.customer_id:
        raise HTTPException(status_code=400, detail="Payment and invoice belong to different customers")

    with _rollback_on_error(db):
        old_amount = db_payment_allocation.allocated_amount
        db_payment_allocation.allocated_amount = payment_allocation.allocated_amount
        _set_invoice_status(invoice, total_invoice_allocated_elsewhere + payment_allocation.allocated_amount)
        db.flush()
        reconciliation, _, exception_cleared = synchronize_reconciliation_state(db, payment)
        db.add(PaymentReconciliationAuditDB(
            payment_id=payment.payment_id,
            action="MANUAL_ALLOCATION_UPDATED",
            details=json.dumps({
                "invoice_id": invoice.invoice_id,
                "allocation_id": payment_allocation_id,
                "old_amount": str(old_amount),
                "new_amount": str(payment_allocation.allocated_amount),
                "reconciliation_status": reconciliation.status.value,
                "exception_cleared": exception_cleared,
            }),
            occurred_at=datetime.now(timezone.utc).replace(tzinfo=None),
        ))
        db.commit()

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
    
    payment = db.query(PaymentDB).filter(PaymentDB.payment_id == db_payment_allocation.payment_id).with_for_update().first()
    invoice = db.query(InvoiceDB).filter(InvoiceDB.invoice_id == db_payment_allocation.invoice_id).with_for_update().first()
    if invoice is None or payment is None:
        raise HTTPException(status_code=409, detail="Payment allocation has a missing related record")
    deleted_amount = db_payment_allocation.allocated_amount

    new_total = _invoice_allocated_total(db, invoice.invoice_id) - db_payment_allocation.allocated_amount
    with _rollback_on_error(db):
        db.delete(db_payment_allocation)
        db.flush()
        _set_invoice_status(invoice, new_total)
        reconciliation, _, exception_cleared = synchronize_reconciliation_state(db, payment)
        db.add(PaymentReconciliationAuditDB(
            payment_id=payment.payment_id,
            action="MANUAL_ALLOCATION_DELETED",
            details=json.dumps({
                "invoice_id": invoice.invoice_id,
                "allocation_id": payment_allocation_id,
                "allocated_amount": str(deleted_amount),
                "reconciliation_status": reconciliation.status.value,
                "exception_cleared": exception_cleared,
            }),
            occurred_at=datetime.now(timezone.utc).replace(tzinfo=None),
        ))
        db.commit()

    return {"message": f"Payment allocation {payment_allocation_id} deleted successfully."}
