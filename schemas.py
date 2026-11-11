from enum import Enum
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator

Money = Annotated[Decimal, Field(max_digits=15, decimal_places=2)]
NonNegativeMoney = Annotated[Money, Field(ge=0)]
PositiveMoney = Annotated[Money, Field(gt=0)]

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

class ReconciliationStatus(str,Enum):
    unmatched="UNMATCHED"
    partially_reconciled="PARTIALLY_RECONCILED"
    reconciled="RECONCILED"
    exception="EXCEPTION"

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
    credit_limit:NonNegativeMoney
    payment_terms:PaymentTerms

class CustomerResponse(BaseModel):
    id:int
    name:str
    country:str
    email:str
    credit_limit:NonNegativeMoney
    payment_terms:PaymentTerms

    model_config=ConfigDict(from_attributes=True)

class SalesOrderCreate(BaseModel):
    customer_id:int
    order_date:date
    order_amount:PositiveMoney

class SalesOrderUpdate(SalesOrderCreate):
    order_status:order_Status

class SalesOrderResponse(BaseModel):
    order_id:int
    customer_id:int
    order_date:date
    order_amount:PositiveMoney
    order_status:order_Status

    model_config=ConfigDict(from_attributes=True)

class InvoiceCreate(BaseModel):
    customer_id:int
    invoice_number:str=Field(min_length=1)
    sales_order_id:int
    invoice_date:date
    due_date:date
    invoice_amount:PositiveMoney
    invoice_status:InvoiceStatus

    @model_validator(mode="after")
    def due_date_not_before_invoice_date(self):
        if self.due_date < self.invoice_date:
            raise ValueError("due_date cannot precede invoice_date")
        return self

class InvoiceResponse(BaseModel):

    invoice_id:int
    customer_id:int
    invoice_number:str
    sales_order_id:int
    invoice_date:date
    due_date:date
    invoice_amount:PositiveMoney
    invoice_status:InvoiceStatus

    model_config=ConfigDict(from_attributes=True)


class PaymentCreate(BaseModel):
    payment_reference:str=Field(min_length=1)
    customer_id:int
    payment_date:date
    payment_amount:PositiveMoney
    payment_method:PaymentMethod
    payment_status:PaymentStatus

class PaymentUpdate(BaseModel):
    payment_date:date
    payment_amount:PositiveMoney
    payment_method:PaymentMethod
    payment_status:PaymentStatus


class PaymentResponse(BaseModel):
    payment_id:int
    payment_reference:str
    customer_id:int
    payment_date:date
    payment_amount:PositiveMoney
    payment_method:PaymentMethod
    payment_status:PaymentStatus

    model_config=ConfigDict(from_attributes=True)

class PaymentAllocationCreate(BaseModel):
    payment_id:int
    invoice_id:int
    allocated_amount:PositiveMoney

class PaymentAllocationUpdate(BaseModel):
    allocated_amount:PositiveMoney

class PaymentAllocationResponse(BaseModel):
    allocation_id:int
    payment_id:int
    invoice_id:int
    allocated_amount:PositiveMoney

    model_config=ConfigDict(from_attributes=True)

class ReconciliationAllocation(BaseModel):
    invoice_id:int=Field(gt=0)
    allocated_amount:PositiveMoney

class PaymentReconciliationRequest(BaseModel):
    allocations:list[ReconciliationAllocation]=Field(default_factory=list)

class PaymentReconciliationResponse(BaseModel):
    payment_id:int
    status:ReconciliationStatus
    allocated_amount:Decimal
    unapplied_amount:Decimal
    exception_reason:str|None=None
    reconciled_at:datetime|None=None

class PaymentReconciliationAuditResponse(BaseModel):
    audit_id:int
    payment_id:int
    action:str
    details:str
    occurred_at:datetime

    model_config=ConfigDict(from_attributes=True)

class CollectionActionType(str,Enum):
    email_reminder="EMAIL_REMINDER"
    phone_call="PHONE_CALL"
    account_review="ACCOUNT_REVIEW"

class CollectionActionStatus(str,Enum):
    scheduled="SCHEDULED"
    completed="COMPLETED"
    failed="FAILED"

class DunningRuleCreate(BaseModel):
    name:str=Field(min_length=1,max_length=100)
    days_overdue:int=Field(ge=0)
    action_type:CollectionActionType
    enabled:bool=True

class DunningRuleUpdate(BaseModel):
    name:str=Field(min_length=1,max_length=100)
    days_overdue:int=Field(ge=0)
    action_type:CollectionActionType
    enabled:bool

class DunningRuleResponse(BaseModel):
    rule_id:int
    name:str
    days_overdue:int
    action_type:CollectionActionType
    enabled:bool

    model_config=ConfigDict(from_attributes=True)

class CollectionActionResponse(BaseModel):
    action_id:int
    invoice_id:int
    rule_id:int
    action_type:CollectionActionType
    status:CollectionActionStatus
    scheduled_date:date
    completed_at:datetime|None
    outcome:str|None

    model_config=ConfigDict(from_attributes=True)

class CollectionActionOutcome(BaseModel):
    status:CollectionActionStatus
    outcome:str|None=Field(default=None,max_length=1000)

class ReceivableResponse(BaseModel):
    invoice_id:int
    invoice_number:str
    customer_id:int
    due_date:date
    invoice_amount:Money
    allocated_amount:Money
    outstanding_amount:Money
    days_overdue:int

class ReceivablesSummary(BaseModel):
    outstanding_amount:Money
    overdue_amount:Money
    outstanding_invoice_count:int
    overdue_invoice_count:int
