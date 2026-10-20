from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db, CustomerDB, PaymentDB
from schemas import PaymentCreate, PaymentUpdate, PaymentResponse

router = APIRouter(
    prefix="/payments",
    tags=["Payments"]
)


@router.post("/",response_model=PaymentResponse)
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

@router.get("/",response_model=list[PaymentResponse])
def get_payments(db:Session=Depends(get_db)):
    # Here you would typically retrieve payments from a database
    return db.query(PaymentDB).all()

@router.get("/{payment_id}",response_model=PaymentResponse)
def get_payment(payment_id:int,db:Session=Depends(get_db)):

    db_payment=db.query(PaymentDB).filter(PaymentDB.payment_id==payment_id).first()

    if not db_payment:
        raise HTTPException(
            status_code=404,
            detail="Payment not found")

    return db_payment

@router.put("/{payment_id}",response_model=PaymentResponse)
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

@router.delete("/{payment_id}")
def delete_payment(payment_id:int,db:Session=Depends(get_db)):


    db_payment=db.query(PaymentDB).filter(PaymentDB.payment_id==payment_id).first()

    if not db_payment:
        raise HTTPException(
            status_code=404,
            detail="Payment not found")

    db.delete(db_payment)

    db.commit()

    return {"message": f"Payment with id {payment_id} has been deleted successfully."}