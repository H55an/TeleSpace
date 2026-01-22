from fastapi import APIRouter, Depends, HTTPException, Query
from api.dependencies import get_current_user
from api.schemas import CreateSectionRequest, CreateFolderRequest, RenameRequest, DeleteResponse
from app.shared.database import containers as db_containers
from app.shared.database import auth as db_auth

router = APIRouter(prefix="/structure", tags=["Structure Management"])

@router.post("/section", response_model=dict)
def create_section(request: CreateSectionRequest, user_id: int = Depends(get_current_user)):
    """
    Creates a new organizational Section.
    """
    if not (1 <= len(request.name) <= 100):
        raise HTTPException(status_code=400, detail="Name must be between 1 and 100 characters")

    owner_id = user_id
    if request.parent_id:
        if not db_containers.container_exists(request.parent_id):
             raise HTTPException(status_code=404, detail="Parent container not found")
        
        parent_details = db_containers.get_container_details(request.parent_id)
        if parent_details['type'] != 'section':
            raise HTTPException(status_code=400, detail="Parent must be a Section")
            
        # Permission Check (Must be Owner or Admin of parent)
        perm = db_auth.get_permission_level(user_id, 'section', request.parent_id)
        if perm not in ['owner', 'admin']:
             raise HTTPException(status_code=403, detail="Insufficient permissions")
        
        # New container owner is same as parent owner? Usually yes for consistency, 
        # or the creator becomes owner? 
        # Logic in TeleSpace usually keeps 'owner_user_id' as the top-level owner.
        owner_id = parent_details['owner_user_id'] 

    new_id = db_containers.add_container(owner_id, request.name, 'section', request.parent_id)
    if not new_id:
        raise HTTPException(status_code=500, detail="Failed to create section")
        
    return {"id": new_id, "message": "Section created successfully"}

@router.post("/folder", response_model=dict)
def create_folder(request: CreateFolderRequest, user_id: int = Depends(get_current_user)):
    """
    Creates a new content Folder.
    """
    if not (1 <= len(request.name) <= 100):
        raise HTTPException(status_code=400, detail="Name must be between 1 and 100 characters")

    owner_id = user_id
    if request.parent_section_id:
        if not db_containers.container_exists(request.parent_section_id):
             raise HTTPException(status_code=404, detail="Parent container not found")
        
        parent_details = db_containers.get_container_details(request.parent_section_id)
        if parent_details['type'] != 'section':
            raise HTTPException(status_code=400, detail="Parent must be a Section. Folders cannot be nested in Folders.")
            
        # Permission Check
        perm = db_auth.get_permission_level(user_id, 'section', request.parent_section_id)
        if perm not in ['owner', 'admin']:
             raise HTTPException(status_code=403, detail="Insufficient permissions")
        
        owner_id = parent_details['owner_user_id']

    new_id = db_containers.add_container(owner_id, request.name, 'folder', request.parent_section_id)
    if not new_id:
        raise HTTPException(status_code=500, detail="Failed to create folder")
        
    return {"id": new_id, "message": "Folder created successfully"}

@router.patch("/{container_id}/rename")
def rename_container(container_id: int, request: RenameRequest, type: str = Query(..., regex="^(section|folder)$"), user_id: int = Depends(get_current_user)):
    """
    Renames a container.
    """
    if not db_containers.container_exists(container_id):
        raise HTTPException(status_code=404, detail="Container not found")

    # Permission Check
    perm = db_auth.get_permission_level(user_id, type, container_id)
    if perm not in ['owner', 'admin']:
         raise HTTPException(status_code=403, detail="Insufficient permissions")

    db_containers.rename_container(container_id, request.new_name, user_id)
    return {"message": "Renamed successfully"}

@router.delete("/{container_id}", response_model=DeleteResponse)
def delete_container(container_id: int, type: str = Query(..., regex="^(section|folder)$"), user_id: int = Depends(get_current_user)):
    """
    Deletes a container and all its contents recursively.
    """
    if not db_containers.container_exists(container_id):
        raise HTTPException(status_code=404, detail="Container not found")

    # Permission Check (Owner Only usually, or Admin if allowed? Spec says Owner Only, or Admin if allowed)
    # Let's enforce Owner or Admin for now.
    perm = db_auth.get_permission_level(user_id, type, container_id)
    if perm not in ['owner', 'admin']:
         raise HTTPException(status_code=403, detail="Insufficient permissions")
         
    # Logic in handlers/admin.py: delete_container_recursively
    db_containers.delete_container_recursively(container_id, user_id)
    
    return DeleteResponse(message="Container and contents deleted successfully.")
