from fastapi import APIRouter, Depends, HTTPException, status
import requests
from api.dependencies import get_current_user
from api.schemas import (
    UploadRequestRequest, UploadRequestResponse, TextItemRequest,
    DownloadLinkResponse, BulkDeleteRequest, BulkDeleteResponse,
    RenameItemRequest, RenameItemResponse
)
from app.shared.database import containers as db_containers
from app.shared.database import items as db_items
from app.shared.database import auth as db_auth
from app.shared import config

router = APIRouter(prefix="/items", tags=["Item Management"])

@router.post("/upload/request", response_model=UploadRequestResponse)
def request_reverse_upload(request: UploadRequestRequest, user_id: int = Depends(get_current_user)):
    """
    Generates a deep link to the bot to handle file uploads.
    """
    folder_id = request.target_folder_id
    if not db_containers.container_exists(folder_id):
        raise HTTPException(status_code=404, detail="Folder not found")
        
    details = db_containers.get_container_details(folder_id)
    if details['type'] != 'folder':
        raise HTTPException(status_code=400, detail="Target must be a Folder")
        
    perm = db_auth.get_permission_level(user_id, 'folder', folder_id)
    if perm not in ['owner', 'admin']:
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    bot_username = "TeleSpaceBot" # Placeholder
    deep_link = f"https://t.me/{bot_username}?start=upload_{folder_id}"
    
    return UploadRequestResponse(
        deep_link=deep_link,
        instructions="Click the link to open Telegram and send your files there."
    )

@router.post("/text", response_model=dict)
def add_text_note(request: TextItemRequest, user_id: int = Depends(get_current_user)):
    """
    Directly saves a text item from the app.
    """
    folder_id = request.folder_id
    if not db_containers.container_exists(folder_id):
        raise HTTPException(status_code=404, detail="Folder not found")
        
    perm = db_auth.get_permission_level(user_id, 'folder', folder_id)
    if perm not in ['owner', 'admin']:
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    # Save to DB
    item_id = db_items.add_item(
        container_id=folder_id,
        user_id=user_id,
        item_name=f"Note from App", # Or derive from content
        item_type="text",
        content=request.content
    )
    
    if not item_id:
        raise HTTPException(status_code=500, detail="Failed to save text note")
        
    return {"message": "Text note saved successfully", "item_id": item_id}

@router.post("/{item_id}/download", response_model=DownloadLinkResponse)
def get_download_link(item_id: int, user_id: int = Depends(get_current_user)):
    """
    Returns a direct Telegram file URL (temporary).
    """
    if not db_items.item_exists(item_id):
        raise HTTPException(status_code=404, detail="Item not found")
        
    item = db_items.get_item_details(item_id)
    
    # Check permissions on the container
    perm = db_auth.get_permission_level(user_id, 'folder', item['container_id'])
    if not perm: # viewer+ is enough
        raise HTTPException(status_code=403, detail="Access denied")

    if item['item_type'] == 'text':
         raise HTTPException(status_code=400, detail="Cannot download text items")
         
    file_id = item['file_id']
    if not file_id:
         raise HTTPException(status_code=404, detail="File ID missing for this item")

    # Call Telegram API getFile
    url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/getFile?file_id={file_id}"
    try:
        resp = requests.get(url, timeout=10)
        data = resp.json()
        
        if not data.get("ok"):
            raise HTTPException(status_code=502, detail=f"Telegram API Error: {data.get('description')}")
            
        file_path = data['result']['file_path']
        direct_url = f"https://api.telegram.org/file/bot{config.TELEGRAM_BOT_TOKEN}/{file_path}"
        
        return DownloadLinkResponse(
            direct_url=direct_url,
            expires_in=3600 # 1 hour default from Telegram? actually it's persistent until bot token changes usually, but we say 1 hour
        )
    except Exception as e:
        print(f"Error fetching file path: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error fetching download link")

@router.post("/delete", response_model=BulkDeleteResponse)
def bulk_delete_items(request: BulkDeleteRequest, user_id: int = Depends(get_current_user)):
    """
    Removes items from the App Database ONLY.
    """
    deleted_count = 0
    for item_id in request.item_ids:
        if not db_items.item_exists(item_id):
            continue
            
        item = db_items.get_item_details(item_id)
        # Check permission for EACH item's container
        perm = db_auth.get_permission_level(user_id, 'folder', item['container_id'])
        if perm in ['owner', 'admin']:
            db_items.delete_item(item_id, user_id)
            deleted_count += 1
            
    return BulkDeleteResponse(success=True, deleted_count=deleted_count)

@router.patch("/{item_id}/rename", response_model=RenameItemResponse)
def rename_item_endpoint(item_id: int, request: RenameItemRequest, user_id: int = Depends(get_current_user)):
    """
    Renames the file display name in the database.
    """
    if not db_items.item_exists(item_id):
        raise HTTPException(status_code=404, detail="Item not found")

    item = db_items.get_item_details(item_id)
    perm = db_auth.get_permission_level(user_id, 'folder', item['container_id'])
    
    if perm not in ['owner', 'admin']:
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    result = db_items.rename_item(item_id, request.new_name, user_id)
    if not result:
        raise HTTPException(status_code=500, detail="Failed to rename item")
        
    return RenameItemResponse(id=result['item_record_id'], name=result['item_name'])
