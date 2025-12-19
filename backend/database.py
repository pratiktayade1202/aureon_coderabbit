# backend/database.py
import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# Load the .env file
load_dotenv(override=True)  # Override env vars with .env file values

# 1. Get the URL from Environment (Vercel injects this automatically)
DATABASE_URL = os.getenv("POSTGRES_URL") or os.getenv("DATABASE_URL")

# 2. Fix for SQLAlchemy (Neon gives "postgres://", we need "postgresql://")
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# 3. Handle SSL (Required for Neon)
connect_args = {}
if DATABASE_URL and "neon.tech" in DATABASE_URL:
    connect_args = {"sslmode": "require"}

# Fallback for local testing if no URL is found
if not DATABASE_URL:
    # Use a local sqlite file for dev if needed, or raise error
    DATABASE_URL = "sqlite:///./aureon_test.db" 
    connect_args = {"check_same_thread": False}

# 4. Create Engine
engine = create_engine(
    DATABASE_URL, 
    pool_pre_ping=True, 
    # Only use connect_args for Postgres (SSL) or SQLite specific flags
    connect_args=connect_args if "sqlite" not in DATABASE_URL else {"check_same_thread": False}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()