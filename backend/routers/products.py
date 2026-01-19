from fastapi import APIRouter, Depends,HTTPException,Query
from sqlalchemy.orm import Session
from sqlalchemy import Column, Integer, String, Numeric, or_
from pydantic import BaseModel
from typing import Optional, List
from database import get_db, Base, engine
import math


class Product(Base):
    __tablename__ = "products"
    product_id = Column(Integer, primary_key=True, unique=True, nullable=False)
    product_name = Column(String, nullable=False)
    name = Column(String, nullable=False)
    category_id = Column(Integer, nullable=False)
    price = Column(Numeric, nullable=False)
    description = Column(String, nullable=False)
    image_url = Column(String, nullable=False)

Base.metadata.create_all(engine)

#Pydantic Models
class ProductCreate(BaseModel):
    product_name:str
    name:str
    category_id:int
    price:float
    description:str
    image_url:str

class ProductResponse(BaseModel):
    product_id:int
    product_name:str
    name:str
    category_id:int
    price:float
    description: Optional[str] = None 
    image_url: Optional[str] = None

    class Config:
        from_attributes = True

class PaginatedProductResponse(BaseModel):
    total_pages: int
    product_per_page: int
    page: int
    data: List[ProductResponse]


router = APIRouter(
    prefix="/products",
    tags=["Products"]
)

@router.get("/", response_model=PaginatedProductResponse)
def get_all_products(db:Session = Depends(get_db), page: int = Query(default=1, ge=1), product_per_page: int = Query(default=20, ge=1, le=100)):
    calculated_offset = (page - 1) * product_per_page
    total = math.ceil(db.query(Product).count()/product_per_page)
    products = db.query(Product).offset( calculated_offset).limit(product_per_page).all()
    if calculated_offset  >= total:
        raise HTTPException(status_code=404, detail="Search exceed product")
    return {
        "total_pages": total,
        "product_per_page": product_per_page,
        "page": page,
        "data": products
    }

@router.get("/{product_id}", response_model=ProductResponse)
def get_product_details(product_id:int, db:Session = Depends(get_db)):
    product = db.query(Product).filter(Product.product_id==product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product

@router.get("{searchterm}", response_model=PaginatedProductResponse)
def search_product(q: str = Query(..., min_length=3, description="Search term for name or description"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
    ):
    search_term = f"%{q}%"
    
    query = db.query(Product).filter(
        or_(
            Product.product_name.ilike(search_term),
            Product.description.ilike(search_term),
            Product.name.ilike(search_term)
        )
    )

    total_count = query.count()
    total_pages = math.ceil(total_count / size)
    
    offset = (page - 1) * size
    results = query.offset(offset).limit(size).all()

    return {
        "total_pages": total_pages,
        "product_per_page": size,
        "page": page,
        "data": results
    }