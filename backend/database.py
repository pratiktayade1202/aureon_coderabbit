# backend/database.py
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv

# Load the .env file
load_dotenv(override=True)  # Override env vars with .env file values

# 1. Get the URL (Assign to DATABASE_URL)
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://aureon:aureon123@localhost:5432/custody_ai"
)

# 2. THE FIX: Check DATABASE_URL, not 'url'
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# 3. Create the engine using the corrected DATABASE_URL
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,  # Checks connection health
    pool_size=20,        # Allow 20 concurrent connections
    max_overflow=10
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()