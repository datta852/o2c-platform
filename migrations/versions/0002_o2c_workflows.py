"""Add reconciliation, collections, and financial integrity constraints."""

from alembic import op
import sqlalchemy as sa

revision = "0002_o2c_workflows"
down_revision = "0001_core"
branch_labels = None
depends_on = None


def _assert_no_bad_rows(table: str, required_columns: tuple[str, ...], positive_column: str | None = None) -> None:
    bind = op.get_bind()
    for column in required_columns:
        count = bind.execute(sa.text(f'SELECT COUNT(*) FROM "{table}" WHERE "{column}" IS NULL')).scalar_one()
        if count:
            raise RuntimeError(
                f"Migration stopped: {table}.{column} has {count} NULL row(s). "
                "Back up the database and correct the records before retrying."
            )
    if positive_column:
        count = bind.execute(sa.text(
            f'SELECT COUNT(*) FROM "{table}" WHERE "{positive_column}" <= 0'
        )).scalar_one()
        if count:
            raise RuntimeError(
                f"Migration stopped: {table}.{positive_column} has {count} non-positive row(s). "
                "Back up the database and correct the records before retrying."
            )


def _assert_no_orphans(child_table: str, child_column: str, parent_table: str, parent_column: str) -> None:
    count = op.get_bind().execute(sa.text(
        f'SELECT COUNT(*) FROM "{child_table}" c LEFT JOIN "{parent_table}" p '
        f'ON c."{child_column}" = p."{parent_column}" WHERE p."{parent_column}" IS NULL'
    )).scalar_one()
    if count:
        raise RuntimeError(
            f"Migration stopped: {child_table}.{child_column} has {count} orphaned reference(s) "
            f"to {parent_table}.{parent_column}. Back up the database and repair the records before retrying."
        )


