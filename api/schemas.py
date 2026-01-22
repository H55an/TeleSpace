from pydantic import BaseModel
from typing import List, Optional, Any
from datetime import datetime

# --- Auth Schemas ---
class LoginInitiateRequest(BaseModel):
    device_name: Optional[str] = "Mobile App"

class LoginInitiateResponse(BaseModel):
    request_id: str
    deep_link: str
    expires_in: int

class UserInfo(BaseModel):
    id: int
    first_name: str
    username: Optional[str] = None
    photo_url: Optional[str] = None

class LoginStatusResponse(BaseModel):
    status: str  # 'pending', 'approved', 'expired', 'rejected'
    access_token: Optional[str] = None
    user: Optional[UserInfo] = None

# --- Explorer Schemas ---
class ContainerInfo(BaseModel):
    id: int
    name: str
    type: str # 'section', 'folder'
    icon: str
    created_at: Optional[str] = None # ISO format string

class RootContainersResponse(BaseModel):
    sections: List[ContainerInfo]
    folders: List[ContainerInfo]

class Breadcrumb(BaseModel):
    id: int
    name: str

class SectionInfo(BaseModel):
    id: int
    name: str
    parent_id: Optional[int]
    role: str # 'owner', 'admin', 'viewer'

class SectionContentResponse(BaseModel):
    info: SectionInfo
    sub_sections: List[ContainerInfo]
    folders: List[ContainerInfo]
    breadcrumbs: List[Breadcrumb]

class ItemInfo(BaseModel):
    id: int
    type: str # 'document', 'photo', 'video', 'voice', 'text', 'audio'
    name: Optional[str] = None
    size: Optional[str] = None
    timestamp: Optional[str] = None
    content: Optional[str] = None

class FolderInfo(BaseModel):
    id: int
    name: str
    parent_id: Optional[int]
    role: str

class Pagination(BaseModel):
    current_page: int
    total_pages: int
    total_items: int

class FolderContentResponse(BaseModel):
    info: FolderInfo
    items: List[ItemInfo]
    pagination: Pagination

# --- Structure Management Schemas ---
class CreateSectionRequest(BaseModel):
    name: str
    parent_id: Optional[int] = None

class CreateFolderRequest(BaseModel):
    name: str
    parent_section_id: Optional[int] = None

class RenameRequest(BaseModel):
    new_name: str

class DeleteResponse(BaseModel):
    message: str

# --- Item Management Schemas ---
class UploadRequestRequest(BaseModel):
    target_folder_id: int

class UploadRequestResponse(BaseModel):
    deep_link: str
    instructions: str

class TextItemRequest(BaseModel):
    folder_id: int
    content: str

class DownloadLinkResponse(BaseModel):
    direct_url: str
    expires_in: int

class BulkDeleteRequest(BaseModel):
    item_ids: List[int]

class BulkDeleteResponse(BaseModel):
    success: bool
    deleted_count: int

class RenameItemRequest(BaseModel):
    new_name: str

class RenameItemResponse(BaseModel):
    id: int
    name: str

# --- Sharing Schemas ---
class ShareLinkRequest(BaseModel):
    entity_id: int
    entity_type: str # 'section', 'folder'
    role: str # 'viewer', 'admin'

class ShareLinkResponse(BaseModel):
    share_link: str

class LeaveShareRequest(BaseModel):
    entity_id: int
    entity_type: str # 'section', 'folder'
