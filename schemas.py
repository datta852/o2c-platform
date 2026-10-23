from enum import Enum
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

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

class PaymentAllocationCreate(BaseModel):
    payment_id:int
    invoice_id:int
    allocated_amount:Decimal=Field(gt=0,description="Allocated amount must be a positive value")

class PaymentAllocationUpdate(BaseModel):
    allocated_amount:Decimal=Field(gt=0,description="Allocated amount must be a positive value")

class PaymentAllocationResponse(BaseModel):
    allocation_id:int
    payment_id:int
    invoice_id:int
    allocated_amount:Decimal=Field(gt=0,description="Allocated amount must be a positive value")

    model_config=ConfigDict(from_attributes=True)
