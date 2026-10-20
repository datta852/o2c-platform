from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db, CustomerDB
from schemas import CustomerCreate, CustomerResponse

router = APIRouter(
    prefix="/customers",
    tags=["Customers"]
)


@router.post("/", response_model=CustomerResponse)
def create_customer(
    customer: CustomerCreate,
    db: Session = Depends(get_db)
):
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


@router.get("/", response_model=list[CustomerResponse])
def get_customers(db: Session = Depends(get_db)):
    return db.query(CustomerDB).all()


@router.get("/{customer_id}", response_model=CustomerResponse)
def get_customer(
    customer_id: int,
    db: Session = Depends(get_db)
):
    customer = db.query(CustomerDB).filter(
        CustomerDB.id == customer_id
    ).first()

    if not customer:
        raise HTTPException(
            status_code=404,
            detail="Customer not found"
        )

    return customer

@router.delete("/{customer_id}")
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

@router.put("/{customer_id}",response_model=CustomerResponse)
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