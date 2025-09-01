# keyboards.py

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from database import get_root_sections, get_root_folders, get_subsections, get_folders_in_section

def build_main_menu_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """
    #[تعديل جوهري]: تبني الواجهة الرئيسية مع زر إعدادات بجانب كل عنصر.
    """
    keyboard_layout = []
    
    # بناء أزرار الأقسام الرئيسية
    root_sections = get_root_sections(user_id)
    for section in root_sections:
        keyboard_layout.append([
            InlineKeyboardButton(f"📂 {section['section_name']}", callback_data=f"section:{section['section_id']}"),
            InlineKeyboardButton("⚙️", callback_data=f"settings_section:{section['section_id']}")
        ])
        
    # بناء أزرار المجلدات الرئيسية
    root_folders = get_root_folders(user_id)
    for folder in root_folders:
        keyboard_layout.append([
            InlineKeyboardButton(f"📁 {folder['folder_name']}", callback_data=f"folder:{folder['folder_id']}"),
            InlineKeyboardButton("⚙️", callback_data=f"settings_folder:{folder['folder_id']}")
        ])
        
    # أزرار الإنشاء
    control_buttons = [
        InlineKeyboardButton("➕ قسم رئيسي", callback_data="new_section_root"),
        InlineKeyboardButton("➕ مجلد رئيسي", callback_data="new_folder_root")
    ]
    keyboard_layout.append(control_buttons)
    
    return InlineKeyboardMarkup(keyboard_layout)

def build_section_view_keyboard(section_id: int) -> InlineKeyboardMarkup:
    """
    #[إضافة جديدة]: دالة مخصصة لبناء واجهة عرض محتويات القسم.
    """
    keyboard_layout = []
    
    # بناء أزرار الأقسام الفرعية
    subsections = get_subsections(section_id)
    for sub in subsections:
        keyboard_layout.append([
            InlineKeyboardButton(f"📂 {sub['section_name']}", callback_data=f"section:{sub['section_id']}"),
            InlineKeyboardButton("⚙️", callback_data=f"settings_section:{sub['section_id']}")
        ])

    # بناء أزرار المجلدات داخل القسم
    folders_in_section = get_folders_in_section(section_id)
    for folder in folders_in_section:
        keyboard_layout.append([
            InlineKeyboardButton(f"📁 {folder['folder_name']}", callback_data=f"folder:{folder['folder_id']}"),
            InlineKeyboardButton("⚙️", callback_data=f"settings_folder:{folder['folder_id']}")
        ])

    # أزرار التحكم
    control_buttons = [
        InlineKeyboardButton("➕ قسم فرعي هنا", callback_data=f"new_section_sub:{section_id}"),
        InlineKeyboardButton("➕ مجلد جديد هنا", callback_data=f"new_folder_in_sec:{section_id}")
    ]
    keyboard_layout.append(control_buttons)
    keyboard_layout.append([InlineKeyboardButton("🔙 العودة للقائمة الرئيسية", callback_data="back_to_main")])
    
    return InlineKeyboardMarkup(keyboard_layout)