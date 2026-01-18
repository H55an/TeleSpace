from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import sys
import os

# Ensure the app root is in path for imports to work if run directly
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.routers import auth, explorer
from app.shared import config

app = FastAPI(title="TeleSpace API", version="1.0.0")

# Setup CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(auth.router)
app.include_router(explorer.router)

@app.get("/")
def root():
    return {"message": "TeleSpace API is running"}

if __name__ == "__main__":
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)
