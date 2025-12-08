# backend/main.py

import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .database import engine, Base
from .ingestion_api import router as ingestion_router
from .recon_api import router as recon_router
from .rules_api import router as rules_router

# Initialize Logging
logging.basicConfig(level=logging.INFO)

# Create Tables
print("🛠️  Initializing Enterprise Database Schema...")
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Aureon Enterprise Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- ROUTER REGISTRATION ---
app.include_router(ingestion_router, prefix="/ingestion", tags=["ingestion"])
app.include_router(recon_router) 
app.include_router(rules_router)

@app.get("/")
def root():
    return {
        "system": "Aureon Enterprise Core", 
        "status": "OPERATIONAL", 
        "version": "v2.0.0-PILOT"
    }