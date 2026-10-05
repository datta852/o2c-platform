from enum import Enum, Enum
from fastapi import FastAPI,HTTPException,Depends
from pydantic import BaseModel,ConfigDict,Field
from database import get_db,CustomerDB,SalesOrderDB
from sqlalchemy.orm import Session
from datetime import date

customer_data=[]
next_id = 1


class PaymentTerms(str,Enum):#Enum class allows you to choose from a set of predefined values for the payment terms.
    net_15="Net_15"
    net_30="Net_30"
    net_45="Net_45"
    net_60="Net_60"
    net_90="Net_90"

class order_Status(str,Enum):
    #Enum class allows you to choose from a set of predefined values for the order status.
    open="OPEN"
    awaiting_approval="AWAITING_APPROVAL"
    processed="PROCESSED"
    blocked="BLOCKED"
    closed="CLOSED"
    cancelled="CANCELLED"

class CustomerCreate(BaseModel):
    name:str
    country:str
    email:str
    credit_limit:float=Field(ge=0,description="Credit limit must be a non-negative value")#Field with ge=0 ensures that the credit limit is a non-negative value.
    payment_terms:PaymentTerms

class CustomerResponse(BaseModel):
    id:int
    name:str
    country:str
    email:str
    credit_limit:float=Field(ge=0,description="Credit limit must be a non-negative value")#Field with ge=0 ensures that the credit limit is a non-negative value.
    payment_terms:PaymentTerms

    model_config=ConfigDict(from_attributes=True)

class SalesOrderCreate(BaseModel):
    customer_id:int
    order_date:date
    order_amount:float=Field(ge=0,description="Order amount must be a non-negative value")#Field with ge=0 ensures that the order amount is a non-negative value.
    order_status:order_Status

class SalesOrderResponse(BaseModel):
    order_id:int
    customer_id:int
    order_date:date
    order_amount:float=Field(ge=0,description="Order amount must be a non-negative value")#Field with ge=0 ensures that the order amount is a non-negative value.
    order_status:order_Status

    model_config=ConfigDict(from_attributes=True)

app = FastAPI()


@app.get("/")
def root():
    return {"Hello":"World"}

@app.get("/health")
def health_check():
    return {"status":"ok"}

@app.get("/about")
def about():
    return {
        "project":"O2C application platform",
        "version":"1.0.0",
    }

@app.post("/customers",response_model=CustomerResponse)
def create_customer(customer: CustomerCreate,db:Session=Depends(get_db)): #FastAPI Dependency Injection to get the database session.
    # Here you would typically add logic to save the customer to a database
    db_customer = CustomerDB(
        name=customer.name,
        country=customer.country,
        email=customer.email,
        credit_limit=customer.credit_limit,
        payment_terms=customer.payment_terms
    )

    db.add(db_customer)
    db.commit()
    db.refresh(db_customer)

    return db_customer

@app.post("/orders",response_model=SalesOrderResponse)
def create_sales_orders(order:SalesOrderCreate,db:Session=Depends(get_db)):
    
    customer=db.query(CustomerDB).filter(CustomerDB.id==order.customer_id).first()

    if not customer:
                raise HTTPException(
                    status_code=404,
                    detail="Customer not found")

    db_order=SalesOrderDB(
        customer_id=order.customer_id,
        order_date=order.order_date,
        order_amount=order.order_amount,
        order_status=order.order_status
    )

    db.add(db_order)
    db.commit()
    db.refresh(db_order)

    return db_order


@app.get("/customers",response_model=list[CustomerResponse])
def get_customers(db:Session=Depends(get_db)):
    # Here you would typically retrieve customers from a database
    return db.query(CustomerDB).all()

@app.get("/customers/{customer_id}",response_model=CustomerResponse)
def get_customer(customer_id:int,db:Session=Depends(get_db)):
    # Here you would typically retrieve customers from a database

    customer=db.query(CustomerDB).filter(CustomerDB.id == customer_id).first()

    if not customer:
        raise HTTPException(
            status_code=404,
            detail="Customer not found")

    return customer


@app.get("/orders",response_model=list[SalesOrderResponse])
def get_sales_orders(db:Session=Depends(get_db)):
    # Here you would typically retrieve sales orders from a database
    return db.query(SalesOrderDB).all()

@app.get("/orders/{order_id}",response_model=SalesOrderResponse)
def get_sales_order(order_id:int,db:Session=Depends(get_db)):
    # Here you would typically retrieve sales orders from a database
    db_order=db.query(SalesOrderDB).filter(SalesOrderDB.order_id==order_id).first()

    if not db_order:
        raise HTTPException(
            status_code=404,
            detail="Sales order not found")

    return db_order

@app.delete("/customers/{customer_id}")
def delete_customer(customer_id:int,db:Session=Depends(get_db)):
    # Here you would typically delete customers from a database

    #Find the customer in the database
    customer_db=db.query(CustomerDB).filter(CustomerDB.id==customer_id).first()

    #Check if the customer exists
    if not customer_db:
        raise HTTPException(status_code=404, detail="Customer not found")

    #Delete the customer from the database
    db.delete(customer_db)

    #Save changes to the database
    db.commit()

    #Return the result after deletion
    return {"message": f"Customer with id {customer_id} has been deleted successfully."}

@app.put("/customers/{customer_id}",response_model=CustomerResponse)
def update_customer(customer_id:int,customer:CustomerCreate,db:Session=Depends(get_db)):
    # Here you would typically update customers in a database

    #Find existing customer
    customer_db=db.query(CustomerDB).filter(CustomerDB.id==customer_id).first()

    #Check if it exists
    if not customer_db:
        raise HTTPException(status_code=404,detail="Customer not found")

    #Update the existing database object
    customer_db.name=customer.name
    customer_db.country=customer.country
    customer_db.email=customer.email

    #Save changes
    db.commit()

    #Return the updated customer
    return customer_db