from fastapi import APIRouter, Depends, HTTPException
from api.dependencies import get_current_user
from api.schemas import ShareLinkRequest, ShareLinkResponse, LeaveShareRequest
from app.shared.database import containers as db_containers
from app.shared.database import auth as db_auth

router = APIRouter(prefix="/share", tags=["Sharing"])

@router.post("/link", response_model=ShareLinkResponse)
def generate_share_link(request: ShareLinkRequest, user_id: int = Depends(get_current_user)):
    """
    Creates or retrieves a Telegram Deep Link to share a folder/section.
    """
    # Validate Entity
    if not db_containers.container_exists(request.entity_id):
        raise HTTPException(status_code=404, detail="Entity not found")
        
    details = db_containers.get_container_details(request.entity_id)
    if details['type'] != request.entity_type:
         raise HTTPException(status_code=400, detail="Entity type mismatch")
    
    # Permission Check (Owner/Admin)
    # Spec says Owner/Admin.
    # Logic in handlers allows admins to share if can_add_admins=1?
    # Or admins can always share viewer links?
    # db_auth.can_user_add_admins checks if admin can add admins.
    # If role is 'admin', user MUST be owner or admin with can_add_admins rights.
    # If role is 'viewer', generally admins can share viewer links.
    
    current_perm = db_auth.get_permission_level(user_id, request.entity_type, request.entity_id)
    if current_perm not in ['owner', 'admin']:
         raise HTTPException(status_code=403, detail="Insufficient permissions")

    share_token = None
    
    if request.role == 'viewer':
        # Return existing persistent link or create one
        share_token = db_auth.get_or_create_viewer_share_link(user_id, request.entity_type, request.entity_id)
    elif request.role == 'admin':
        # Check if user allowed to add admins
        if current_perm != 'owner' and not db_auth.can_user_add_admins(user_id, request.entity_id):
             raise HTTPException(status_code=403, detail="You do not have permission to invite admins.")
             
        # Always generate NEW One-Time-Use
        # Using create_share_link with default grants_can_add_admins=0 for now (or pass it in request? Request Body excludes it)
        # Spec says: "If role is admin: Always generate a NEW One-Time-Use token/link."
        # Does not specify grants_can_add_admins in request. Default to 0? Or 1?
        # Let's default to 0 (safer).
        share_token = db_auth.create_share_link(user_id, request.entity_type, request.entity_id, 'admin', grants_can_add_admins=0)
    else:
        raise HTTPException(status_code=400, detail="Invalid role. Must be 'viewer' or 'admin'.")

    if not share_token:
        raise HTTPException(status_code=500, detail="Failed to generate link")

    bot_username = "TeleSpaceBot" # Placeholder
    share_link = f"https://t.me/{bot_username}?start={share_token}"
    
    return ShareLinkResponse(share_link=share_link)

@router.delete("/leave", response_model=dict)
def leave_shared_space(request: LeaveShareRequest, user_id: int = Depends(get_current_user)):
    """
    Removes the current user's access to a shared resource.
    """
    if not db_containers.container_exists(request.entity_id):
        raise HTTPException(status_code=404, detail="Entity not found")
        
    # Check if user actually has permission to revoke
    if not db_auth.has_direct_permission(user_id, request.entity_type, request.entity_id):
        # Maybe they are owner? Owners cannot leave their own root container easily via this API?
        # "Removes current user's ACCESS". Owner access is inherent via containers table.
        # So this only applies to 'permissions' table.
        # If user is owner, return error?
        details = db_containers.get_container_details(request.entity_id)
        if details['owner_user_id'] == user_id:
             raise HTTPException(status_code=400, detail="Owner cannot leave their own container. Delete it instead.")
        
        raise HTTPException(status_code=400, detail="You are not a member of this space or cannot leave it.")

    db_auth.revoke_permission(user_id, request.entity_type, request.entity_id)
    
    return {"message": "Left shared space successfully"}
