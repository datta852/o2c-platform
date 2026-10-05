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


def get_db():
    db=SessionLocal()
    try:
        yield db
    finally:
        db.close()

Base.metadata.create_all(bind=engine)