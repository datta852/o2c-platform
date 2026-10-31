from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from database import PaymentAllocationDB, PaymentDB, PaymentReconciliationDB
from schemas import ReconciliationStatus


def synchronize_reconciliation_state(
    db: Session,
    payment: PaymentDB,
    *,
    clear_exception: bool = True,
    refresh_reconciled_at: bool = True,
) -> tuple[PaymentReconciliationDB, Decimal, bool]:
    """Derive persisted reconciliation state from a payment's current allocations.

    The caller owns the surrounding transaction and must flush allocation changes
    before calling this helper. The returned boolean indicates whether an existing
    exception reason was cleared.
    """
    reconciliation = db.query(PaymentReconciliationDB).filter(
        PaymentReconciliationDB.payment_id == payment.payment_id
    ).with_for_update().first()
    if reconciliation is None:
        reconciliation = PaymentReconciliationDB(
            payment_id=payment.payment_id,
            status=ReconciliationStatus.unmatched,
        )
        db.add(reconciliation)
        db.flush()

    amounts = db.query(PaymentAllocationDB.allocated_amount).filter(
        PaymentAllocationDB.payment_id == payment.payment_id
    ).all()
    allocated_total = sum((amount for (amount,) in amounts), Decimal("0"))

    if allocated_total > payment.payment_amount:
        reconciliation.status = ReconciliationStatus.exception
        reconciliation.exception_reason = (
            f"Allocated total {allocated_total} exceeds payment amount {payment.payment_amount}"
        )
        reconciliation.reconciled_at = None
        return reconciliation, allocated_total, False

    # An explicit reconciliation exception describes a failed reconciliation
    # attempt, which can coexist with the previous allocation plan. A state
    # repair must not dismiss that exception.
    had_exception = reconciliation.status == ReconciliationStatus.exception or (
        reconciliation.exception_reason is not None
    )
    if not clear_exception and had_exception:
        reconciliation.status = ReconciliationStatus.exception
        reconciliation.reconciled_at = None
        return reconciliation, allocated_total, False

    if allocated_total == 0:
        reconciliation.status = ReconciliationStatus.unmatched
    elif allocated_total < payment.payment_amount:
        reconciliation.status = ReconciliationStatus.partially_reconciled
    else:
        reconciliation.status = ReconciliationStatus.reconciled

    if clear_exception:
        reconciliation.exception_reason = None
    if reconciliation.status == ReconciliationStatus.reconciled:
        if refresh_reconciled_at or reconciliation.reconciled_at is None:
            reconciliation.reconciled_at = datetime.now(timezone.utc).replace(tzinfo=None)
    else:
        reconciliation.reconciled_at = None
    return reconciliation, allocated_total, bool(clear_exception and had_exception)
