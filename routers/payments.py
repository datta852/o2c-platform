import hashlib
import json
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database import (
    get_db, CustomerDB, PaymentDB, InvoiceDB, PaymentAllocationDB,
    PaymentReconciliationDB, PaymentReconciliationAuditDB, IdempotencyRecordDB,
)
from schemas import (
    PaymentCreate, PaymentUpdate, PaymentResponse, PaymentStatus, InvoiceStatus,
    ReconciliationStatus, PaymentReconciliationRequest, PaymentReconciliationResponse,
    PaymentReconciliationAuditResponse,
)
from security import require_api_key
from reconciliation_state import synchronize_reconciliation_state

router = APIRouter(
    prefix="/payments",
    tags=["Payments"],
    dependencies=[Depends(require_api_key)],
)


@router.post("/",response_model=PaymentResponse)
def create_payments(payment:PaymentCreate,db:Session=Depends(get_db)):

    customer=db.query(CustomerDB).filter(CustomerDB.id==payment.customer_id).first()

    if not customer:
        raise HTTPException(
            status_code=404,
            detail="Customer not found")

    db_payment=PaymentDB(
        payment_reference=payment.payment_reference,
        customer_id=payment.customer_id,
        payment_date=payment.payment_date,
        payment_amount=payment.payment_amount,
        payment_method=payment.payment_method,
        payment_status=payment.payment_status
    )

    db.add(db_payment)
    db.commit()
    db.refresh(db_payment)

    return db_payment

@router.get("/",response_model=list[PaymentResponse])
def get_payments(db:Session=Depends(get_db)):
    # Here you would typically retrieve payments from a database
    return db.query(PaymentDB).all()

@router.get("/{payment_id}",response_model=PaymentResponse)
def get_payment(payment_id:int,db:Session=Depends(get_db)):

    db_payment=db.query(PaymentDB).filter(PaymentDB.payment_id==payment_id).first()

    if not db_payment:
        raise HTTPException(
            status_code=404,
            detail="Payment not found")

    return db_payment

@router.put("/{payment_id}",response_model=PaymentResponse)
def update_payment(payment_id:int,payment:PaymentUpdate,db:Session=Depends(get_db)):

    db_payment=db.query(PaymentDB).filter(PaymentDB.payment_id==payment_id).first()

    if not db_payment:
        raise HTTPException(status_code=404,detail="Payment not found")

    allocations = db.query(PaymentAllocationDB).filter(PaymentAllocationDB.payment_id == payment_id).all()
    allocated_total = sum((item.allocated_amount for item in allocations), Decimal("0"))
    if payment.payment_amount < allocated_total:
        raise HTTPException(status_code=409, detail="Payment amount cannot be less than its allocated total")
    if allocations and payment.payment_status != PaymentStatus.completed:
        raise HTTPException(status_code=409, detail="An allocated payment must remain completed")

    allocations = db.query(PaymentAllocationDB).filter(PaymentAllocationDB.payment_id == payment_id).all()
    allocated_total = sum((item.allocated_amount for item in allocations), Decimal("0"))
    if payment.payment_amount < allocated_total:
        raise HTTPException(status_code=409, detail="Payment amount cannot be less than its allocated total")
    if allocations and payment.payment_status != PaymentStatus.completed:
        raise HTTPException(status_code=409, detail="An allocated payment must remain completed")

    db_payment.payment_date=payment.payment_date
    db_payment.payment_amount=payment.payment_amount
    db_payment.payment_method=payment.payment_method
    db_payment.payment_status=payment.payment_status

    db.commit()

    return db_payment

@router.delete("/{payment_id}")
def delete_payment(payment_id:int,db:Session=Depends(get_db)):


    db_payment=db.query(PaymentDB).filter(PaymentDB.payment_id==payment_id).first()

    if not db_payment:
        raise HTTPException(
            status_code=404,
            detail="Payment not found")

    if db.query(PaymentAllocationDB.allocation_id).filter(
        PaymentAllocationDB.payment_id == payment_id
    ).first():
        raise HTTPException(status_code=409, detail="Payment has allocations and cannot be deleted")
    if db.query(PaymentReconciliationAuditDB.audit_id).filter(
        PaymentReconciliationAuditDB.payment_id == payment_id
    ).first():
        raise HTTPException(status_code=409, detail="Payment has reconciliation history and cannot be deleted")

    if db.query(PaymentAllocationDB.allocation_id).filter(
        PaymentAllocationDB.payment_id == payment_id
    ).first():
        raise HTTPException(status_code=409, detail="Payment has allocations and cannot be deleted")
    if db.query(PaymentReconciliationAuditDB.audit_id).filter(
        PaymentReconciliationAuditDB.payment_id == payment_id
    ).first():
        raise HTTPException(status_code=409, detail="Payment has reconciliation history and cannot be deleted")

    db.delete(db_payment)

    db.commit()

    return {"message": f"Payment with id {payment_id} has been deleted successfully."}