def upgrade() -> None:
    _assert_no_bad_rows("Customers", ("name", "country", "email", "credit_limit", "payment_terms"))
    negative_credit_limits = op.get_bind().execute(sa.text(
        'SELECT COUNT(*) FROM "Customers" WHERE credit_limit < 0'
    )).scalar_one()
    if negative_credit_limits:
        raise RuntimeError(
            "Migration stopped: Customers.credit_limit has negative values. "
            "Back up the database and correct the records before retrying."
        )
    _assert_no_bad_rows("Salesorders", ("customer_id", "order_date", "order_amount", "order_status"), "order_amount")
    _assert_no_bad_rows("Invoices", ("invoice_number", "customer_id", "sales_order_id", "invoice_date", "due_date", "invoice_amount", "invoice_status"), "invoice_amount")
    _assert_no_bad_rows("Payments", ("payment_reference", "customer_id", "payment_date", "payment_amount", "payment_method", "payment_status"), "payment_amount")
    _assert_no_bad_rows("PaymentAllocations", ("payment_id", "invoice_id", "allocated_amount"), "allocated_amount")
    duplicates = op.get_bind().execute(sa.text(
        'SELECT COUNT(*) FROM (SELECT payment_id, invoice_id FROM "PaymentAllocations" '
        'GROUP BY payment_id, invoice_id HAVING COUNT(*) > 1)'
    )).scalar_one()
    if duplicates:
        raise RuntimeError(
            "Migration stopped: duplicate payment/invoice allocations exist. "
            "Back up the database and consolidate duplicates before retrying."
        )
    for child, child_column, parent, parent_column in (
        ("Salesorders", "customer_id", "Customers", "id"),
        ("Invoices", "customer_id", "Customers", "id"),
        ("Invoices", "sales_order_id", "Salesorders", "order_id"),
        ("Payments", "customer_id", "Customers", "id"),
        ("PaymentAllocations", "payment_id", "Payments", "payment_id"),
        ("PaymentAllocations", "invoice_id", "Invoices", "invoice_id"),
    ):
        _assert_no_orphans(child, child_column, parent, parent_column)

    inconsistent_invoice_owners = op.get_bind().execute(sa.text(
        'SELECT COUNT(*) FROM "Invoices" i JOIN "Salesorders" o ON i.sales_order_id=o.order_id '
        'WHERE i.customer_id != o.customer_id'
    )).scalar_one()
    if inconsistent_invoice_owners:
        raise RuntimeError(
            "Migration stopped: invoices and their sales orders have mismatched customers. "
            "Back up the database and correct the records before retrying."
        )
    overallocated_payments = op.get_bind().execute(sa.text(
        'SELECT COUNT(*) FROM (SELECT p.payment_id FROM "Payments" p JOIN "PaymentAllocations" a '
        'ON a.payment_id=p.payment_id GROUP BY p.payment_id HAVING SUM(a.allocated_amount)>p.payment_amount)'
    )).scalar_one()
    overallocated_invoices = op.get_bind().execute(sa.text(
        'SELECT COUNT(*) FROM (SELECT i.invoice_id FROM "Invoices" i JOIN "PaymentAllocations" a '
        'ON a.invoice_id=i.invoice_id GROUP BY i.invoice_id HAVING SUM(a.allocated_amount)>i.invoice_amount)'
    )).scalar_one()
    if overallocated_payments or overallocated_invoices:
        raise RuntimeError(
            "Migration stopped: existing allocations exceed a payment or invoice balance. "
            "Back up the database and correct the records before retrying."
        )

    op.create_table(
        "PaymentReconciliations",
        sa.Column("reconciliation_id", sa.Integer(), primary_key=True),
        sa.Column("payment_id", sa.Integer(), sa.ForeignKey("Payments.payment_id"), nullable=False, unique=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("exception_reason", sa.String(), nullable=True),
        sa.Column("reconciled_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_PaymentReconciliations_reconciliation_id", "PaymentReconciliations", ["reconciliation_id"])
    op.create_table(
        "PaymentReconciliationAudits",
        sa.Column("audit_id", sa.Integer(), primary_key=True),
        sa.Column("payment_id", sa.Integer(), sa.ForeignKey("Payments.payment_id"), nullable=False),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("details", sa.String(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_PaymentReconciliationAudits_audit_id", "PaymentReconciliationAudits", ["audit_id"])
    op.create_table(
        "IdempotencyRecords",
        sa.Column("idempotency_key", sa.String(), primary_key=True),
        sa.Column("request_hash", sa.String(), nullable=False),
        sa.Column("response_body", sa.String(), nullable=False),
        sa.Column("payment_id", sa.Integer(), sa.ForeignKey("Payments.payment_id"), nullable=False),
    )
    op.create_table(
        "DunningRules",
        sa.Column("rule_id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False, unique=True),
        sa.Column("days_overdue", sa.Integer(), nullable=False),
        sa.Column("action_type", sa.String(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.CheckConstraint("days_overdue >= 0", name="ck_dunning_rules_days_nonnegative"),
    )
    op.create_index("ix_DunningRules_rule_id", "DunningRules", ["rule_id"])
    op.create_table(
        "CollectionActions",
        sa.Column("action_id", sa.Integer(), primary_key=True),
        sa.Column("invoice_id", sa.Integer(), sa.ForeignKey("Invoices.invoice_id"), nullable=False),
        sa.Column("rule_id", sa.Integer(), sa.ForeignKey("DunningRules.rule_id"), nullable=False),
        sa.Column("action_type", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("scheduled_date", sa.Date(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("outcome", sa.String(), nullable=True),
        sa.UniqueConstraint("invoice_id", "rule_id", name="uq_collection_actions_invoice_rule"),
    )
    op.create_index("ix_CollectionActions_action_id", "CollectionActions", ["action_id"])

    with op.batch_alter_table("Customers") as batch:
        for column in ("name", "country", "email", "credit_limit", "payment_terms"):
            type_ = sa.Numeric(15, 2) if column == "credit_limit" else sa.String()
            batch.alter_column(column, existing_type=type_, nullable=False)
        batch.create_check_constraint("ck_customers_credit_limit_nonnegative", "credit_limit >= 0")
    with op.batch_alter_table("Salesorders") as batch:
        for column, type_ in (("customer_id", sa.Integer()), ("order_date", sa.Date()),
                              ("order_amount", sa.Numeric(15, 2)), ("order_status", sa.String())):
            batch.alter_column(column, existing_type=type_, nullable=False)
        batch.create_check_constraint("ck_orders_amount_positive", "order_amount > 0")
    with op.batch_alter_table("Invoices") as batch:
        for column, type_ in (("invoice_number", sa.String()), ("customer_id", sa.Integer()),
                              ("sales_order_id", sa.Integer()), ("invoice_date", sa.Date()),
                              ("due_date", sa.Date()), ("invoice_amount", sa.Numeric(15, 2)),
                              ("invoice_status", sa.String())):
            batch.alter_column(column, existing_type=type_, nullable=False)
        batch.create_check_constraint("ck_invoices_amount_positive", "invoice_amount > 0")
    with op.batch_alter_table("Payments") as batch:
        for column, type_ in (("payment_reference", sa.String()), ("customer_id", sa.Integer()),
                              ("payment_date", sa.Date()), ("payment_amount", sa.Numeric(15, 2)),
                              ("payment_method", sa.String()), ("payment_status", sa.String())):
            batch.alter_column(column, existing_type=type_, nullable=False)
        batch.create_check_constraint("ck_payments_amount_positive", "payment_amount > 0")
    with op.batch_alter_table("PaymentAllocations") as batch:
        for column, type_ in (("payment_id", sa.Integer()), ("invoice_id", sa.Integer()),
                              ("allocated_amount", sa.Numeric(15, 2))):
            batch.alter_column(column, existing_type=type_, nullable=False)
        batch.create_check_constraint("ck_payment_allocations_amount_positive", "allocated_amount > 0")
        batch.create_unique_constraint("uq_payment_allocations_payment_invoice", ["payment_id", "invoice_id"])


def downgrade() -> None:
    raise RuntimeError("Downgrade is disabled because financial allocation history must not be deleted")
