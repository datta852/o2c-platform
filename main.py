from enum import Enum, Enum
from fastapi import FastAPI,HTTPException,Depends
from pydantic import BaseModel,ConfigDict,Field
from database import get_db,CustomerDB,SalesOrderDB,InvoiceDB,PaymentDB
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

class InvoiceStatus(str,Enum):
    open="OPEN"
    paid="PAID"
    partially_paid="PARTIALLY_PAID"
    overdue="OVERDUE"
    cancelled="CANCELLED"

class PaymentStatus(str,Enum):
    pending="PENDING"
    completed="COMPLETED"
    failed="FAILED"
    refunded="REFUNDED"
    cancelled="CANCELLED"

class PaymentMethod(str,Enum):
    credit_card="CREDIT_CARD"
    debit_card="DEBIT_CARD"
    bank_transfer="BANK_TRANSFER"
    cheque="CHEQUE"
    net_banking="NET_BANKING"
    payment_gateway="PAYMENT_GATEWAY"


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

class InvoiceCreate(BaseModel):
    customer_id:int
    invoice_number:str
    sales_order_id:int
    invoice_date:date
    due_date:date
    invoice_amount:float=Field(ge=0,description="Invoice amount must be a non-negative value")#Field with ge=0 ensures that the invoice amount is a non-negative value.
    invoice_status:InvoiceStatus

class InvoiceResponse(BaseModel):

    invoice_id:int
    customer_id:int
    invoice_number:str
    sales_order_id:int
    invoice_date:date
    due_date:date
    invoice_amount:float=Field(ge=0,description="Invoice amount must be a non-negative value")#Field with ge=0 ensures that the invoice amount is a non-negative value.
    invoice_status:InvoiceStatus

    model_config=ConfigDict(from_attributes=True)


class PaymentCreate(BaseModel):
    payment_reference:str
    customer_id:int
    payment_date:date
    payment_amount:float=Field(ge=0,description="Payment amount must be a non-negative value")
    payment_method:PaymentMethod
    payment_status:PaymentStatus

class PaymentUpdate(BaseModel):
    payment_date:date
    payment_amount:float=Field(ge=0,description="Payment amount must be a non-negative value")
    payment_method:PaymentMethod
    payment_status:PaymentStatus


class PaymentResponse(BaseModel):
    payment_id:int
    payment_reference:str
    customer_id:int
    payment_date:date
    payment_amount:float
    payment_method:PaymentMethod
    payment_status:PaymentStatus

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

@app.post("/invoices",response_model=InvoiceResponse)
def create_invoice(invoice:InvoiceCreate,db:Session=Depends(get_db)):

    customer=db.query(CustomerDB).filter(CustomerDB.id==invoice.customer_id).first()

    order=db.query(SalesOrderDB).filter(SalesOrderDB.order_id==invoice.sales_order_id).first()

    if not customer:
        raise HTTPException(
            status_code=404,
            detail="Customer not found")

    if not order:
            raise HTTPException(
                status_code=404, 
                detail="Sales order not found")

    db_invoice=InvoiceDB(
        customer_id=invoice.customer_id,
        invoice_number=invoice.invoice_number,
        sales_order_id=invoice.sales_order_id,
        invoice_date=invoice.invoice_date,
        due_date=invoice.due_date,
        invoice_amount=invoice.invoice_amount,
        invoice_status=invoice.invoice_status
    )
    
    db.add(db_invoice)
    db.commit()
    db.refresh(db_invoice)

    return db_invoice

@app.post("/payments",response_model=PaymentResponse)
def create_payments(payment:PaymentCreate,db:Session=Depends(get_db)):

    customer=db.query(CustomerDB).filter(CustomerDB.id==payment.customer_id).first()

    if not customer:
        raise HTTPException(
            status_code=404,
            detail="Customer not found")

    db_payment=PaymentDB(
        payment_reference=payment.payment_reference,
        customer_id=payment.customer_id,
        payment_date=payment.payment_date,
        payment_amount=payment.payment_amount,
        payment_method=payment.payment_method,
        payment_status=payment.payment_status
    )

    db.add(db_payment)
    db.commit()
    db.refresh(db_payment)

    return db_payment



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

@app.get("/invoices",response_model=list[InvoiceResponse])
def get_invoices(db:Session=Depends(get_db)):
    # Here you would typically retrieve invoices from a database
    return db.query(InvoiceDB).all()


