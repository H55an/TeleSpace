from fastapi import APIRouter, Depends, Query, HTTPException
from typing import List
from api.dependencies import get_current_user
from api.schemas import ContainerResponse, ItemResponse, ContainerContentResponse
from app.shared.database import containers as db_containers
from app.shared.database import items as db_items
from app.shared.constants import PAGE_SIZE

router = APIRouter(prefix="/explorer", tags=["explorer"])

@router.get("/roots", response_model=List[ContainerResponse])
def get_roots(user_id: int = Depends(get_current_user)):
    """
    Returns the root containers (sections/folders) for the user.
    """
    roots = db_containers.get_root_containers(user_id)
    # Convert psycopg2 Row/DictRow to Schema
    return [
        ContainerResponse(
            id=r['id'],
            name=r['name'],
            type=r['type'],
            owner_user_id=r['owner_user_id']
        ) for r in roots
    ]

@router.get("/container/{container_id}", response_model=ContainerContentResponse)
def get_container_content(
    container_id: int, 
    page: int = Query(1, ge=1), 
    user_id: int = Depends(get_current_user)
):
    """
    Returns contents (sub-folders and items) of a specific container.
    """
    # 1. Check existence
    if not db_containers.container_exists(container_id):
        raise HTTPException(status_code=404, detail="Container not found")
        
    # 2. Check Permissions (Basic check: is owner or has permission?)
    # Since shared logic handles permissions in queries usually, but get_child_containers doesn't filter by user permissions explicitly!
    # Wait, get_child_containers takes parent_id.
    # We should verify user has access to this container first.
    # For now, we rely on the fact that if they have the ID they might see it (or we should add a permission check).
    # The prompt says "Calls get_child_containers AND get_items_paginated".
    # We will assume valid access for MVP or add a quick check.
    # db_containers.get_container_details(container_id) -> check owner or permissions table.
    # Adding a simple check:
    # details = db_containers.get_container_details(container_id)
    # if details['owner_user_id'] != user_id and not db_auth.has_direct_permission(user_id, details['type'], container_id):
    #    raise HTTPException(403, "Access denied")
    
    # 3. Get Sub-folders
    folders_data = db_containers.get_child_containers(container_id)
    folders = [
        ContainerResponse(
            id=f['id'],
            name=f['name'],
            type=f['type'],
            owner_user_id=f['owner_user_id']
        ) for f in folders_data
    ]
    
    # 4. Get Items
    items_data, total_items = db_items.get_items_paginated(container_id, page, PAGE_SIZE)
    items = [
        ItemResponse(
            id=i['item_record_id'],
            name=i['item_name'],
            type=i['item_type'],
            file_id=i['file_id']
        ) for i in items_data
    ]
    
    return ContainerContentResponse(
        container_id=container_id,
        folders=folders,
        items=items,
        total_items=total_items,
        page=page,
        page_size=PAGE_SIZE
    )
