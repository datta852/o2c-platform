import atexit
import os
import tempfile
import unittest
from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

# Import database models while DATABASE_URL points at a disposable location.
# This protects the default o2c.db when this test module is discovered alone.
_original_cwd = os.getcwd()
_original_database_url = os.environ.get("DATABASE_URL")
_import_directory = tempfile.TemporaryDirectory(dir=os.path.dirname(__file__))
os.environ["DATABASE_URL"] = "sqlite:///" + os.path.join(
    _import_directory.name, "application.sqlite"
).replace("\\", "/")
try:
    os.chdir(_import_directory.name)
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    import database as _database_module
    from database import (
        Base,
        CustomerDB,
        InvoiceDB,
        PaymentAllocationDB,
        PaymentDB,
        SalesOrderDB,
    )
    from services.credit_management import (
        CustomerNotFoundError,
        calculate_credit_exposure,
    )
finally:
    os.chdir(_original_cwd)
    if _original_database_url is None:
        os.environ.pop("DATABASE_URL", None)
    else:
        os.environ["DATABASE_URL"] = _original_database_url


def _cleanup_import_database():
    _database_module.engine.dispose()
    _import_directory.cleanup()


atexit.register(_cleanup_import_database)


class CreditExposureCalculationTests(unittest.TestCase):
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

    def setUp(self):
        Base.metadata.create_all(self.engine)
        self.db = self.Session()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(self.engine)

    def add_customer(self, credit_limit=Decimal("1000.00")):
        suffix = uuid4().hex
        customer = CustomerDB(
            name=f"Credit Test {suffix}",
            country="IN",
            email=f"credit-{suffix}@example.test",
            credit_limit=credit_limit,
            payment_terms="Net_30",
        )
        self.db.add(customer)
        self.db.flush()
        return customer

    def add_order(self, customer_id, amount, status):
        order = SalesOrderDB(
            customer_id=customer_id,
            order_date=date.today(),
            order_amount=amount,
            order_status=status,
        )
        self.db.add(order)
        self.db.flush()
        return order

    def add_invoice(self, customer_id, order_id, amount, status, allocated=Decimal("0")):
        invoice = InvoiceDB(
            customer_id=customer_id,
            sales_order_id=order_id,
            invoice_number=f"CREDIT-{uuid4().hex}",
            invoice_date=date.today(),
            due_date=date.today() + timedelta(days=30),
            invoice_amount=amount,
            invoice_status=status,
        )
        self.db.add(invoice)
        self.db.flush()

        if allocated:
            payment = PaymentDB(
                payment_reference=f"CREDIT-PAY-{uuid4().hex}",
                customer_id=customer_id,
                payment_date=date.today(),
                payment_amount=allocated,
                payment_method="BANK_TRANSFER",
                payment_status="COMPLETED",
            )
            self.db.add(payment)
            self.db.flush()
            self.db.add(PaymentAllocationDB(
                payment_id=payment.payment_id,
                invoice_id=invoice.invoice_id,
                allocated_amount=allocated,
            ))

        return invoice

    def test_calculates_receivables_and_uninvoiced_exposure_by_status(self):
        customer = self.add_customer(Decimal("1000.00"))

        # Eligible orders: unbilled OPEN, partly invoiced AWAITING_APPROVAL,
        # and PROCESSED with multiple invoices.
        open_order = self.add_order(customer.id, Decimal("300.00"), "OPEN")
        awaiting_order = self.add_order(customer.id, Decimal("300.00"), "AWAITING_APPROVAL")
        processed_order = self.add_order(customer.id, Decimal("300.00"), "PROCESSED")

        self.add_invoice(
            customer.id, awaiting_order.order_id, Decimal("200.00"),
            "PARTIALLY_PAID", Decimal("50.00"),
        )
        self.add_invoice(
            customer.id, processed_order.order_id, Decimal("80.00"),
            "OVERDUE", Decimal("30.00"),
        )
        self.add_invoice(
            customer.id, processed_order.order_id, Decimal("20.00"), "OPEN"
        )
        # Fully paid and cancelled invoices do not contribute to receivables.
        self.add_invoice(
            customer.id, processed_order.order_id, Decimal("100.00"),
            "PAID", Decimal("100.00"),
        )
        self.add_invoice(
            customer.id, processed_order.order_id, Decimal("90.00"),
            "CANCELLED",
        )

        # These order states do not contribute any uninvoiced exposure.
        for status in ("BLOCKED", "CLOSED", "CANCELLED"):
            self.add_order(customer.id, Decimal("500.00"), status)

        result = calculate_credit_exposure(customer.id, self.db)

        self.assertEqual(result.customer_id, customer.id)
        self.assertEqual(result.credit_limit, Decimal("1000.00"))
        self.assertEqual(result.outstanding_receivables, Decimal("220.00"))
        self.assertEqual(result.uninvoiced_order_exposure, Decimal("500.00"))
        self.assertEqual(result.total_credit_exposure, Decimal("720.00"))
        self.assertEqual(result.available_credit, Decimal("280.00"))
        for amount in (
            result.credit_limit,
            result.outstanding_receivables,
            result.uninvoiced_order_exposure,
            result.total_credit_exposure,
            result.available_credit,
        ):
            self.assertIsInstance(amount, Decimal)

    def test_customer_without_financial_records_has_full_available_credit(self):
        customer = self.add_customer(Decimal("750.25"))

        result = calculate_credit_exposure(customer.id, self.db)

        self.assertEqual(result.outstanding_receivables, Decimal("0"))
        self.assertEqual(result.uninvoiced_order_exposure, Decimal("0"))
        self.assertEqual(result.total_credit_exposure, Decimal("0"))
        self.assertEqual(result.available_credit, Decimal("750.25"))

    def test_cancelled_invoice_does_not_reduce_uninvoiced_order_exposure(self):
        customer = self.add_customer()
        order = self.add_order(customer.id, Decimal("1000.00"), "PROCESSED")
        self.add_invoice(customer.id, order.order_id, Decimal("300.00"), "OPEN")
        self.add_invoice(customer.id, order.order_id, Decimal("200.00"), "CANCELLED")

        result = calculate_credit_exposure(customer.id, self.db)

        self.assertEqual(result.uninvoiced_order_exposure, Decimal("700.00"))

    def test_missing_customer_raises_a_clear_domain_error(self):
        with self.assertRaisesRegex(CustomerNotFoundError, "Customer 987654 was not found"):
            calculate_credit_exposure(987654, self.db)


if __name__ == "__main__":
    unittest.main()
