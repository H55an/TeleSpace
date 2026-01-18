from fastapi import APIRouter, HTTPException, status
import uuid
from app.shared.database import auth as db_auth
from app.shared import config
from api.schemas import AuthInitiateResponse, AuthStatusResponse

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/initiate", response_model=AuthInitiateResponse)
def initiate_auth():
    """
    Generates a new request_id and returns a deep link for the user to open in Telegram.
    Deep Link Format: https://t.me/BOT_NAME?start=login_UUID
    """
    request_id = str(uuid.uuid4())
    success = db_auth.create_auth_request(request_id)
    
    if not success:
        raise HTTPException(status_code=500, detail="Failed to create auth request")

    # Assuming bot username is fetched or hardcoded. Ideally config has it.
    # For now, we construct using a placeholder or config if available.
    # Using config.REQUIRED_CHANNEL_LINK to guess bot link is risky. 
    # Let's assume standard bot link format. 
    # Since we can't get bot username easily without running bot code, 
    # we will use a generic format or user configurable one.
    # The requirement asks for deep link.
    # We will assume config has bot username OR we just return the param.
    # Let's try to get bot info from config if possible (TOKEN doesn't give username directly).
    # We will assume a placeholder 'TeleSpaceBot' or allow user to replace.
    # Actually, config.py has TELEGRAM_BOT_TOKEN but not username.
    # We'll use a placeholder 'YOUR_BOT_USERNAME' and user can fix, or we check if we can parse it? No.
    # Better: just return the link param or use a 'TeleSpace_bot' guess.
    
    bot_username = "engtaiz_bot" # Best guess or placeholder.
    deep_link = f"https://t.me/{bot_username}?start=login_{request_id}"
    
    return AuthInitiateResponse(request_id=request_id, deep_link=deep_link)

@router.get("/status/{request_id}", response_model=AuthStatusResponse)
def get_auth_status(request_id: str):
    """
    Checks the status of the login request.
    """
    result = db_auth.get_auth_request_status(request_id)
    
    if not result:
        raise HTTPException(status_code=404, detail="Request ID not found")
        
    return AuthStatusResponse(
        status=result['status'],
        access_token=result['access_token']
    )
