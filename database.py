import os

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, create_engine,Column,Integer,String,Numeric,ForeignKey,UniqueConstraint, event
from sqlalchemy.orm import declarative_base,sessionmaker

DATABASE_URL=os.getenv("DATABASE_URL", "sqlite:///./o2c.db")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine=create_engine(DATABASE_URL, connect_args=connect_args)

if DATABASE_URL.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def _enable_sqlite_foreign_keys(connection, _connection_record):
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
SessionLocal=sessionmaker(bind=engine)

Base=declarative_base()

class CustomerDB(Base):

    __tablename__="Customers"

    id=Column(Integer,primary_key=True,index=True)
    name=Column(String,nullable=False)
    country=Column(String,nullable=False)
    email=Column(String,nullable=False)
    credit_limit=Column(Numeric(15,2),default=0,nullable=False)
    payment_terms=Column(String,default="Net 30",nullable=False)
    __table_args__=(CheckConstraint("credit_limit >= 0",name="ck_customers_credit_limit_nonnegative"),)

class SalesOrderDB(Base):
    
    __tablename__="Salesorders"

    order_id=Column(Integer,primary_key=True,index=True)
    customer_id=Column(Integer,ForeignKey("Customers.id"),nullable=False)
    order_date=Column(Date,nullable=False)
    order_amount=Column(Numeric(15,2),nullable=False)
    order_status=Column(String,nullable=False)
    __table_args__=(CheckConstraint("order_amount > 0",name="ck_orders_amount_positive"),)

class InvoiceDB(Base):

    __tablename__="Invoices"

    invoice_id=Column(Integer,primary_key=True,index=True)
    invoice_number=Column(String,unique=True,nullable=False)
    customer_id=Column(Integer,ForeignKey("Customers.id"),nullable=False)
    sales_order_id=Column(Integer,ForeignKey("Salesorders.order_id"),nullable=False)
    invoice_date=Column(Date,nullable=False)
    due_date=Column(Date,nullable=False)
    invoice_amount=Column(Numeric(15,2),nullable=False)
    invoice_status=Column(String,nullable=False)
    __table_args__=(CheckConstraint("invoice_amount > 0",name="ck_invoices_amount_positive"),)

class PaymentDB(Base):
    
    __tablename__="Payments"

    payment_id=Column(Integer,primary_key=True,index=True)
    payment_reference=Column(String,unique=True,nullable=False)
    customer_id=Column(Integer,ForeignKey("Customers.id"),nullable=False)
    payment_date=Column(Date,nullable=False)
    payment_amount=Column(Numeric(15,2),nullable=False)
    payment_method=Column(String,nullable=False)
    payment_status=Column(String,nullable=False)
    __table_args__=(CheckConstraint("payment_amount > 0",name="ck_payments_amount_positive"),)

class PaymentAllocationDB(Base):

    __tablename__="PaymentAllocations"

    allocation_id=Column(Integer,primary_key=True,index=True)
    payment_id=Column(Integer,ForeignKey("Payments.payment_id"),nullable=False)
    invoice_id=Column(Integer,ForeignKey("Invoices.invoice_id"),nullable=False)
    allocated_amount=Column(Numeric(15,2),nullable=False)
    __table_args__=(
        CheckConstraint("allocated_amount > 0",name="ck_payment_allocations_amount_positive"),
        UniqueConstraint("payment_id","invoice_id",name="uq_payment_allocations_payment_invoice"),
    )

class PaymentReconciliationDB(Base):

    __tablename__="PaymentReconciliations"

    reconciliation_id=Column(Integer,primary_key=True,index=True)
    payment_id=Column(Integer,ForeignKey("Payments.payment_id"),unique=True,nullable=False)
    status=Column(String,nullable=False)
    exception_reason=Column(String,nullable=True)
    reconciled_at=Column(DateTime,nullable=True)

class PaymentReconciliationAuditDB(Base):

    __tablename__="PaymentReconciliationAudits"

    audit_id=Column(Integer,primary_key=True,index=True)
    payment_id=Column(Integer,ForeignKey("Payments.payment_id"),nullable=False)
    action=Column(String,nullable=False)
    details=Column(String,nullable=False)
    occurred_at=Column(DateTime,nullable=False)

class IdempotencyRecordDB(Base):

    __tablename__="IdempotencyRecords"

    idempotency_key=Column(String,primary_key=True)
    request_hash=Column(String,nullable=False)
    response_body=Column(String,nullable=False)
    payment_id=Column(Integer,ForeignKey("Payments.payment_id"),nullable=False)

class DunningRuleDB(Base):

    __tablename__="DunningRules"

    rule_id=Column(Integer,primary_key=True,index=True)
    name=Column(String,unique=True,nullable=False)
    days_overdue=Column(Integer,nullable=False)
    action_type=Column(String,nullable=False)
    enabled=Column(Boolean,nullable=False,default=True)
    __table_args__=(CheckConstraint("days_overdue >= 0",name="ck_dunning_rules_days_nonnegative"),)

class CollectionActionDB(Base):

    __tablename__="CollectionActions"

    action_id=Column(Integer,primary_key=True,index=True)
    invoice_id=Column(Integer,ForeignKey("Invoices.invoice_id"),nullable=False)
    rule_id=Column(Integer,ForeignKey("DunningRules.rule_id"),nullable=False)
    action_type=Column(String,nullable=False)
    status=Column(String,nullable=False)
    scheduled_date=Column(Date,nullable=False)
    completed_at=Column(DateTime,nullable=True)
    outcome=Column(String,nullable=True)
    __table_args__=(UniqueConstraint("invoice_id","rule_id",name="uq_collection_actions_invoice_rule"),)

def get_db():
    db=SessionLocal()
    try:
        yield db
    finally:
        db.close()
