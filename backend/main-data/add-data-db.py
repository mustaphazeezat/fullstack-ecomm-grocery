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
    'products', metadata,
    Column('product_id', Integer, unique=True, nullable=False),
    Column('product_name', String, nullable=False),
    Column('name', String, nullable=False),
    Column('category_id', Integer, nullable=False),
    Column('price', String, nullable=False),
    Column('description', String, nullable=False),
    Column('image_url', String, nullable=False), 
)

# Read CSV
df = pd.read_csv('main-data/mock.csv')

def extract_hi_res(image_str):
    try:
        img_dict = ast.literal_eval(image_str)
        return img_dict.get('hi_res', [None])[0]
    except:
        return None

# Apply the cleaning function
df['image_url'] = df['image_url'].apply(extract_hi_res)

# Clean up description while you're at it (removing brackets/quotes)
df['description'] = df['description'].apply(lambda x: ast.literal_eval(x)[0] if isinstance(x, str) else x)

# Insert into database
df.to_sql('products', engine, if_exists='replace', index=False)

