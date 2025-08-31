from telegram import InlineKeyboardButton, InlineKeyboardMarkup
# نستورد الدوال التي تجلب البيانات من قاعدة البيانات
from database import get_root_sections, get_root_folders

def build_main_menu_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """
    تبني وتعيد لوحة الأزرار للواجهة الرئيسية (الأقسام والمجلدات الرئيسية فقط).
    """
    keyboard_layout = []
    
    root_sections = get_root_sections(user_id)
    if root_sections:
        keyboard_layout.append([InlineKeyboardButton(f"📂 {s['section_name']}", callback_data=f"section:{s['section_id']}") for s in root_sections])
        
    root_folders = get_root_folders(user_id)
    if root_folders:
        keyboard_layout.append([InlineKeyboardButton(f"📁 {f['folder_name']}", callback_data=f"folder:{f['folder_id']}") for f in root_folders])
        
    control_buttons = [
        InlineKeyboardButton("➕ قسم رئيسي", callback_data="new_section_root"),
        InlineKeyboardButton("➕ مجلد رئيسي", callback_data="new_folder_root")
    ]
    keyboard_layout.append(control_buttons)
    
    return InlineKeyboardMarkup(keyboard_layout)