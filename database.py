from sqlalchemy import Date, create_engine,Column,Integer,String,Numeric,ForeignKey
from sqlalchemy.orm import declarative_base,sessionmaker

DATABASE_URL="sqlite:///./o2c.db"

engine=create_engine(DATABASE_URL)
SessionLocal=sessionmaker(bind=engine)

Base=declarative_base()

class CustomerDB(Base):

    __tablename__="Customers"

    id=Column(Integer,primary_key=True,index=True)
    name=Column(String)
    country=Column(String)
    email=Column(String)
    credit_limit=Column(Numeric(15,2),default=0)
    payment_terms=Column(String,default="Net 30")

class SalesOrderDB(Base):
    
    __tablename__="Salesorders"

    order_id=Column(Integer,primary_key=True,index=True)
    customer_id=Column(Integer,ForeignKey("Customers.id"))
    order_date=Column(Date)
    order_amount=Column(Numeric(15,2))
    order_status=Column(String)

class InvoiceDB(Base):

    __tablename__="Invoices"

    invoice_id=Column(Integer,primary_key=True,index=True)
    invoice_number=Column(String,unique=True)
    customer_id=Column(Integer,ForeignKey("Customers.id"))
    sales_order_id=Column(Integer,ForeignKey("Salesorders.order_id"))
    invoice_date=Column(Date)
    due_date=Column(Date)
    invoice_amount=Column(Numeric(15,2))
    invoice_status=Column(String)


def get_db():
    db=SessionLocal()
    try:
        yield db
    finally:
        db.close()

Base.metadata.create_all(bind=engine)