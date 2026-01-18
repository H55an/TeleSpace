from pydantic import BaseModel
from typing import List, Optional, Any

# --- Auth Schemas ---
class AuthInitiateResponse(BaseModel):
    request_id: str
    deep_link: str

class AuthStatusResponse(BaseModel):
    status: str
    access_token: Optional[str] = None

# --- Explorer Schemas ---
class ContainerResponse(BaseModel):
    id: int
    name: str
    type: str  # 'section' or 'folder'
    owner_user_id: int

class ItemResponse(BaseModel):
    id: int
    name: Optional[str]
    type: str
    file_id: Optional[str]
    # We can add more fields as needed

class ContainerContentResponse(BaseModel):
    container_id: int
    folders: List[ContainerResponse]
    items: List[ItemResponse]
    total_items: int
    page: int
    page_size: int
