from enum import Enum, Enum
from fastapi import FastAPI,HTTPException,Depends
from pydantic import BaseModel,ConfigDict,Field
from database import get_db,CustomerDB
from sqlalchemy.orm import Session

customer_data=[]
next_id = 1


class PaymentTerms(str,Enum):#Enum class allows you to choose from a set of predefined values for the payment terms.
    net_15="Net_15"
    net_30="Net_30"
    net_45="Net_45"
    net_60="Net_60"
    net_90="Net_90"

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