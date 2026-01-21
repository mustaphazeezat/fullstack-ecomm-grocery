from fastapi import APIRouter, Depends,HTTPException,Query, BackgroundTasks, Request
from sqlalchemy.orm import Session, relationship
from sqlalchemy import  Column, Integer, String, DateTime, ForeignKey, Numeric
from pydantic import BaseModel, Field
from typing import List
from database import get_db, Base, engine
import math
import os
import stripe
from decimal import Decimal
from .users import get_current_active_user, User
from .products import Product
from datetime import datetime, timezone
from helpers.email import order_notification_email



class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    total_price = Column(Numeric(10, 2), nullable=False)
    status = Column(String, default="pending")
    shipping_address = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))

    user = relationship("User", back_populates="orders")
    order_items = relationship("OrderItem", back_populates="order")

class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("orders.id"))
    product_id = Column(Integer, ForeignKey("products.product_id"))
    quantity = Column(Integer, nullable=False)
    price_at_purchase = Column(Numeric(10, 2), nullable=False) 
    order = relationship("Order", back_populates="order_items")

    

Base.metadata.create_all(engine)

class OrderItemBase(BaseModel):
    product_id: int
    quantity: int = Field(..., gt=0) 
    price_at_purchase: Decimal

class OrderItemResponse(OrderItemBase):
    id: int
    class Config:
        from_attributes = True

#Pydantic Models
class OrderBase(BaseModel):
    shipping_address: str
    total_price: Decimal = Field(..., ge=0, decimal_places=2)
    status: str = "pending"

class OrderCreate(OrderBase):
    items: List[OrderItemBase]

class OrderResponse(OrderBase):
    id: int
    user_id: int
    created_at: datetime
    order_items: List[OrderItemResponse] = []

    class Config:
        from_attributes = True

class PaginatedOrderResponse(BaseModel):
    total_pages: int
    items_per_page: int
    page: int
    data: List[OrderResponse] = []

    class Config:
        from_attributes = True

router = APIRouter(
    prefix="/orders",
    tags=["Orders"]
)

@router.get("/", response_model=PaginatedOrderResponse)
def get_all_orders(current_user: User = Depends(get_current_active_user), db:Session = Depends(get_db), page: int = Query(default=1, ge=1), order_per_page: int = Query(default=5, ge=1, le=100)):

    user_orders_query = db.query(Order).filter(Order.user_id == current_user.user_id)
    total_count = user_orders_query.count()
    total_pages = math.ceil(total_count / order_per_page) if total_count > 0 else 1

    if page > total_pages and total_count > 0:
        raise HTTPException(status_code=404, detail="Page does not exist")

    #Calculate offset and fetch data
    calculated_offset = (page - 1) * order_per_page
    orders = user_orders_query.offset(calculated_offset).limit(order_per_page).all()

    return {
        "total_pages": total_pages,
        "items_per_page": order_per_page,
        "page": page,
        "data": orders
    }

@router.post("/create-order", response_model=OrderResponse)
def check_out(order:OrderCreate, background_tasks: BackgroundTasks,current_user: User = Depends(get_current_active_user), db: Session= Depends(get_db)):
    total_price = 0
    order_items_to_create_email = []
    order_items_to_create = []

    for item in order.items:
        product = db.query(Product).filter(Product.product_id == item.product_id).first()
        if not product:
            raise HTTPException(status_code=404, detail=f"Product {item.product_id} not found")
        
        item_total = product.price * item.quantity
        total_price += item_total

        new_item = OrderItem(
            product_id=product.product_id,
            quantity=item.quantity,
            price_at_purchase=product.price 
        )
        
        order_items_to_create.append(new_item)

        new_item.temp_product_name = product.name
        new_item.temp_product_image = product.image_url
        order_items_to_create_email.append(new_item)
   
    new_order = Order(
        user_id = current_user.user_id,
        shipping_address = order.shipping_address,
        total_price = total_price,
        status = "pending",
        order_items = order_items_to_create
    )
    db.add(new_order)
    db.commit()
    db.refresh(new_order)
    
    background_tasks.add_task(
       order_notification_email, 
        current_user.email, 
        current_user.name, 
        Order(
            user_id = current_user.user_id,
            shipping_address = order.shipping_address,
            total_price = total_price,
            status = "pending",
            order_items = order_items_to_create_email
        )
    )
    return  new_order


@router.delete("/cancel-order", response_model=PaginatedOrderResponse)
def cancel_order(current_user: User = Depends(get_current_active_user), db:Session = Depends(get_db)):

    pass

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
STRIPE_SUCCESS_URL=os.getenv("STRIPE_SUCCESS_URL")
STRIPE_CANCEL_URL=os.getenv("STRIPE_CANCEL_URL")

@router.post("/create-checkout-session")
def create_checkout_session(order_id: int,current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    order = db.query(Order).filter(Order.id == order_id).first()
    if order.user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Not authorized to pay for this order")
    try:
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            customer_email=current_user.email,
            line_items=[{
                'price_data': {
                    'currency': 'usd',
                    'product_data': {
                        'name': f"Order #{order.id}",
                    },
                    'unit_amount': int(order.total_price * 100), 
                },
                'quantity': 1,
            }],
            mode='payment',
            success_url='{STRIPE_SUCCESS_URL}?session_id={CHECKOUT_SESSION_ID}',
            cancel_url='https://your-site.com/cancel',
            client_reference_id=str(order.id)
        )
        return {"checkout_url": checkout_session.url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")

@router.post("/webhook")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail="Invalid signature")

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        order_id = session.get("client_reference_id")

        if order_id:
            update_order_status(order_id, db)
    return {"status": "success"}

def update_order_status(order_id: int, db: Session):
    order = db.query(Order).filter(Order.id == order_id).first()
    if order:
        order.status = "paid"
        db.commit()
   




