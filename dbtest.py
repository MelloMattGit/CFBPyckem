import os
from dotenv import load_dotenv
import psycopg2

# Load environment variables from .env file
load_dotenv()

DB_CONFIG = {
    "dbname": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "host": os.getenv("DB_HOST"),
    "port": os.getenv("DB_PORT")
}

try:
    conn = psycopg2.connect(**DB_CONFIG)
    print("Database connection successful!")
    conn.close()
except Exception as e:
    print(f"Database connection failed: {e}")