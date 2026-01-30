from fastapi import APIRouter, Depends, Query, HTTPException, Request
from typing import List
from api.dependencies import get_current_user
from api.schemas import (
    RootContainersResponse, ContainerInfo, SectionContentResponse, 
    FolderContentResponse, SectionInfo, FolderInfo, 
    ItemInfo, Breadcrumb, Pagination
)
from app.shared.database import containers as db_containers
from app.shared.database import items as db_items
from app.shared.database import auth as db_auth

router = APIRouter(prefix="/explorer", tags=["Explorer"])

@router.get("/roots", response_model=RootContainersResponse)
def get_roots(user_id: int = Depends(get_current_user)):
    """
    Fetches top-level Sections and Folders.
    """
    roots = db_containers.get_root_containers(user_id)
    
    sections = []
    folders = []
    
    for r in roots:
        c_info = ContainerInfo(
            id=r['id'],
            name=r['name'],
            type=r['type'],
            icon="briefcase" if r['type'] == 'section' else "folder",
            created_at=str(r.get('creation_date', ''))
        )
        if r['type'] == 'section':
            sections.append(c_info)
        else:
            folders.append(c_info)
            
    return RootContainersResponse(sections=sections, folders=folders)

@router.get("/section/{section_id}", response_model=SectionContentResponse)
def view_section_content(section_id: int, user_id: int = Depends(get_current_user)):
    """
    Returns Sub-Sections and Folders inside a specific section.
    """
    if not db_containers.container_exists(section_id):
        raise HTTPException(status_code=404, detail="Section not found")
        
    details = db_containers.get_container_details(section_id)
    if details['type'] != 'section':
         raise HTTPException(status_code=400, detail="Requested container is not a Section")

    # Check Permissions
    permission = db_auth.get_permission_level(user_id, 'section', section_id)
    if not permission:
        raise HTTPException(status_code=403, detail="Access denied")

    # Get Children
    children = db_containers.get_child_containers(section_id)
    sub_sections = []
    folders = []
    
    for child in children:
        c_info = ContainerInfo(
            id=child['id'],
            name=child['name'],
            type=child['type'],
            icon="briefcase" if child['type'] == 'section' else "folder",
            # created_at missing in get_child_containers select, treating as None
        )
        if child['type'] == 'section':
            sub_sections.append(c_info)
        else:
            folders.append(c_info)

    # Breadcrumbs
    path = db_containers.get_container_path(section_id)
    breadcrumbs = [Breadcrumb(id=p[0], name=p[1]) for p in path]

    return SectionContentResponse(
        info=SectionInfo(
            id=details['id'],
            name=details['name'],
            parent_id=details['parent_id'],
            role=permission
        ),
        sub_sections=sub_sections,
        folders=folders,
        breadcrumbs=breadcrumbs
    )

@router.get("/folder/{folder_id}", response_model=FolderContentResponse)
def view_folder_content(
    folder_id: int, 
    request: Request,
    page: int = Query(1, ge=1), 
    limit: int = Query(50, le=100),
    user_id: int = Depends(get_current_user)
):
    """
    Returns items inside a specific folder.
    """
    if not db_containers.container_exists(folder_id):
        raise HTTPException(status_code=404, detail="Folder not found")

    details = db_containers.get_container_details(folder_id)
    if details['type'] != 'folder':
         raise HTTPException(status_code=400, detail="Requested container is not a Folder")

    # Check Permissions
    permission = db_auth.get_permission_level(user_id, 'folder', folder_id)
    if not permission:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Calculate offset
    offset = (page - 1) * limit
    
    # Get Items
    items_data, total_items = db_items.get_items_paginated(folder_id, limit, offset)
    
    items = []
    base_url = str(request.base_url).rstrip("/")
    
    for i in items_data:
        # Construct Thumbnail URL if video or photo
        thumb_url = None
        # We use a placeholder logic here. In reality, we'd need file_unique_id.
        # Assuming 'content' field holds file_id for non-text items.
        # We'll use file_id as a proxy for unique_id for now, or just a generic link.
        if i['item_type'] in ['video', 'photo']:
            # We use the item ID or content (file_id) to map to a thumbnail
            # The URL pattern: /static/thumbnails/{file_unique_id}.jpg
            # Since we don't have unique_id explicitly separate, we might use file_id or a hash.
            # For demonstration purposes, we assume file_id is usable or mapped.
             if i.get('content'):
                 # Extract a semblance of unique id or just use file_id
                 thumb_url = f"{base_url}/static/thumbnails/{i['content']}.jpg"

        items.append(ItemInfo(
            id=i['item_record_id'],
            type=i['item_type'],
            name=i['item_name'],
            size=None, # Not stored in DB currently
            mime_type=None, # Not stored in DB currently
            thumbnail_url=thumb_url,
            timestamp=str(i.get('upload_date', '')), 
            content=i['content'] if i['item_type'] == 'text' else None
        ))
        
    return FolderContentResponse(
        info=FolderInfo(
            id=details['id'],
            name=details['name'],
            parent_id=details['parent_id'],
            role=permission
        ),
        items=items,
        pagination=Pagination(
            current_page=page,
            total_pages=(total_items + limit - 1) // limit,
            total_items=total_items
        )
    )
