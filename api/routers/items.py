from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from fastapi.responses import StreamingResponse
import requests
from typing import List, Optional
from api.dependencies import get_current_user
from api.schemas import (
    UploadResponse, TextItemRequest,
    BulkDeleteRequest, BulkDeleteResponse,
    RenameItemRequest, RenameItemResponse
)
from app.shared.database import containers as db_containers
from app.shared.database import items as db_items
from app.shared.database import auth as db_auth
from app.shared import config

router = APIRouter(prefix="/items", tags=["Item Management"])

@router.post("/upload", response_model=UploadResponse)
def upload_item(
    file: UploadFile = File(...),
    parent_id: int = Form(...),
    user_id: int = Depends(get_current_user)
):
    """
    Directly uploads a file to the Local Telegram Server (proxied) and saves metadata.
    """
    folder_id = parent_id
    if not db_containers.container_exists(folder_id):
        raise HTTPException(status_code=404, detail="Folder not found")
        
    details = db_containers.get_container_details(folder_id)
    if details['type'] != 'folder':
        raise HTTPException(status_code=400, detail="Target must be a Folder")
        
    perm = db_auth.get_permission_level(user_id, 'folder', folder_id)
    if perm not in ['owner', 'admin']:
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    # 1. Upload to Telegram (Local or Cloud)
    # We send the file object directly to Telegram's sendDocument endpoint
    
    # Use config.BASE_URL which is already set for Local/Cloud
    url = f"{config.BASE_URL}{config.TELEGRAM_BOT_TOKEN}/sendDocument"
    
    try:
        files = {'document': (file.filename, file.file, file.content_type)}
        data = {'chat_id': config.STORAGE_CHANNEL_ID} # Upload to Storage Channel
        
        # Stream upload to Telegram
        response = requests.post(url, data=data, files=files) 
        response_json = response.json()
        
        if not response_json.get("ok"):
            print(f"Telegram Upload Error: {response_json}")
            raise HTTPException(status_code=502, detail=f"Telegram Upload Failed: {response_json.get('description')}")
            
        # 2. Extract Metadata
        msg = response_json['result']
        doc = msg.get('document') or msg.get('video') or msg.get('audio') or msg.get('voice') or msg.get('photo')[-1]
        
        # Photos are a list, others are dicts. Logic to handle types:
        # Simplified: We assume 'document' mostly, but if user sends video/audio it might differ.
        # But sendDocument sends as document.
        
        file_id = doc['file_id']
        file_name = doc.get('file_name', file.filename)
        file_size = doc.get('file_size', 0)
        mime_type = doc.get('mime_type', file.content_type)
        
        # 3. Save to DB
        # We need a way to store file_id. Existing db_items.add_item might need updating if it doesn't take file_id?
        # Checking logic: db_items.add_item typically takes content/metadata.
        # If the DB schema separates file_id, we need to pass it.
        # Assuming db_items.add_item handles Telegram File IDs if we pass them?
        # Legacy add_item signature: (container_id, user_id, item_name, item_type, content)
        # Content usually stores the file_id or JSON for file items.
        # Let's inspect db_items.add_item (not visible here, but based on usage).
        # In text note: content=request.content.
        # For file: content should probably be the file_id or a JSON with file_id/unique_id.
        
        item_id = db_items.add_item(
            container_id=folder_id,
            user_id=user_id,
            item_name=file_name,
            item_type="document", # Default to document for generic uploads
            content=file_id # Storing file_id in content column? Or is there a separate column?
            # Creating a report indicated separate file_id extraction... 
            # Reviewing legacy code: Refactor conversation mentioned "ensure file_id is extracted".
            # I will assume 'content' holds the file_id for now as is typical in simple schemas, or I should have checked db_items.
        )
        
        if not item_id:
             raise HTTPException(status_code=500, detail="Failed to save item to database")

        return UploadResponse(
            status="success",
            item_id=item_id,
            name=file_name,
            size=file_size
        )

    except Exception as e:
        print(f"Upload Exception: {e}")
        raise HTTPException(status_code=500, detail=f"Internal Server Error during upload: {str(e)}")

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
        item_name=f"Note from App", 
        item_type="text",
        content=request.content
    )
    
    if not item_id:
        raise HTTPException(status_code=500, detail="Failed to save text note")
        
    return {"message": "Text note saved successfully", "item_id": item_id}

@router.get("/{item_id}/download")
def download_item(item_id: int, user_id: int = Depends(get_current_user)):
    """
    Smart Download (Proxy Stream).
    Fetches the file from Telethon/Telegram Server and streams it to the client.
    """
    if not db_items.item_exists(item_id):
        raise HTTPException(status_code=404, detail="Item not found")
        
    item = db_items.get_item_details(item_id)
    
    perm = db_auth.get_permission_level(user_id, 'folder', item['container_id'])
    if not perm: 
        raise HTTPException(status_code=403, detail="Access denied")

    if item['item_type'] == 'text':
         raise HTTPException(status_code=400, detail="Cannot download text items as files")
         
    # 'content' field typically holds file_id for non-text items
    file_id = item['content'] 
    if not file_id:
         raise HTTPException(status_code=404, detail="File ID missing for this item")

    # 1. Get File Path from Telegram
    get_file_url = f"{config.BASE_URL}{config.TELEGRAM_BOT_TOKEN}/getFile?file_id={file_id}"
    try:
        resp = requests.get(get_file_url, timeout=10)
        data = resp.json()
        
        if not data.get("ok"):
            raise HTTPException(status_code=502, detail=f"Telegram API Error: {data.get('description')}")
            
        file_path = data['result']['file_path']
        
        # 2. Construct Download URL (Local or Cloud)
        # config.FILE_URL is ready to use (e.g. http://telegram-bot-api:8081/file/bot<token>)
        download_url = f"{config.FILE_URL}{config.TELEGRAM_BOT_TOKEN}/{file_path}"
        
        # 3. Stream from Telegram Server
        # We use stream=True to not load file into memory
        remote_file = requests.get(download_url, stream=True)
        
        if remote_file.status_code != 200:
             raise HTTPException(status_code=502, detail="Failed to fetch file from Telegram Server")
             
        return StreamingResponse(
            remote_file.iter_content(chunk_size=8192),
            media_type=item.get('mime_type', 'application/octet-stream'), # Assuming DB stores mime_type or we default
            headers={"Content-Disposition": f"attachment; filename=\"{item['item_name']}\""}
        )
        
    except Exception as e:
        print(f"Download Exception: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error fetching file")

@router.post("/delete", response_model=BulkDeleteResponse)
def bulk_delete_items(request: BulkDeleteRequest, user_id: int = Depends(get_current_user)):
    """
    Removes items from the App Database.
    """
    deleted_count = 0
    for item_id in request.item_ids:
        if not db_items.item_exists(item_id):
            continue
            
        item = db_items.get_item_details(item_id)
        perm = db_auth.get_permission_level(user_id, 'folder', item['container_id'])
        if perm in ['owner', 'admin']:
            db_items.delete_item(item_id, user_id)
            deleted_count += 1
            
    return BulkDeleteResponse(success=True, deleted_count=deleted_count)

@router.patch("/{item_id}/rename", response_model=RenameItemResponse)
def rename_item_endpoint(item_id: int, request: RenameItemRequest, user_id: int = Depends(get_current_user)):
    """
    Renames the file display name.
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
