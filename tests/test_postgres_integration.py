"""Integration tests against the dedicated, Alembic-managed PostgreSQL test DB."""

import os
import unittest
from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, make_url, text
from sqlalchemy.orm import sessionmaker

from database import get_db
from main import app


class PostgreSQLAPITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        database_url = os.getenv("O2C_TEST_DATABASE_URL")
        if not database_url:
            raise RuntimeError(
                "PostgreSQL integration tests require O2C_TEST_DATABASE_URL to be set"
            )

        try:
            parsed_url = make_url(database_url)
        except Exception as exc:
            raise RuntimeError("O2C_TEST_DATABASE_URL is not a valid SQLAlchemy URL") from exc

        if parsed_url.get_backend_name() != "postgresql":
            raise RuntimeError(
                "O2C_TEST_DATABASE_URL must use a PostgreSQL backend; refusing to connect"
            )
        if parsed_url.database != "o2c_platform_test":
            raise RuntimeError(
                "O2C_TEST_DATABASE_URL must target exactly 'o2c_platform_test'; refusing to connect"
            )

        # Explicitly select Psycopg 3 regardless of whether the supplied URL
        # uses SQLAlchemy's generic postgresql:// form or a driver-qualified URL.
        test_url = parsed_url.set(drivername="postgresql+psycopg")
        cls.engine = create_engine(test_url)

    @classmethod
    def tearDownClass(cls):
        engine = getattr(cls, "engine", None)
        if engine is not None:
            engine.dispose()

    def setUp(self):
        self.connection = self.engine.connect()
        self.outer_transaction = self.connection.begin()
        self.Session = sessionmaker(
            bind=self.connection,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )

        def override_get_db():
            session = self.Session()
            try:
                yield session
            finally:
                session.close()

        app.dependency_overrides[get_db] = override_get_db
        configured_api_key = os.getenv("O2C_API_KEY")
        headers = {"X-API-Key": configured_api_key} if configured_api_key else {}
        self.client = TestClient(app, headers=headers)

    def tearDown(self):
        try:
            self.client.close()
        finally:
            try:
                app.dependency_overrides.pop(get_db, None)
            finally:
                try:
                    if self.outer_transaction.is_active:
                        self.outer_transaction.rollback()
                finally:
                    self.connection.close()

    @staticmethod
    def new_customer_payload():
        suffix = uuid4().hex
        return {
            "name": f"PostgreSQL Integration {suffix}",
            "country": "IN",
            "email": f"o2c-integration-{suffix}@example.test",
            "credit_limit": "25000.00",
            "payment_terms": "Net_30",
        }

    def create_customer(self):
        response = self.client.post("/customers/", json=self.new_customer_payload())
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def create_invoice(self, customer_id, amount):
        today = date.today()
        order_response = self.client.post(
            "/orders/",
            json={
                "customer_id": customer_id,
                "order_date": today.isoformat(),
                "order_amount": str(amount),
                "order_status": "PROCESSED",
            },
        )
        self.assertEqual(order_response.status_code, 200, order_response.text)
        order_id = order_response.json()["order_id"]

        invoice_number = f"PG-INT-{uuid4().hex}"
        invoice_response = self.client.post(
            "/invoices/",
            json={
                "customer_id": customer_id,
                "invoice_number": invoice_number,
                "sales_order_id": order_id,
                "invoice_date": today.isoformat(),
                "due_date": (today + timedelta(days=30)).isoformat(),
                "invoice_amount": str(amount),
                "invoice_status": "OPEN",
            },
        )
        self.assertEqual(invoice_response.status_code, 200, invoice_response.text)
        return invoice_response.json()

    def create_payment(self, customer_id, amount, status="COMPLETED"):
        payment_reference = f"PG-INT-{uuid4().hex}"
        response = self.client.post(
            "/payments/",
            json={
                "payment_reference": payment_reference,
                "customer_id": customer_id,
                "payment_date": date.today().isoformat(),
                "payment_amount": str(amount),
                "payment_method": "BANK_TRANSFER",
                "payment_status": status,
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def allocate(self, payment_id, invoice_id, amount):
        return self.client.post(
            "/payment_allocations/",
            json={
                "payment_id": payment_id,
                "invoice_id": invoice_id,
                "allocated_amount": str(amount),
            },
        )

    def test_customer_can_be_created_and_retrieved_via_api(self):
        payload = self.new_customer_payload()

        created = self.client.post("/customers/", json=payload)
        self.assertEqual(created.status_code, 200, created.text)
        customer_id = created.json()["id"]
        self.assertEqual(created.json()["email"], payload["email"])

        retrieved = self.client.get(f"/customers/{customer_id}")
        self.assertEqual(retrieved.status_code, 200, retrieved.text)
        self.assertEqual(retrieved.json()["id"], customer_id)
        self.assertEqual(retrieved.json()["name"], payload["name"])

    def test_customer_order_invoice_workflow_via_api(self):
        customer_payload = self.new_customer_payload()
        customer_response = self.client.post("/customers/", json=customer_payload)
        self.assertEqual(customer_response.status_code, 200, customer_response.text)
        customer_id = customer_response.json()["id"]

        order_amount = Decimal("1845.50")
        order_date = date.today()
        order_response = self.client.post(
            "/orders/",
            json={
                "customer_id": customer_id,
                "order_date": order_date.isoformat(),
                "order_amount": str(order_amount),
                "order_status": "PROCESSED",
            },
        )
        self.assertEqual(order_response.status_code, 200, order_response.text)
        order_id = order_response.json()["order_id"]

        retrieved_order = self.client.get(f"/orders/{order_id}")
        self.assertEqual(retrieved_order.status_code, 200, retrieved_order.text)
        self.assertEqual(retrieved_order.json()["order_id"], order_id)
        self.assertEqual(retrieved_order.json()["customer_id"], customer_id)
        self.assertEqual(Decimal(retrieved_order.json()["order_amount"]), order_amount)

        invoice_amount = Decimal("1250.50")
        invoice_date = date.today()
        invoice_number = f"PG-INT-{uuid4().hex}"
        invoice_response = self.client.post(
            "/invoices/",
            json={
                "customer_id": customer_id,
                "invoice_number": invoice_number,
                "sales_order_id": order_id,
                "invoice_date": invoice_date.isoformat(),
                "due_date": (invoice_date + timedelta(days=30)).isoformat(),
                "invoice_amount": str(invoice_amount),
                "invoice_status": "OPEN",
            },
        )
        self.assertEqual(invoice_response.status_code, 200, invoice_response.text)
        invoice_id = invoice_response.json()["invoice_id"]

        retrieved_invoice = self.client.get(f"/invoices/{invoice_id}")
        self.assertEqual(retrieved_invoice.status_code, 200, retrieved_invoice.text)
        invoice_data = retrieved_invoice.json()
        self.assertEqual(invoice_data["customer_id"], customer_id)
        self.assertEqual(invoice_data["sales_order_id"], order_id)
        self.assertEqual(invoice_data["invoice_number"], invoice_number)
        self.assertEqual(Decimal(invoice_data["invoice_amount"]), invoice_amount)
        self.assertEqual(invoice_data["invoice_status"], "OPEN")

    def test_payment_can_be_created_and_retrieved_via_api(self):
        customer = self.create_customer()
        payment_amount = Decimal("725.40")
        payment = self.create_payment(customer["id"], payment_amount)

        retrieved = self.client.get(f"/payments/{payment['payment_id']}")
        self.assertEqual(retrieved.status_code, 200, retrieved.text)
        payment_data = retrieved.json()
        self.assertEqual(payment_data["payment_id"], payment["payment_id"])
        self.assertEqual(payment_data["payment_reference"], payment["payment_reference"])
        self.assertEqual(payment_data["customer_id"], customer["id"])
        self.assertEqual(Decimal(payment_data["payment_amount"]), payment_amount)
        self.assertEqual(payment_data["payment_status"], "COMPLETED")

    def test_manual_allocations_update_invoice_from_partial_to_paid(self):
        customer = self.create_customer()
        invoice_amount = Decimal("100.00")
        invoice = self.create_invoice(customer["id"], invoice_amount)

        first_payment = self.create_payment(customer["id"], Decimal("40.00"))
        first_allocation = self.allocate(
            first_payment["payment_id"], invoice["invoice_id"], Decimal("40.00")
        )
        self.assertEqual(first_allocation.status_code, 200, first_allocation.text)
        allocation_id = first_allocation.json()["allocation_id"]

        retrieved_allocation = self.client.get(f"/payment_allocations/{allocation_id}")
        self.assertEqual(retrieved_allocation.status_code, 200, retrieved_allocation.text)
        allocation_data = retrieved_allocation.json()
        self.assertEqual(allocation_data["payment_id"], first_payment["payment_id"])
        self.assertEqual(allocation_data["invoice_id"], invoice["invoice_id"])
        self.assertEqual(Decimal(allocation_data["allocated_amount"]), Decimal("40.00"))

        partial_invoice = self.client.get(f"/invoices/{invoice['invoice_id']}")
        self.assertEqual(partial_invoice.status_code, 200, partial_invoice.text)
        self.assertEqual(partial_invoice.json()["invoice_status"], "PARTIALLY_PAID")

        second_payment = self.create_payment(customer["id"], Decimal("60.00"))
        second_allocation = self.allocate(
            second_payment["payment_id"], invoice["invoice_id"], Decimal("60.00")
        )
        self.assertEqual(second_allocation.status_code, 200, second_allocation.text)

        paid_invoice = self.client.get(f"/invoices/{invoice['invoice_id']}")
        self.assertEqual(paid_invoice.status_code, 200, paid_invoice.text)
        self.assertEqual(paid_invoice.json()["invoice_status"], "PAID")

    def test_pending_and_failed_payments_cannot_be_allocated(self):
        customer = self.create_customer()
        invoice = self.create_invoice(customer["id"], Decimal("100.00"))

        for status in ("PENDING", "FAILED"):
            with self.subTest(payment_status=status):
                payment = self.create_payment(customer["id"], Decimal("25.00"), status)
                response = self.allocate(
                    payment["payment_id"], invoice["invoice_id"], Decimal("10.00")
                )
                self.assertEqual(response.status_code, 400, response.text)
                self.assertIn("Only completed payments can be allocated", response.json()["detail"])

    def test_allocation_cannot_exceed_payment_remaining_amount(self):
        customer = self.create_customer()
        first_invoice = self.create_invoice(customer["id"], Decimal("80.00"))
        target_invoice = self.create_invoice(customer["id"], Decimal("100.00"))
        payment = self.create_payment(customer["id"], Decimal("100.00"))

        existing_allocation = self.allocate(
            payment["payment_id"], first_invoice["invoice_id"], Decimal("80.00")
        )
        self.assertEqual(existing_allocation.status_code, 200, existing_allocation.text)

        response = self.allocate(
            payment["payment_id"], target_invoice["invoice_id"], Decimal("30.00")
        )
        self.assertEqual(response.status_code, 400, response.text)
        self.assertIn("exceeds the remaining payment amount", response.json()["detail"])

    def test_allocation_cannot_exceed_invoice_outstanding_balance(self):
        customer = self.create_customer()
        invoice = self.create_invoice(customer["id"], Decimal("100.00"))
        first_payment = self.create_payment(customer["id"], Decimal("75.00"))
        existing_allocation = self.allocate(
            first_payment["payment_id"], invoice["invoice_id"], Decimal("75.00")
        )
        self.assertEqual(existing_allocation.status_code, 200, existing_allocation.text)
        second_payment = self.create_payment(customer["id"], Decimal("100.00"))

        response = self.allocate(
            second_payment["payment_id"], invoice["invoice_id"], Decimal("30.00")
        )
        self.assertEqual(response.status_code, 400, response.text)
        self.assertIn("outstanding balance of the invoice", response.json()["detail"])

    def test_payment_cannot_be_allocated_to_another_customers_invoice(self):
        payment_customer = self.create_customer()
        invoice_customer = self.create_customer()
        invoice = self.create_invoice(invoice_customer["id"], Decimal("100.00"))
        payment = self.create_payment(payment_customer["id"], Decimal("50.00"))

        response = self.allocate(payment["payment_id"], invoice["invoice_id"], Decimal("10.00"))
        self.assertEqual(response.status_code, 400, response.text)
        self.assertEqual(
            response.json()["detail"],
            "Payment and invoice belong to different customers",
        )

    def test_api_write_is_rolled_back_after_test(self):
        payload = self.new_customer_payload()
        response = self.client.post("/customers/", json=payload)
        self.assertEqual(response.status_code, 200, response.text)

        # This test explicitly demonstrates that even an endpoint db.commit()
        # only releases its savepoint; the outer transaction is still reversible.
        self.outer_transaction.rollback()
        self.assertFalse(self.outer_transaction.is_active)

        with self.engine.connect() as verification_connection:
            persisted_count = verification_connection.execute(
                text('SELECT COUNT(*) FROM "Customers" WHERE email = :email'),
                {"email": payload["email"]},
            ).scalar_one()
        self.assertEqual(persisted_count, 0)
