from fastapi import FastAPI

from routers.customers import router as customer_router
from routers.sales_orders import router as order_router
from routers.invoices import router as invoice_router
from routers.payments import router as payment_router
from routers.payment_allocations import router as payment_allocation_router


app = FastAPI()
app.include_router(customer_router)
app.include_router(order_router)
app.include_router(invoice_router)
app.include_router(payment_router)
app.include_router(payment_allocation_router)

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
