from fastapi import FastAPI,HTTPException
from pydantic import BaseModel



customer_data=[]
next_id = 1

class Customer(BaseModel):
    id:int
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
def create_customer(customer: Customer):
    # Here you would typically add logic to save the customer to a database
    global next_id
    customer.id = next_id
    next_id+=1
    customer_data.append(customer)
    return customer

@app.get("/customers/{customer_id}")
def get_customers(customer_id:int):
    # Here you would typically retrieve customers from a database
    for customer in customer_data:
        if customer.id == customer_id:
            return customer
    raise HTTPException(status_code=404, detail="Customer not found")
