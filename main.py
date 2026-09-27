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

@app.delete("/customers/{customer_id}")
def delete_customer(customer_id:int):
    # Here you would typically delete customers from a database
    for customer in customer_data:
        if customer.id == customer_id:
            customer_data.remove(customer)
            return {"message": "Customer deleted successfully"}
    raise HTTPException(status_code=404, detail="Customer not found")

@app.put("/customers/{customer_id}")
def update_customer(customer_id:int,customer:Customer):
    # Here you would typically update customers in a database
    for existing_customer in customer_data:
        if existing_customer.id == customer_id:
            existing_customer.name=customer.name
            existing_customer.email=customer.email
            existing_customer.country=customer.country
            return {"message": "Customer updated successfully","customer":existing_customer}
    raise HTTPException(status_code=404,detail="Customer not found")