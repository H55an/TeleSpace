# keyboards.py

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from database import (
    get_root_sections,
    get_root_folders,
    get_subsections,
    get_folders_in_section,
    get_section_details,
    get_permission_level,
    has_direct_permission,
    get_parent_section_id,
    get_section_id_for_folder,
    get_folder_details
)

def build_my_space_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """Bears the keyboard for the user's own space, showing only owned items."""
    keyboard_layout = []
    
    # Fetch and filter owned sections
    root_sections = get_root_sections(user_id)
    owned_sections = [s for s in root_sections if s['owner_user_id'] == user_id]
    for section in owned_sections:
        section_button = InlineKeyboardButton(f"🗂️ {section['section_name']}", callback_data=f"section:{section['section_id']}")
        controls_row = [
            InlineKeyboardButton("⚙️", callback_data=f"settings_section:{section['section_id']}"),
            InlineKeyboardButton("🔗", callback_data=f"share_menu_section:{section['section_id']}")
        ]
        keyboard_layout.append([section_button])
        keyboard_layout.append(controls_row)

    # Fetch and filter owned folders
    root_folders = get_root_folders(user_id)
    owned_folders = [f for f in root_folders if f['owner_user_id'] == user_id]
    for folder in owned_folders:
        folder_button = InlineKeyboardButton(f"📁 {folder['folder_name']}", callback_data=f"folder:{folder['folder_id']}")
        controls_row = [
            InlineKeyboardButton("⚙️", callback_data=f"settings_folder:{folder['folder_id']}"),
            InlineKeyboardButton("🔗", callback_data=f"share_menu_folder:{folder['folder_id']}")
        ]
        keyboard_layout.append([folder_button])
        keyboard_layout.append(controls_row)
        
    # Add new item buttons
    control_buttons = [
        InlineKeyboardButton("➕ قسم رئيسي", callback_data="new_section_root"),
        InlineKeyboardButton("➕ مجلد رئيسي", callback_data="new_folder_root")
    ]
    keyboard_layout.append(control_buttons)
    
    # Add back button to the main lobby
    keyboard_layout.append([InlineKeyboardButton("🔙 العودة إلى البداية", callback_data="back_to_main")])
    
    return InlineKeyboardMarkup(keyboard_layout)

def build_shared_spaces_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """Bears the keyboard for shared spaces, showing items shared with the user."""
    keyboard_layout = []
    
    # Fetch and filter shared sections
    root_sections = get_root_sections(user_id)
    shared_sections = [s for s in root_sections if s['owner_user_id'] != user_id]
    for section in shared_sections:
        section_button = InlineKeyboardButton(f"🔗 🗂️ {section['section_name']}", callback_data=f"section:{section['section_id']}")
        controls_row = [
            InlineKeyboardButton("🔗", callback_data=f"get_viewer_link:section:{section['section_id']}"),
            InlineKeyboardButton("🗑️", callback_data=f"leave_item_prompt_section:{section['section_id']}")
        ]
        keyboard_layout.append([section_button])
        keyboard_layout.append(controls_row)

    # Fetch and filter shared folders
    root_folders = get_root_folders(user_id)
    shared_folders = [f for f in root_folders if f['owner_user_id'] != user_id]
    for folder in shared_folders:
        folder_button = InlineKeyboardButton(f"🔗 📁 {folder['folder_name']}", callback_data=f"folder:{folder['folder_id']}")
        controls_row = [
            InlineKeyboardButton("🔗", callback_data=f"get_viewer_link:folder:{folder['folder_id']}"),
            InlineKeyboardButton("🗑️", callback_data=f"leave_item_prompt_folder:{folder['folder_id']}")
        ]
        keyboard_layout.append([folder_button])
        keyboard_layout.append(controls_row)
        
    # Add back button to the main lobby
    keyboard_layout.append([InlineKeyboardButton("🔙 العودة للقائمة الرئيسية", callback_data="back_to_main")])
    
    return InlineKeyboardMarkup(keyboard_layout)

def build_section_view_keyboard(section_id: int, user_id: int) -> InlineKeyboardMarkup:
    """[تعديل جذري]: بناء واجهة عرض القسم مع أزرار تحكم سياقية منفصلة."""
    keyboard_layout = []
    
    subsections = get_subsections(section_id)
    for sub in subsections:
        permission = get_permission_level(user_id, 'section', sub['section_id'])
        prefix = "🔗 " if permission in ['admin', 'viewer'] else ""
        
        section_button = InlineKeyboardButton(f"{prefix} 🗂️ {sub['section_name']}", callback_data=f"section:{sub['section_id']}")
        keyboard_layout.append([section_button])

        controls_row = []
        if permission == 'owner':
            controls_row.append(InlineKeyboardButton("⚙️", callback_data=f"settings_section:{sub['section_id']}"))
            controls_row.append(InlineKeyboardButton("🔗", callback_data=f"share_menu_section:{sub['section_id']}"))
        elif permission == 'admin':
            controls_row.append(InlineKeyboardButton("⚙️", callback_data=f"settings_section:{sub['section_id']}"))
        
        if controls_row:
            keyboard_layout.append(controls_row)

    folders_in_section = get_folders_in_section(section_id)
    for folder in folders_in_section:
        permission = get_permission_level(user_id, 'folder', folder['folder_id'])
        prefix = "🔗 " if permission in ['admin', 'viewer'] else ""

        folder_button = InlineKeyboardButton(f"{prefix} 📁 {folder['folder_name']}", callback_data=f"folder:{folder['folder_id']}")
        keyboard_layout.append([folder_button])

        controls_row = []
        if permission == 'owner':
            controls_row.append(InlineKeyboardButton("⚙️", callback_data=f"settings_folder:{folder['folder_id']}"))
            controls_row.append(InlineKeyboardButton("🔗", callback_data=f"share_menu_folder:{folder['folder_id']}"))
        elif permission == 'admin':
            controls_row.append(InlineKeyboardButton("⚙️", callback_data=f"settings_folder:{folder['folder_id']}"))

        if controls_row:
            keyboard_layout.append(controls_row)

    current_section_permission = get_permission_level(user_id, 'section', section_id)
    if current_section_permission in ['owner', 'admin']:
        control_buttons = [
            InlineKeyboardButton("➕ قسم فرعي هنا", callback_data=f"new_section_sub:{section_id}"),
            InlineKeyboardButton("➕ مجلد جديد هنا", callback_data=f"new_folder_in_sec:{section_id}")
        ]
        keyboard_layout.append(control_buttons)
    
    parent_section_id = get_parent_section_id(section_id)
    
    if parent_section_id != 0:
        back_button = InlineKeyboardButton("🔙 عودة", callback_data=f"section:{parent_section_id}")
    else:
        section_details = get_section_details(section_id)
        if section_details and section_details['user_id'] == user_id:
            back_button = InlineKeyboardButton("🔙 عودة", callback_data="my_space")
        else:
            back_button = InlineKeyboardButton("🔙 عودة", callback_data="shared_spaces")
        
    keyboard_layout.append([back_button])
    
    return InlineKeyboardMarkup(keyboard_layout)
