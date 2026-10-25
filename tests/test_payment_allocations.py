import os
import tempfile
import unittest
from datetime import date
from decimal import Decimal

# database.py creates its configured SQLite file when imported. Import it while
# the working directory is temporary so test discovery never touches o2c.db.
_original_cwd = os.getcwd()
_import_directory = tempfile.TemporaryDirectory(dir=os.path.dirname(__file__))
_original_database_url = os.environ.get("DATABASE_URL")
os.environ["DATABASE_URL"] = "sqlite:///" + os.path.join(_import_directory.name, "application.sqlite").replace("\\", "/")
os.chdir(_import_directory.name)
try:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from database import (
        Base, CustomerDB, SalesOrderDB, InvoiceDB, PaymentDB, PaymentAllocationDB,
        PaymentReconciliationDB, PaymentReconciliationAuditDB, IdempotencyRecordDB,
    )
    import database as _database_module
    from routers.payment_allocations import update_payment_allocation, delete_payment_allocation
    from routers.payments import reconcile_payment, get_payment_reconciliation, create_payments
    from routers.customers import create_customer
    from routers.sales_orders import create_sales_orders
    from routers.invoices import create_invoice, get_invoice, delete_invoice
    from routers.collections import (
        create_dunning_rule, run_collections, list_collection_actions,
        record_collection_outcome, list_receivables, receivables_summary,
    )
    from schemas import (
        InvoiceStatus, PaymentAllocationUpdate, PaymentReconciliationRequest,
        ReconciliationAllocation, ReconciliationStatus, DunningRuleCreate,
        CollectionActionType, CollectionActionOutcome, CollectionActionStatus,
        PaymentCreate, PaymentMethod, PaymentStatus, CustomerCreate,
        PaymentTerms, SalesOrderCreate, order_Status, InvoiceCreate,
    )
    from main import app
    from security import require_api_key
finally:
    os.chdir(_original_cwd)
    if _original_database_url is None:
        os.environ.pop("DATABASE_URL", None)
    else:
        os.environ["DATABASE_URL"] = _original_database_url


class PaymentAllocationMutationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        cls.Session = sessionmaker(bind=cls.engine)

    @classmethod
    def tearDownClass(cls):
        cls.engine.dispose()
        _database_module.engine.dispose()
        _import_directory.cleanup()

    def setUp(self):
        Base.metadata.create_all(self.engine)
        self.db = self.Session()
        customer = CustomerDB(name="Test", country="US", email="test@example.com")
        self.db.add(customer)
        self.db.flush()
        order = SalesOrderDB(
            customer_id=customer.id,
            order_date=date(2025, 12, 1),
            order_amount=Decimal("100.00"),
            order_status="PROCESSED",
        )
        self.db.add(order)
        self.db.flush()
        self.invoice = InvoiceDB(
            customer_id=customer.id,
            sales_order_id=order.order_id,
            invoice_number="INV-1",
            invoice_date=date(2026, 1, 1),
            due_date=date(2026, 1, 31),
            invoice_amount=Decimal("100.00"),
            invoice_status=InvoiceStatus.partially_paid,
        )
        self.payment = PaymentDB(
            customer_id=customer.id,
            payment_reference="PAY-1",
            payment_date=date(2026, 1, 10),
            payment_amount=Decimal("100.00"),
            payment_method="BANK_TRANSFER",
            payment_status="COMPLETED",
        )
        self.db.add_all([self.invoice, self.payment])
        self.db.flush()
        self.allocation = PaymentAllocationDB(
            payment_id=self.payment.payment_id,
            invoice_id=self.invoice.invoice_id,
            allocated_amount=Decimal("60.00"),
        )
        self.db.add(self.allocation)
        self.db.commit()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(self.engine)

    def test_update_missing_allocation_returns_404(self):
        from fastapi import HTTPException

        with self.assertRaises(HTTPException) as error:
            update_payment_allocation(999, PaymentAllocationUpdate(allocated_amount=Decimal("10")), self.db)
        self.assertEqual(error.exception.status_code, 404)

    def test_update_rejects_amount_over_payment_or_invoice_balance(self):
        from fastapi import HTTPException

        with self.assertRaises(HTTPException) as payment_error:
            update_payment_allocation(self.allocation.allocation_id,
                PaymentAllocationUpdate(allocated_amount=Decimal("101")), self.db)
        self.assertEqual(payment_error.exception.status_code, 400)

        self.payment.payment_amount = Decimal("200.00")
        self.db.commit()
        with self.assertRaises(HTTPException) as invoice_error:
            update_payment_allocation(self.allocation.allocation_id,
                PaymentAllocationUpdate(allocated_amount=Decimal("101")), self.db)
        self.assertEqual(invoice_error.exception.status_code, 400)

    def test_update_to_full_then_partial_recalculates_invoice_status(self):
        self.allocation = update_payment_allocation(
            self.allocation.allocation_id,
            PaymentAllocationUpdate(allocated_amount=Decimal("100.00")),
            self.db,
        )
        self.assertEqual(self.invoice.invoice_status, InvoiceStatus.paid)

        update_payment_allocation(
            self.allocation.allocation_id,
            PaymentAllocationUpdate(allocated_amount=Decimal("40.00")),
            self.db,
        )
        self.assertEqual(self.invoice.invoice_status, InvoiceStatus.partially_paid)

    def test_delete_final_allocation_reopens_invoice(self):
        delete_payment_allocation(self.allocation.allocation_id, self.db)
        self.assertEqual(self.invoice.invoice_status, InvoiceStatus.open)
        self.assertIsNone(self.db.get(PaymentAllocationDB, self.allocation.allocation_id))

    def test_delete_missing_allocation_returns_404(self):
        from fastapi import HTTPException

        with self.assertRaises(HTTPException) as error:
            delete_payment_allocation(999, self.db)
        self.assertEqual(error.exception.status_code, 404)

    def test_reconcile_unmatched_payment_records_status_and_audit(self):
        result = reconcile_payment(
            self.payment.payment_id, PaymentReconciliationRequest(), "reconcile-empty", self.db
        )
        self.assertEqual(result.status, ReconciliationStatus.unmatched)
        self.assertEqual(result.unapplied_amount, Decimal("100.00"))
        self.assertEqual(self.db.query(PaymentReconciliationAuditDB).count(), 1)

    def test_get_payment_reconciliation_reports_current_state(self):
        result = get_payment_reconciliation(self.payment.payment_id, self.db)
        self.assertEqual(result.status, ReconciliationStatus.partially_reconciled)
        self.assertEqual(result.allocated_amount, Decimal("60.00"))
        self.assertEqual(result.unapplied_amount, Decimal("40.00"))

    def test_customer_to_order_invoice_payment_reconciliation_flow(self):
        customer = create_customer(CustomerCreate(
            name="Flow Customer", country="US", email="flow@example.com",
            credit_limit=Decimal("1000.00"), payment_terms=PaymentTerms.net_30,
        ), self.db)
        order = create_sales_orders(SalesOrderCreate(
            customer_id=customer.id,
            order_date=date(2026, 1, 1),
            order_amount=Decimal("75.25"),
            order_status=order_Status.processed,
        ), self.db)
        invoice = create_invoice(InvoiceCreate(
            customer_id=customer.id,
            invoice_number="FLOW-INV",
            sales_order_id=order.order_id,
            invoice_date=date(2026, 1, 1),
            due_date=date(2026, 1, 31),
            invoice_amount=Decimal("75.25"),
            invoice_status=InvoiceStatus.open,
        ), self.db)
        payment = create_payments(PaymentCreate(
            payment_reference="FLOW-PAY",
            customer_id=customer.id,
            payment_date=date(2026, 1, 15),
            payment_amount=Decimal("75.25"),
            payment_method=PaymentMethod.bank_transfer,
            payment_status=PaymentStatus.completed,
        ), self.db)
        result = reconcile_payment(
            payment.payment_id,
            PaymentReconciliationRequest(allocations=[
                ReconciliationAllocation(invoice_id=invoice.invoice_id, allocated_amount=Decimal("75.25")),
            ]),
            "flow-idempotency-key",
            self.db,
        )
        self.assertEqual(result.status, ReconciliationStatus.reconciled)
        self.assertEqual(get_invoice(invoice.invoice_id, self.db).invoice_status, InvoiceStatus.paid)
        from fastapi import HTTPException
        with self.assertRaises(HTTPException) as delete_error:
            delete_invoice(invoice.invoice_id, self.db)
        self.assertEqual(delete_error.exception.status_code, 409)

    def test_reconcile_allocates_one_payment_across_multiple_invoices(self):
        second_invoice = InvoiceDB(
            customer_id=self.invoice.customer_id,
            sales_order_id=self.invoice.sales_order_id,
            invoice_number="INV-2",
            invoice_date=date(2026, 1, 1),
            due_date=date(2026, 1, 31),
            invoice_amount=Decimal("80.00"),
            invoice_status=InvoiceStatus.open,
        )
        self.db.add(second_invoice)
        self.db.commit()

        result = reconcile_payment(
            self.payment.payment_id,
            PaymentReconciliationRequest(allocations=[
                ReconciliationAllocation(invoice_id=self.invoice.invoice_id, allocated_amount=Decimal("60.00")),
                ReconciliationAllocation(invoice_id=second_invoice.invoice_id, allocated_amount=Decimal("40.00")),
            ]),
            "reconcile-multi",
            self.db,
        )
        self.assertEqual(result.status, ReconciliationStatus.reconciled)
        self.assertEqual(result.allocated_amount, Decimal("100.00"))
        self.assertEqual(self.db.query(PaymentAllocationDB).filter(
            PaymentAllocationDB.payment_id == self.payment.payment_id
        ).count(), 2)

    def test_reconcile_replay_returns_saved_result_without_duplicate_allocations(self):
        request = PaymentReconciliationRequest(allocations=[
            ReconciliationAllocation(invoice_id=self.invoice.invoice_id, allocated_amount=Decimal("100.00")),
        ])
        first = reconcile_payment(self.payment.payment_id, request, "reconcile-once", self.db)
        replay = reconcile_payment(self.payment.payment_id, request, "reconcile-once", self.db)
        self.assertEqual(first, replay)
        self.assertEqual(self.db.query(PaymentAllocationDB).count(), 1)
        self.assertEqual(self.db.query(PaymentReconciliationAuditDB).count(), 1)

    def test_reconcile_rejects_reusing_key_for_different_payload(self):
        from fastapi import HTTPException

        reconcile_payment(self.payment.payment_id, PaymentReconciliationRequest(), "same-key", self.db)
        changed_request = PaymentReconciliationRequest(allocations=[
            ReconciliationAllocation(invoice_id=self.invoice.invoice_id, allocated_amount=Decimal("10.00")),
        ])
        with self.assertRaises(HTTPException) as error:
            reconcile_payment(self.payment.payment_id, changed_request, "same-key", self.db)
        self.assertEqual(error.exception.status_code, 409)

    def test_reconcile_exception_is_audited_and_can_be_resolved(self):
        invalid_plan = PaymentReconciliationRequest(allocations=[
            ReconciliationAllocation(invoice_id=self.invoice.invoice_id, allocated_amount=Decimal("101.00")),
        ])
        failed = reconcile_payment(self.payment.payment_id, invalid_plan, "reconcile-invalid", self.db)
        self.assertEqual(failed.status, ReconciliationStatus.exception)
        self.assertIsNotNone(failed.exception_reason)
        self.assertEqual(self.db.query(PaymentAllocationDB).count(), 1)  # Existing plan is preserved.

        valid_plan = PaymentReconciliationRequest(allocations=[
            ReconciliationAllocation(invoice_id=self.invoice.invoice_id, allocated_amount=Decimal("100.00")),
        ])
        resolved = reconcile_payment(self.payment.payment_id, valid_plan, "reconcile-fixed", self.db)
        self.assertEqual(resolved.status, ReconciliationStatus.reconciled)
        self.assertIsNone(resolved.exception_reason)
        self.assertEqual(self.db.query(PaymentAllocationDB).count(), 1)
        self.assertEqual(self.db.query(PaymentReconciliationAuditDB).count(), 2)

    def test_receivables_reports_outstanding_and_overdue_balances(self):
        as_of = date(2026, 2, 20)
        rows = list_receivables(None, True, 100, 0, as_of, self.db)
        summary = receivables_summary(as_of, self.db)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].outstanding_amount, Decimal("40.00"))
        self.assertEqual(rows[0].days_overdue, 20)
        self.assertEqual(summary.overdue_amount, Decimal("40.00"))
        self.assertEqual(summary.overdue_invoice_count, 1)

    def test_collection_run_is_idempotent_and_records_outcome(self):
        rule = create_dunning_rule(
            DunningRuleCreate(
                name="First reminder",
                days_overdue=10,
                action_type=CollectionActionType.email_reminder,
            ),
            self.db,
        )
        as_of = date(2026, 2, 20)
        first_run = run_collections(as_of, self.db)
        second_run = run_collections(as_of, self.db)
        self.assertEqual(len(first_run), 1)
        self.assertEqual(second_run, [])
        self.assertEqual(first_run[0].rule_id, rule.rule_id)

        completed = record_collection_outcome(
            first_run[0].action_id,
            CollectionActionOutcome(status=CollectionActionStatus.completed, outcome="Reminder queued"),
            self.db,
        )
        replay = record_collection_outcome(
            first_run[0].action_id,
            CollectionActionOutcome(status=CollectionActionStatus.completed, outcome="Reminder queued"),
            self.db,
        )
        self.assertEqual(completed, replay)
        self.assertEqual(len(list_collection_actions(CollectionActionStatus.completed, 100, 0, self.db)), 1)

    def test_collection_rule_does_not_trigger_before_threshold(self):
        create_dunning_rule(
            DunningRuleCreate(
                name="Later reminder",
                days_overdue=30,
                action_type=CollectionActionType.email_reminder,
            ),
            self.db,
        )
        self.assertEqual(run_collections(date(2026, 2, 20), self.db), [])

    def test_money_schema_requires_positive_two_decimal_amounts(self):
        from pydantic import ValidationError

        base = {
            "payment_reference": "PRECISION-1",
            "customer_id": 1,
            "payment_date": date(2026, 1, 10),
            "payment_method": PaymentMethod.bank_transfer,
            "payment_status": PaymentStatus.completed,
        }
        with self.assertRaises(ValidationError):
            PaymentCreate(payment_amount=Decimal("0"), **base)
        with self.assertRaises(ValidationError):
            PaymentCreate(payment_amount=Decimal("1.001"), **base)
        valid = PaymentCreate(payment_amount=Decimal("1.01"), **base)
        self.assertEqual(valid.payment_amount, Decimal("1.01"))

    def test_sqlite_foreign_key_enforcement_is_enabled(self):
        with _database_module.engine.connect() as connection:
            enabled = connection.exec_driver_sql("PRAGMA foreign_keys").scalar()
        self.assertEqual(enabled, 1)

    def test_openapi_documents_reconciliation_and_collections_routes(self):
        paths = app.openapi()["paths"]
        self.assertIn("/payments/{payment_id}/reconcile", paths)
        self.assertIn("/receivables/summary", paths)
        self.assertIn("/collections/run", paths)

    def test_configured_api_key_is_required_and_compared_safely(self):
        from unittest.mock import patch
        from fastapi import HTTPException

        with patch.dict(os.environ, {"O2C_API_KEY": "synthetic-test-key"}):
            with self.assertRaises(HTTPException) as missing:
                require_api_key(api_key=None)
            self.assertEqual(missing.exception.status_code, 401)
            with self.assertRaises(HTTPException):
                require_api_key(api_key="wrong-key")
            self.assertIsNone(require_api_key(api_key="synthetic-test-key"))
        schemes = app.openapi()["components"]["securitySchemes"]
        self.assertIn("APIKeyHeader", schemes)

    def test_alembic_upgrades_legacy_schema_and_preserves_synthetic_rows(self):
        import os
        from alembic import command
        from alembic.config import Config
        from sqlalchemy import inspect, text

        migration_dir = tempfile.TemporaryDirectory(dir=os.path.dirname(__file__))
        database_path = os.path.join(migration_dir.name, "migration.sqlite").replace("\\", "/")
        database_url = "sqlite:///" + database_path
        previous_url = os.environ.get("DATABASE_URL")
        os.environ["DATABASE_URL"] = database_url
        migration_engine = None
        try:
            alembic_config = Config(os.path.join(os.path.dirname(os.path.dirname(__file__)), "alembic.ini"))
            command.upgrade(alembic_config, "0001_core")
            migration_engine = create_engine(database_url)
            with migration_engine.begin() as connection:
                connection.execute(text(
                    'INSERT INTO "Customers" (id,name,country,email,credit_limit,payment_terms) '
                    "VALUES (1,'Synthetic','US','synthetic@example.com',1000,'Net 30')"
                ))
                connection.execute(text(
                    'INSERT INTO "Salesorders" (order_id,customer_id,order_date,order_amount,order_status) '
                    "VALUES (1,1,'2026-01-01',100,'PROCESSED')"
                ))
                connection.execute(text(
                    'INSERT INTO "Invoices" (invoice_id,invoice_number,customer_id,sales_order_id,invoice_date,due_date,invoice_amount,invoice_status) '
                    "VALUES (1,'SYN-INV',1,1,'2026-01-01','2026-01-31',100,'PARTIALLY_PAID')"
                ))
                connection.execute(text(
                    'INSERT INTO "Payments" (payment_id,payment_reference,customer_id,payment_date,payment_amount,payment_method,payment_status) '
                    "VALUES (1,'SYN-PAY',1,'2026-01-02',50,'BANK_TRANSFER','COMPLETED')"
                ))
                connection.execute(text(
                    'INSERT INTO "PaymentAllocations" (allocation_id,payment_id,invoice_id,allocated_amount) '
                    "VALUES (1,1,1,25)"
                ))
            migration_engine.dispose()
            migration_engine = None

            command.upgrade(alembic_config, "head")
            command.check(alembic_config)
            migration_engine = create_engine(database_url)
            inspector = inspect(migration_engine)
            tables = set(inspector.get_table_names())
            self.assertIn("PaymentReconciliations", tables)
            self.assertIn("DunningRules", tables)
            self.assertIn("CollectionActions", tables)
            checks = {item["name"] for item in inspector.get_check_constraints("PaymentAllocations")}
            self.assertIn("ck_payment_allocations_amount_positive", checks)
            with migration_engine.connect() as connection:
                self.assertEqual(connection.execute(text('SELECT COUNT(*) FROM "PaymentAllocations"')).scalar_one(), 1)
        finally:
            if migration_engine:
                migration_engine.dispose()
            if previous_url is None:
                os.environ.pop("DATABASE_URL", None)
            else:
                os.environ["DATABASE_URL"] = previous_url
            migration_dir.cleanup()

    def test_alembic_refuses_legacy_rows_that_violate_new_constraints(self):
        import os
        from alembic import command
        from alembic.config import Config
        from sqlalchemy import inspect, text

        migration_dir = tempfile.TemporaryDirectory(dir=os.path.dirname(__file__))
        database_path = os.path.join(migration_dir.name, "invalid.sqlite").replace("\\", "/")
        database_url = "sqlite:///" + database_path
        previous_url = os.environ.get("DATABASE_URL")
        os.environ["DATABASE_URL"] = database_url
        migration_engine = None
        try:
            alembic_config = Config(os.path.join(os.path.dirname(os.path.dirname(__file__)), "alembic.ini"))
            command.upgrade(alembic_config, "0001_core")
            migration_engine = create_engine(database_url)
            with migration_engine.begin() as connection:
                connection.execute(text(
                    'INSERT INTO "Customers" (id,name,country,email,credit_limit,payment_terms) '
                    "VALUES (1,'Invalid','US',NULL,0,'Net 30')"
                ))
            migration_engine.dispose()
            migration_engine = None

            with self.assertRaisesRegex(RuntimeError, "Customers.email has 1 NULL"):
                command.upgrade(alembic_config, "head")
            migration_engine = create_engine(database_url)
            self.assertNotIn("PaymentReconciliations", inspect(migration_engine).get_table_names())
        finally:
            if migration_engine:
                migration_engine.dispose()
            if previous_url is None:
                os.environ.pop("DATABASE_URL", None)
            else:
                os.environ["DATABASE_URL"] = previous_url
            migration_dir.cleanup()

if __name__ == "__main__":
    unittest.main()
