from fastapi import APIRouter, Depends,HTTPException, status, BackgroundTasks
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session, relationship
from sqlalchemy import Column, Integer, String, Boolean
from pydantic import BaseModel, Field
from typing import Optional
from database import get_db, Base, engine
from passlib.context import CryptContext
import hashlib
import jwt
import os
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
import bcrypt
import base64
from helpers.email import auth_send_email

load_dotenv()


router = APIRouter(
    prefix="",
    tags=["Users"]
)

SECRET_KEY = os.getenv("APP_SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM")
TOKEN_EXPIRES = int(os.getenv("TOKEN_EXPIRES"))

pwd_context = CryptContext(schemes=['bcrypt'], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")



class User(Base):
    __tablename__ = "users"
    user_id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, nullable=False)
    role = Column(String, nullable=False)
    hash_password = Column(String, nullable=False)
    is_active= Column(Boolean, default=True)

    orders = relationship("Order", back_populates="user")

Base.metadata.create_all(bind=engine)

#Pydantic Models
class UserCreate(BaseModel):
    name:str
    email:str
    role:str
    password:str = Field(..., min_length=8, max_length=72)
    is_active:bool

class UserResponse(BaseModel):
    user_id:int
    name:str
    email:str
    role:str
    is_active:bool
    class Config:
        from_attributes: True

class UserLogin(BaseModel):
    email:str
    password:str

class Token(BaseModel):
    access_token:str
    token_type:str

class TokenData(BaseModel):
   email:Optional[str] = None

class ChangePassword(BaseModel):
   email:str
   new_password:str

# -----------------------------
# Password hashing
# -----------------------------
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password:str) -> str:
    byte_pwd = password.encode('utf-8')
    sha_hash = base64.b64encode(hashlib.sha256(byte_pwd).digest())

    # 3. Use bcrypt.gensalt() and hashpw
    # bcrypt returns bytes, so we .decode() it to store as a string in DB
    hashed = bcrypt.hashpw(sha_hash, bcrypt.gensalt())
    return hashed.decode('utf-8')

def verify_password(plain_password:str, hashed_password:str) -> bool:
    # Transform the login attempt the same way we did the original
    byte_pwd = plain_password.encode('utf-8')
    sha_hash = base64.b64encode(hashlib.sha256(byte_pwd).digest())
    
    # Check against the stored hash
    return bcrypt.checkpw(sha_hash, hashed_password.encode('utf-8'))

# -----------------------------
# Password hashing
# -----------------------------
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    
    now = datetime.now(timezone.utc)
    
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=15)
        
    to_encode.update({"exp": expire})
    
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    
    return encoded_jwt
    
    
def verify_token(token:str) -> TokenData:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not verify creditials",
                headers={"WWW-Authenticate":"Bearer"}
            )
        return TokenData(email=email)
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not verify creditials",
                headers={"WWW-Authenticate":"Bearer"}
        )

def get_current_user(token:str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    token_data = verify_token(token) 
    user = db.query(User).filter(User.email == token_data.email).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User does not exisit",
                headers={"WWW-Authenticate":"Bearer"}
        )
    return user



def get_current_active_user(current_user: User = Depends(get_current_user)):
    if not current_user.is_active:
        raise HTTPException(
            status_code=404,
            detail="Inactive User",
        )
    return current_user

@router.post("/register", response_model=UserResponse)
def register(user:UserCreate, background_tasks: BackgroundTasks, db: Session= Depends(get_db)):
    if db.query(User).filter(User.email == user.email).first():
        raise HTTPException(
            status_code=404,
            detail="There is a user with this email"
        )
    hashed_pswd = hash_password(user.password)
    new_user = User(
        name=user.name,
        email=user.email,
        role=user.role,
        hash_password=hashed_pswd
    )
    db.add( new_user)
    db.commit()
    db.refresh( new_user)
    
    background_tasks.add_task(
    auth_send_email, "welcome", user.email, user.name, "Welcome to Shopper!"
    )
    
    return  new_user

@router.post("/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session= Depends(get_db)):
    user = db.query(User).filter(User.email == form_data.username).first()
    
    if not user or not verify_password(form_data.password, user.hash_password):
        raise HTTPException(
            status_code=status.HTTP_01_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled",
        )

    access_token_expires = timedelta(minutes=TOKEN_EXPIRES)
    access_token = create_access_token(
        data={"sub":user.email}, expires_delta=access_token_expires
    )
    return {
        "access_token": access_token, 
        "token_type": "bearer",
        "user": {
            "name": user.name,
            "email": user.email,
            "role": user.role
        }
    }



@router.put("/forgot-password")
def forgot_password(user_email:str, background_tasks: BackgroundTasks, db:Session = Depends(get_db)):
    user = db.query(User).filter(User.email == user_email).first()
    if not user:
        raise HTTPException(
            status_code=404,
            detail="Email not found",
        )
    background_tasks.add_task(
    auth_send_email, "password_reset", user.email, user.name, "Reset your Password"

    )

    return {"message": "If this email exists, a reset link has been sent."}
   
    

@router.put("/change-password")
def change_password(data:ChangePassword, db:Session = Depends(get_db)):
    user_db = db.query(User).filter(User.email == data.email).first()
    if not user_db:
        raise HTTPException(
            status_code=404,
            detail="User not found",
        )
    new_hash_password = hash_password(data.new_password)
    user_db.hash_password = new_hash_password

    db.commit()
    db.refresh(user_db)
    return {"message": "Password updated successfully"}
    

@router.get("/profile", response_model=UserResponse)
def get_user(current_user:User = Depends(get_current_active_user), db:Session = Depends(get_db)):
    user = db.query(User).filter(User.user_id == current_user.user_id).first()
    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found",
        )
    return user

@router.put("/profile/reset-password")
def reset_password(data:ChangePassword, current_user:User = Depends(get_current_active_user), db:Session = Depends(get_db)):
    user_db = db.query(User).filter(User.user_id == current_user.user_id).first()
    if not user_db:
        raise HTTPException(
            status_code=404,
            detail="User not found",
        )
    new_hash_password = hash_password(data.new_password)
    user_db.hash_password = new_hash_password

    db.commit()
    db.refresh(user_db)
    return {"message": "Password updated successfully"}