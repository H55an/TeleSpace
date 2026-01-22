from fastapi import FastAPI
from api.routers import auth, explorer, structure, items, share

description = """
📘 TeleSpace Mirror API Documentation v1.0
Status: Final Specification Target: Mobile App Backend (FastAPI)

📌 Overview & Standards
This API replicates the Telegram Bot's logic strictly. It distinguishes between Sections (Organization) and Folders (Content Storage).

Base URL: http://127.0.0.1:8000
Authentication: Bearer Token via Header
Authorization: Bearer <ACCESS_TOKEN>
Date Format: ISO 8601 (YYYY-MM-DDTHH:MM:SS)
"""

app = FastAPI(
    title="TeleSpace Mirror API",
    version="1.0",
    description=description,
)

# Include Routers
app.include_router(auth.router)
app.include_router(explorer.router)
app.include_router(structure.router)
app.include_router(items.router)
app.include_router(share.router)

@app.get("/")
def read_root():
    return {"message": "TeleSpace API is running"}
