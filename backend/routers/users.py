from fastapi import APIRouter, Depends,HTTPException,Query
from sqlalchemy.orm import Session
from sqlalchemy import Column, Integer, String, Numeric, or_
from pydantic import BaseModel
from typing import Optional, List
from database import get_db, Base, engine
import math


