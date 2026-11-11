"""Business calculations for customer credit exposure."""

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.orm import Session

from database import CustomerDB, InvoiceDB, PaymentAllocationDB, SalesOrderDB
from schemas import InvoiceStatus, order_Status


ZERO = Decimal("0")


class CustomerNotFoundError(LookupError):
    """Raised when a credit exposure is requested for an unknown customer."""


@dataclass(frozen=True)
class CreditExposure:
    customer_id: int
    credit_limit: Decimal
    outstanding_receivables: Decimal
    uninvoiced_order_exposure: Decimal
    total_credit_exposure: Decimal
    available_credit: Decimal


def _as_decimal(amount) -> Decimal:
    """Normalize SQLAlchemy numeric values without doing arithmetic as floats."""
    if isinstance(amount, Decimal):
        return amount
    return Decimal(str(amount))


def calculate_credit_exposure(customer_id: int, db: Session) -> CreditExposure:
    """Calculate current receivables and uninvoiced order exposure for a customer."""
    customer = db.query(CustomerDB).filter(CustomerDB.id == customer_id).first()
    if customer is None:
        raise CustomerNotFoundError(f"Customer {customer_id} was not found")

    eligible_invoice_statuses = (
        InvoiceStatus.open.value,
        InvoiceStatus.partially_paid.value,
        InvoiceStatus.overdue.value,
    )
    invoices = db.query(InvoiceDB.invoice_id, InvoiceDB.invoice_amount).filter(
        InvoiceDB.customer_id == customer_id,
        InvoiceDB.invoice_status.in_(eligible_invoice_statuses),
    ).all()

    allocated_by_invoice = {}
    allocation_rows = (
        db.query(PaymentAllocationDB.invoice_id, PaymentAllocationDB.allocated_amount)
        .join(InvoiceDB, InvoiceDB.invoice_id == PaymentAllocationDB.invoice_id)
        .filter(
            InvoiceDB.customer_id == customer_id,
            InvoiceDB.invoice_status.in_(eligible_invoice_statuses),
        )
        .all()
    )
    for invoice_id, allocated_amount in allocation_rows:
        allocated_by_invoice[invoice_id] = (
            allocated_by_invoice.get(invoice_id, ZERO) + _as_decimal(allocated_amount)
        )

    outstanding_receivables = sum(
        (
            _as_decimal(invoice_amount) - allocated_by_invoice.get(invoice_id, ZERO)
            for invoice_id, invoice_amount in invoices
        ),
        start=ZERO,
    )

    eligible_order_statuses = (
        order_Status.open.value,
        order_Status.awaiting_approval.value,
        order_Status.processed.value,
    )
    orders = db.query(SalesOrderDB.order_id, SalesOrderDB.order_amount).filter(
        SalesOrderDB.customer_id == customer_id,
        SalesOrderDB.order_status.in_(eligible_order_statuses),
    ).all()
    eligible_order_ids = [order_id for order_id, _ in orders]

    invoiced_by_order = {}
    if eligible_order_ids:
        invoiced_invoice_statuses = (
            InvoiceStatus.open.value,
            InvoiceStatus.partially_paid.value,
            InvoiceStatus.overdue.value,
            InvoiceStatus.paid.value,
        )
        invoice_rows = db.query(InvoiceDB.sales_order_id, InvoiceDB.invoice_amount).filter(
            InvoiceDB.sales_order_id.in_(eligible_order_ids),
            InvoiceDB.invoice_status.in_(invoiced_invoice_statuses),
        ).all()
        for order_id, invoice_amount in invoice_rows:
            invoiced_by_order[order_id] = (
                invoiced_by_order.get(order_id, ZERO) + _as_decimal(invoice_amount)
            )

    uninvoiced_order_exposure = sum(
        (
            _as_decimal(order_amount) - invoiced_by_order.get(order_id, ZERO)
            for order_id, order_amount in orders
        ),
        start=ZERO,
    )

    credit_limit = _as_decimal(customer.credit_limit)
    total_credit_exposure = outstanding_receivables + uninvoiced_order_exposure
    return CreditExposure(
        customer_id=customer.id,
        credit_limit=credit_limit,
        outstanding_receivables=outstanding_receivables,
        uninvoiced_order_exposure=uninvoiced_order_exposure,
        total_credit_exposure=total_credit_exposure,
        available_credit=credit_limit - total_credit_exposure,
    )
