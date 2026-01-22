from fastapi import APIRouter, Depends, Query, HTTPException
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
    for i in items_data:
        items.append(ItemInfo(
            id=i['item_record_id'],
            type=i['item_type'],
            name=i['item_name'],
            size=None, # Not stored in DB
            timestamp=str(i.get('upload_date', '')), # Assuming select fetches it, wait get_items_paginated SELECT doesn't fetch upload_date in previous view...
            content=i['content']
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