@router.post("/{payment_id}/reconcile", response_model=PaymentReconciliationResponse)
def reconcile_payment(
    payment_id: int,
    request: PaymentReconciliationRequest,
    idempotency_key: str = Header(min_length=1, max_length=128, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
):
    """Apply a complete allocation plan for a payment exactly once per key."""
    canonical_request = json.dumps(request.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    request_hash = hashlib.sha256(canonical_request.encode("utf-8")).hexdigest()

    prior_request = db.query(IdempotencyRecordDB).filter(
        IdempotencyRecordDB.idempotency_key == idempotency_key
    ).first()
    if prior_request:
        if prior_request.payment_id != payment_id or prior_request.request_hash != request_hash:
            raise HTTPException(status_code=409, detail="Idempotency key was already used for a different request")
        return PaymentReconciliationResponse.model_validate_json(prior_request.response_body)

    payment = db.query(PaymentDB).filter(PaymentDB.payment_id == payment_id).with_for_update().first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")

    reconciliation = db.query(PaymentReconciliationDB).filter(
        PaymentReconciliationDB.payment_id == payment_id
    ).first()
    if not reconciliation:
        reconciliation = PaymentReconciliationDB(payment_id=payment_id, status=ReconciliationStatus.unmatched)
        db.add(reconciliation)
        db.flush()

    current_allocations = db.query(PaymentAllocationDB).filter(
        PaymentAllocationDB.payment_id == payment_id
    ).all()
    allocation_plan = {line.invoice_id: line.allocated_amount for line in request.allocations}
    exception_reason = None

    if payment.payment_status != PaymentStatus.completed:
        exception_reason = "Only completed payments can be reconciled"
    elif len(allocation_plan) != len(request.allocations):
        exception_reason = "An invoice may appear only once in a reconciliation request"
    elif sum(allocation_plan.values(), Decimal("0")) > payment.payment_amount:
        exception_reason = "Requested allocations exceed the payment amount"

    invoices = {}
    if exception_reason is None:
        for invoice_id, amount in sorted(allocation_plan.items()):
            invoice = db.query(InvoiceDB).filter(InvoiceDB.invoice_id == invoice_id).with_for_update().first()
            if invoice is None:
                exception_reason = f"Invoice {invoice_id} was not found"
                break
            if invoice.customer_id != payment.customer_id:
                exception_reason = f"Invoice {invoice_id} belongs to a different customer"
                break
            if invoice.invoice_status == InvoiceStatus.cancelled:
                exception_reason = f"Invoice {invoice_id} is cancelled"
                break
            allocated_by_other_payments = db.query(PaymentAllocationDB).filter(
                PaymentAllocationDB.invoice_id == invoice_id,
                PaymentAllocationDB.payment_id != payment_id,
            ).all()
            other_total = sum((item.allocated_amount for item in allocated_by_other_payments), Decimal("0"))
            if amount > invoice.invoice_amount - other_total:
                exception_reason = f"Requested allocation exceeds invoice {invoice_id}'s outstanding balance"
                break
            invoices[invoice_id] = invoice

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if exception_reason:
        status = ReconciliationStatus.exception
        reconciliation.status = status
        reconciliation.exception_reason = exception_reason
        reconciliation.reconciled_at = None
    else:
        # The request is the target allocation plan, so a corrected request replaces
        # this payment's previous plan rather than adding a duplicate allocation.
        affected_invoice_ids = {item.invoice_id for item in current_allocations} | set(allocation_plan)
        for existing in current_allocations:
            db.delete(existing)
        db.flush()
        for invoice_id, amount in allocation_plan.items():
            db.add(PaymentAllocationDB(
                payment_id=payment_id,
                invoice_id=invoice_id,
                allocated_amount=amount,
            ))
        db.flush()

        for invoice_id in affected_invoice_ids:
            invoice = invoices.get(invoice_id) or db.query(InvoiceDB).filter(
                InvoiceDB.invoice_id == invoice_id
            ).first()
            if invoice:
                total = db.query(PaymentAllocationDB.allocated_amount).filter(
                    PaymentAllocationDB.invoice_id == invoice_id
                ).all()
                allocated = sum((amount for (amount,) in total), Decimal("0"))
                if allocated == 0:
                    invoice.invoice_status = InvoiceStatus.open
                elif allocated >= invoice.invoice_amount:
                    invoice.invoice_status = InvoiceStatus.paid
                else:
                    invoice.invoice_status = InvoiceStatus.partially_paid

        reconciliation, total_allocated, _ = synchronize_reconciliation_state(db, payment)
        status = reconciliation.status
        exception_reason = reconciliation.exception_reason

    actual_allocations = db.query(PaymentAllocationDB.allocated_amount).filter(
        PaymentAllocationDB.payment_id == payment_id
    ).all()
    actual_allocated = sum((amount for (amount,) in actual_allocations), Decimal("0"))
    response = PaymentReconciliationResponse(
        payment_id=payment_id,
        status=status,
        allocated_amount=actual_allocated,
        unapplied_amount=max(payment.payment_amount - actual_allocated, Decimal("0")),
        exception_reason=exception_reason,
        reconciled_at=reconciliation.reconciled_at,
    )
    db.add(PaymentReconciliationAuditDB(
        payment_id=payment_id,
        action=status.value,
        details=json.dumps({
            "idempotency_key": idempotency_key,
            "requested_allocations": [
                {"invoice_id": invoice_id, "allocated_amount": str(amount)}
                for invoice_id, amount in allocation_plan.items()
            ],
            "exception_reason": exception_reason,
            "response": response.model_dump(mode="json"),
        }, sort_keys=True),
        occurred_at=now,
    ))
    db.add(IdempotencyRecordDB(
        idempotency_key=idempotency_key,
        request_hash=request_hash,
        response_body=response.model_dump_json(),
        payment_id=payment_id,
    ))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        # A concurrent retry may have committed the same key while this request
        # was processing. Return its stored result instead of applying twice.
        prior_request = db.query(IdempotencyRecordDB).filter(
            IdempotencyRecordDB.idempotency_key == idempotency_key
        ).first()
        if prior_request and prior_request.payment_id == payment_id and prior_request.request_hash == request_hash:
            return PaymentReconciliationResponse.model_validate_json(prior_request.response_body)
        if prior_request:
            raise HTTPException(status_code=409, detail="Idempotency key was already used for a different request")
        raise
    except Exception:
        db.rollback()
        raise
    return response


@router.get("/{payment_id}/reconciliation", response_model=PaymentReconciliationResponse)
def get_payment_reconciliation(payment_id: int, db: Session = Depends(get_db)):
    # Locking the payment serializes GET-triggered creation/repair with other
    # reconciliation operations on databases that support row locks. The unique
    # constraint remains the final safeguard; retry once if two readers race to
    # create a previously missing reconciliation row.
    for attempt in range(2):
        try:
            payment = db.query(PaymentDB).filter(
                PaymentDB.payment_id == payment_id
            ).with_for_update().first()
            if not payment:
                raise HTTPException(status_code=404, detail="Payment not found")
            reconciliation = db.query(PaymentReconciliationDB).filter(
                PaymentReconciliationDB.payment_id == payment_id
            ).first()
            previous_state = (
                (reconciliation.status, reconciliation.exception_reason, reconciliation.reconciled_at)
                if reconciliation is not None else None
            )
            reconciliation, allocated, _ = synchronize_reconciliation_state(
                db, payment, clear_exception=False, refresh_reconciled_at=False
            )
            current_state = (
                reconciliation.status, reconciliation.exception_reason, reconciliation.reconciled_at
            )
            if previous_state != current_state:
                db.add(PaymentReconciliationAuditDB(
                    payment_id=payment_id,
                    action="RECONCILIATION_STATE_REPAIRED",
                    details=json.dumps({
                        "previous_status": (
                            getattr(previous_state[0], "value", previous_state[0])
                            if previous_state else None
                        ),
                        "previous_exception_reason": previous_state[1] if previous_state else None,
                        "status": reconciliation.status.value,
                        "exception_reason": reconciliation.exception_reason,
                        "allocated_amount": str(allocated),
                        "payment_amount": str(payment.payment_amount),
                    }, sort_keys=True),
                    occurred_at=datetime.now(timezone.utc).replace(tzinfo=None),
                ))
                db.commit()
            return PaymentReconciliationResponse(
                payment_id=payment_id,
                status=reconciliation.status,
                allocated_amount=allocated,
                unapplied_amount=max(payment.payment_amount - allocated, Decimal("0")),
                exception_reason=reconciliation.exception_reason,
                reconciled_at=reconciliation.reconciled_at,
            )
        except IntegrityError:
            db.rollback()
            if attempt == 1:
                raise
        except Exception:
            db.rollback()
            raise
    raise HTTPException(status_code=409, detail="Could not synchronize payment reconciliation state")


@router.get("/{payment_id}/reconciliation-audit", response_model=list[PaymentReconciliationAuditResponse])
def get_reconciliation_audit(payment_id: int, db: Session = Depends(get_db)):
    if not db.query(PaymentDB.payment_id).filter(PaymentDB.payment_id == payment_id).first():
        raise HTTPException(status_code=404, detail="Payment not found")
    return db.query(PaymentReconciliationAuditDB).filter(
        PaymentReconciliationAuditDB.payment_id == payment_id
    ).order_by(PaymentReconciliationAuditDB.audit_id).all()
