import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

DB_PARAMS = {
    'dbname': os.getenv('POSTGRES_DB'),
    'user': os.getenv('POSTGRES_USER'),
    'password': os.getenv('POSTGRES_PASSWORD'),
    'host': os.getenv('POSTGRES_HOST'),
    'port': os.getenv('POSTGRES_PORT', '5433'),  # Default to 5433 if not set
}

def get_conn():
    return psycopg2.connect(**DB_PARAMS)

def create_table():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute('''
            CREATE TABLE IF NOT EXISTS cars (
                id SERIAL PRIMARY KEY,
                url TEXT UNIQUE,
                title TEXT,
                price_usd NUMERIC,
                odometer INTEGER,
                username TEXT,
                phone_number BIGINT,
                image_url TEXT,
                images_count INTEGER,
                car_number TEXT,
                car_vin TEXT,
                datetime_found TIMESTAMP
            );
            ''')
            conn.commit()
