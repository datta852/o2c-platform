"""Baseline schema from the initial O2C application."""

from alembic import op
import sqlalchemy as sa

revision = "0001_core"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "Customers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("country", sa.String(), nullable=True),
        sa.Column("email", sa.String(), nullable=True),
        sa.Column("credit_limit", sa.Numeric(15, 2), nullable=True),
        sa.Column("payment_terms", sa.String(), nullable=True),
    )
    op.create_index("ix_Customers_id", "Customers", ["id"])
    op.create_table(
        "Salesorders",
        sa.Column("order_id", sa.Integer(), primary_key=True),
        sa.Column("customer_id", sa.Integer(), sa.ForeignKey("Customers.id"), nullable=True),
        sa.Column("order_date", sa.Date(), nullable=True),
        sa.Column("order_amount", sa.Numeric(15, 2), nullable=True),
        sa.Column("order_status", sa.String(), nullable=True),
    )
    op.create_index("ix_Salesorders_order_id", "Salesorders", ["order_id"])
    op.create_table(
        "Invoices",
        sa.Column("invoice_id", sa.Integer(), primary_key=True),
        sa.Column("invoice_number", sa.String(), nullable=True),
        sa.Column("customer_id", sa.Integer(), sa.ForeignKey("Customers.id"), nullable=True),
        sa.Column("sales_order_id", sa.Integer(), sa.ForeignKey("Salesorders.order_id"), nullable=True),
        sa.Column("invoice_date", sa.Date(), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("invoice_amount", sa.Numeric(15, 2), nullable=True),
        sa.Column("invoice_status", sa.String(), nullable=True),
        sa.UniqueConstraint("invoice_number"),
    )
    op.create_index("ix_Invoices_invoice_id", "Invoices", ["invoice_id"])
    op.create_table(
        "Payments",
        sa.Column("payment_id", sa.Integer(), primary_key=True),
        sa.Column("payment_reference", sa.String(), nullable=True),
        sa.Column("customer_id", sa.Integer(), sa.ForeignKey("Customers.id"), nullable=True),
        sa.Column("payment_date", sa.Date(), nullable=True),
        sa.Column("payment_amount", sa.Numeric(15, 2), nullable=True),
        sa.Column("payment_method", sa.String(), nullable=True),
        sa.Column("payment_status", sa.String(), nullable=True),
        sa.UniqueConstraint("payment_reference"),
    )
    op.create_index("ix_Payments_payment_id", "Payments", ["payment_id"])
    op.create_table(
        "PaymentAllocations",
        sa.Column("allocation_id", sa.Integer(), primary_key=True),
        sa.Column("payment_id", sa.Integer(), sa.ForeignKey("Payments.payment_id"), nullable=True),
        sa.Column("invoice_id", sa.Integer(), sa.ForeignKey("Invoices.invoice_id"), nullable=True),
        sa.Column("allocated_amount", sa.Numeric(15, 2), nullable=True),
    )
    op.create_index("ix_PaymentAllocations_allocation_id", "PaymentAllocations", ["allocation_id"])


def downgrade() -> None:
    op.drop_table("PaymentAllocations")
    op.drop_table("Payments")
    op.drop_table("Invoices")
    op.drop_table("Salesorders")
    op.drop_table("Customers")