@app.get("/invoices/{invoice_id}",response_model=InvoiceResponse)
def get_invoice(invoice_id:int,db:Session=Depends(get_db)):

    db_invoice=db.query(InvoiceDB).filter(InvoiceDB.invoice_id==invoice_id).first()

    if not db_invoice:
        raise HTTPException(
            status_code=404,
            detail="Invoice not found")

    return db_invoice

@app.get("/payments",response_model=list[PaymentResponse])
def get_payments(db:Session=Depends(get_db)):
    # Here you would typically retrieve payments from a database
    return db.query(PaymentDB).all()

@app.get("/payments/{payment_id}",response_model=PaymentResponse)
def get_payment(payment_id:int,db:Session=Depends(get_db)):

    db_payment=db.query(PaymentDB).filter(PaymentDB.payment_id==payment_id).first()

    if not db_payment:
        raise HTTPException(
            status_code=404,
            detail="Payment not found")

    return db_payment

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

@app.delete("/orders/{order_id}")
def delete_sales_order(order_id:int,db:Session=Depends(get_db)):

    # Here you would typically delete sales orders from a database

    #Find the sales order in the database
    db_order=db.query(SalesOrderDB).filter(SalesOrderDB.order_id==order_id).first()
    
    #Check if the sales order exists
    if not db_order:
        raise HTTPException(status_code=404,detail="Sales order not found")

    #Delete the sales order from the database
    db.delete(db_order)

    #Save changes to the database
    db.commit()

    #Return the result after deletion
    return {"message": f"Sales order with id {order_id} has been deleted successfully."}

@app.delete("/invoices/{invoice_id}")
def delete_invoice(invoice_id:int,db:Session=Depends(get_db)):

    # Here you would typically delete invoices from a database
    
    #Find the invoice in the database
    db_invoice=db.query(InvoiceDB).filter(InvoiceDB.invoice_id==invoice_id).first()

    #Check if the invoice exists
    if not db_invoice:
        raise HTTPException(
            status_code=404,
            detail="Invoice not found")

    #Delete the invoice from the database
    db.delete(db_invoice)

    #Save changes to the database
    db.commit()

    #Return the result after deletion
    return {"message": f"Invoice with id {invoice_id} has been deleted successfully."}

@app.delete("/payments/{payment_id}")
def delete_payment(payment_id:int,db:Session=Depends(get_db)):


    db_payment=db.query(PaymentDB).filter(PaymentDB.payment_id==payment_id).first()

    if not db_payment:
        raise HTTPException(
            status_code=404,
            detail="Payment not found")

    db.delete(db_payment)

    db.commit()

    return {"message": f"Payment with id {payment_id} has been deleted successfully."}

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

@app.put("/orders/{order_id}",response_model=SalesOrderResponse)
def update_sales_orders(order_id:int,order:SalesOrderCreate,db:Session=Depends(get_db)):

    # Here you would typically update sales orders in a database
    db_order=db.query(SalesOrderDB).filter(SalesOrderDB.order_id==order_id).first()

    #Check if the sales order exists
    if not db_order:
        raise HTTPException(status_code=404,detail="Sales order not found")

    #Update the existing database object
    db_order.customer_id=order.customer_id
    db_order.order_amount=order.order_amount
    db_order.order_date=order.order_date
    db_order.order_status=order.order_status

    #Save changes to the database
    db.commit()

    #Return the updated sales order
    return db_order

@app.put("/invoices/{invoice_id}",response_model=InvoiceResponse)
def update_invoice(invoice_id:int,invoice:InvoiceCreate,db:Session=Depends(get_db)):

    db_invoice=db.query(InvoiceDB).filter(InvoiceDB.invoice_id==invoice_id).first()

    if not db_invoice:
        raise HTTPException(status_code=404,detail="Invoice not found")

    db_invoice.invoice_date=invoice.invoice_date
    db_invoice.due_date=invoice.due_date
    db_invoice.invoice_amount=invoice.invoice_amount
    db_invoice.invoice_status=invoice.invoice_status


    db.commit()

    return db_invoice

@app.put("/payments/{payment_id}",response_model=PaymentResponse)
def update_payment(payment_id:int,payment:PaymentUpdate,db:Session=Depends(get_db)):

    db_payment=db.query(PaymentDB).filter(PaymentDB.payment_id==payment_id).first()

    if not db_payment:
        raise HTTPException(status_code=404,detail="Payment not found")

    db_payment.payment_date=payment.payment_date
    db_payment.payment_amount=payment.payment_amount
    db_payment.payment_method=payment.payment_method
    db_payment.payment_status=payment.payment_status

    db.commit()

    return db_payment
