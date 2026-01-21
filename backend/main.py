from fastapi import FastAPI
from routers import products, users, orders

app = FastAPI(title="Shopper grocery Backend")

# Add the separated logic
app.include_router(products.router)
app.include_router(users.router)
app.include_router(orders.router)

@app.get("/")
def read_root():
    return {"Message": "Your Grocery API"}

