from fastapi import APIRouter, HTTPException, status
import uuid
from app.shared.database import auth as db_auth
from app.shared.database import users as db_users
from api.schemas import LoginInitiateRequest, LoginInitiateResponse, LoginStatusResponse, UserInfo
from app.shared import config

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/login/initiate", response_model=LoginInitiateResponse)
def initiate_login(request: LoginInitiateRequest):
    """
    Generates a unique request ID and a Telegram deep link to start the login process.
    """
    request_id = str(uuid.uuid4())
    success = db_auth.create_auth_request(request_id)
    
    if not success:
        raise HTTPException(status_code=500, detail="Failed to create auth request")
    
    # Needs to match the actual bot username. 
    # For now we use the one known or generic, assuming user configures it correctly.
    # In a real scenario, this should be in config.
    bot_username = "TeleSpaceBot" # Placeholder, ideally from config
    deep_link = f"https://t.me/{bot_username}?start=login_{request_id}"
    
    return LoginInitiateResponse(
        request_id=request_id,
        deep_link=deep_link,
        expires_in=300 # 5 minutes default
    )

@router.get("/login/status/{request_id}", response_model=LoginStatusResponse)
def check_login_status(request_id: str):
    """
    Checks the status of the login request.
    """
    result = db_auth.get_auth_request_status(request_id)
    
    if not result:
        raise HTTPException(status_code=404, detail="Request ID not found")
    
    status_str = result['status']
    access_token = result['access_token']
    user_id = result['user_id']
    
    user_info = None
    if status_str == 'approved' and user_id:
        db_user = db_users.get_user(user_id)
        if db_user:
            user_info = UserInfo(
                id=db_user['user_id'],
                first_name=db_user['first_name'],
                username=None, # user.username not in DB currently
                photo_url=None # Not stored currently
            )
            
    return LoginStatusResponse(
        status=status_str,
        access_token=access_token,
        user=user_info
    )
