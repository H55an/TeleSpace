# keyboards.py

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from database import (
    get_root_sections, 
    get_root_folders, 
    get_subsections, 
    get_folders_in_section,
    get_section_details,
    get_permission_level # <-- [جديد] استيراد الدالة المحورية
)

def build_main_menu_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """[تعديل]: بناء الواجهة الرئيسية مع إظهار الأزرار والرموز بناءً على الصلاحيات."""
    keyboard_layout = []
    
    # جلب الأقسام الرئيسية
    root_sections = get_root_sections(user_id)
    for section in root_sections:
        permission = get_permission_level(user_id, 'section', section['section_id'])
        prefix = "🔗 " if permission in ['admin', 'viewer'] else ""
        
        row = [InlineKeyboardButton(f"{prefix}🗂️ {section['section_name']}", callback_data=f"section:{section['section_id']}")]
        keyboard_layout.append(row)

        if permission in ['owner', 'admin']:
            row1 = [
                InlineKeyboardButton("⚙️", callback_data=f"settings_section:{section['section_id']}"),
                InlineKeyboardButton("🔗", callback_data=f"share_menu_section:{section['section_id']}")
            ]
            keyboard_layout.append(row1)

    # جلب المجلدات الرئيسية
    root_folders = get_root_folders(user_id)
    for folder in root_folders:
        permission = get_permission_level(user_id, 'folder', folder['folder_id'])
        prefix = "🔗 " if permission in ['admin', 'viewer'] else ""

        row = [InlineKeyboardButton(f"{prefix}📁 {folder['folder_name']}", callback_data=f"folder:{folder['folder_id']}")]
        keyboard_layout.append(row)

        if permission in ['owner', 'admin']:
            row1 = [
                InlineKeyboardButton("⚙️", callback_data=f"settings_folder:{folder['folder_id']}"),
                InlineKeyboardButton("🔗", callback_data=f"share_menu_folder:{folder['folder_id']}")
            ]
            keyboard_layout.append(row1)
        
    # أزرار الإنشاء (دائمًا ظاهرة في القائمة الرئيسية)
    control_buttons = [
        InlineKeyboardButton("➕ قسم رئيسي", callback_data="new_section_root"),
        InlineKeyboardButton("➕ مجلد رئيسي", callback_data="new_folder_root")
    ]
    keyboard_layout.append(control_buttons)
    
    return InlineKeyboardMarkup(keyboard_layout)

def build_section_view_keyboard(section_id: int, user_id: int) -> InlineKeyboardMarkup:
    """[تعديل]: بناء واجهة عرض القسم مع إظهار الأزرار والرموز بناءً على الصلاحيات."""
    keyboard_layout = []
    
    # جلب الأقسام الفرعية
    subsections = get_subsections(section_id)
    for sub in subsections:
        permission = get_permission_level(user_id, 'section', sub['section_id'])
        prefix = "🔗 " if permission in ['admin', 'viewer'] else ""
        
        row = [InlineKeyboardButton(f"{prefix}🗂️ {sub['section_name']}", callback_data=f"section:{sub['section_id']}")]
        keyboard_layout.append(row)

        if permission in ['owner', 'admin']:
            row1 = [
                InlineKeyboardButton("⚙️", callback_data=f"settings_section:{sub['section_id']}"),
                InlineKeyboardButton("🔗", callback_data=f"share_menu_section:{sub['section_id']}")
            ]
            keyboard_layout.append(row1)

    # جلب المجلدات داخل القسم
    folders_in_section = get_folders_in_section(section_id)
    for folder in folders_in_section:
        permission = get_permission_level(user_id, 'folder', folder['folder_id'])
        prefix = "🔗 " if permission in ['admin', 'viewer'] else ""

        row = [InlineKeyboardButton(f"{prefix}📁 {folder['folder_name']}", callback_data=f"folder:{folder['folder_id']}")]
        keyboard_layout.append(row)

        if permission in ['owner', 'admin']:
            row1 = [
                InlineKeyboardButton("⚙️", callback_data=f"settings_folder:{folder['folder_id']}"),
                InlineKeyboardButton("🔗", callback_data=f"share_menu_folder:{folder['folder_id']}")
            ]
            keyboard_layout.append(row1)

    # أزرار التحكم (الإنشاء) - تظهر فقط للمالك والمشرف على القسم الحالي
    current_section_permission = get_permission_level(user_id, 'section', section_id)
    if current_section_permission in ['owner', 'admin']:
        control_buttons = [
            InlineKeyboardButton("➕ قسم فرعي هنا", callback_data=f"new_section_sub:{section_id}"),
            InlineKeyboardButton("➕ مجلد جديد هنا", callback_data=f"new_folder_in_sec:{section_id}")
        ]
        keyboard_layout.append(control_buttons)
    
    # --- زر العودة الذكي ---
    section_details = get_section_details(section_id)
    parent_section_id = section_details['parent_section_id'] if section_details else None
    
    if parent_section_id:
        back_button = InlineKeyboardButton("🔙 عودة", callback_data=f"section:{parent_section_id}")
    else:
        back_button = InlineKeyboardButton("🔙 عودة", callback_data="back_to_main")
        
    keyboard_layout.append([back_button])
    
    return InlineKeyboardMarkup(keyboard_layout)