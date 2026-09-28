from fastapi import FastAPI,HTTPException,Depends
from pydantic import BaseModel
from database import get_db,CustomerDB
from sqlalchemy.orm import Session

customer_data=[]
next_id = 1

class Customer(BaseModel):
    name:str
    country:str
    email:str

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

@app.post("/customers")
def create_customer(customer: Customer,db:Session=Depends(get_db)): #FastAPI Dependency Injection to get the database session.
    # Here you would typically add logic to save the customer to a database
    db_customer = CustomerDB(
        name=customer.name,
        country=customer.country,
        email=customer.email
    )

    db.add(db_customer)
    db.commit()
    db.refresh(db_customer)

    return db_customer

@app.get("/customers/{customer_id}")
def get_customer(customer_id:int,db:Session=Depends(get_db)):
    # Here you would typically retrieve customers from a database

    customer=db.query(CustomerDB).filter(CustomerDB.id == customer_id).first()

    if not customer:
        raise HTTPException(
            status_code=404,
            detail="Customer not found")

    return customer
    

@app.delete("/customers/{customer_id}")
def delete_customer(customer_id:int):
    # Here you would typically delete customers from a database
    for customer in customer_data:
        if customer.id == customer_id:
            customer_data.remove(customer)
            return {"message": "Customer deleted successfully"}
    raise HTTPException(status_code=404, detail="Customer not found")

@app.put("/customers/{customer_id}")
def update_customer(customer_id:int,customer:Customer,db:Session=Depends(get_db)):
    # Here you would typically update customers in a database
    customer=db.query(CustomerDB).filter(CustomerDB.id==customer_id).first()

    #Continue with the update logic

    # db.commit()

    # if not customer:
    #     raise HTTPException(status_code=404,detail="Customer not found")

    return customer