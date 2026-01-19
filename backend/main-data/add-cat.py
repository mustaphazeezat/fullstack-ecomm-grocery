import pandas as pd
from sqlalchemy import create_engine, Table, Column, Integer, String, MetaData
import os
from dotenv import load_dotenv
import ast

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

# Connect to DB
engine = create_engine(DATABASE_URL)
metadata = MetaData()

# Define movies table (optional if already created)
products_table = Table(
    'product_category', metadata,
    Column('category_id', Integer, primary_key=True, index=True),
    Column('category_name', String, nullable=False),
)

# Read CSV
df = pd.read_csv('main-data/category.csv')

# Insert into database
df.to_sql('product_category', engine, if_exists='replace', index=False)

