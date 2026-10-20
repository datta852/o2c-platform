from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db, CustomerDB, SalesOrderDB
from schemas import SalesOrderCreate, SalesOrderResponse


router = APIRouter(
    prefix="/orders",
    tags=["Sales Orders"]
)

@router.post("/",response_model=SalesOrderResponse)
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

@router.get("/",response_model=list[SalesOrderResponse])
def get_sales_orders(db:Session=Depends(get_db)):
    # Here you would typically retrieve sales orders from a database
    return db.query(SalesOrderDB).all()

@router.get("/{order_id}",response_model=SalesOrderResponse)
def get_sales_order(order_id:int,db:Session=Depends(get_db)):
    # Here you would typically retrieve sales orders from a database
    db_order=db.query(SalesOrderDB).filter(SalesOrderDB.order_id==order_id).first()

    if not db_order:
        raise HTTPException(
            status_code=404,
            detail="Sales order not found")

    return db_order


@router.delete("/{order_id}")
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

@router.put("/{order_id}",response_model=SalesOrderResponse)
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