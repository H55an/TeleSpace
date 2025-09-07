# keyboards.py

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
import database as db

def build_my_space_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """
    [معدل] تبني لوحة مفاتيح للمساحة الشخصية للمستخدم.
    """
    keyboard_layout = []
    root_containers = db.get_root_containers(user_id)

    # عرض الحاويات التي يملكها المستخدم فقط
    owned_containers = [c for c in root_containers if c['owner_user_id'] == user_id]

    for container in owned_containers:
        icon = "🗂️" if container['type'] == 'section' else "📁"
        container_button = InlineKeyboardButton(
            f"{icon} {container['name']}", 
            callback_data=f"container:{container['id']}"
        )
        controls_row = [
            InlineKeyboardButton("⚙️", callback_data=f"settings_container:{container['id']}"),
            InlineKeyboardButton("🔗", callback_data=f"share_menu_container:{container['id']}")
        ]
        keyboard_layout.append([container_button])
        keyboard_layout.append(controls_row)
        
    # أزرار إضافة جديدة
    control_buttons = [
        InlineKeyboardButton("➕ قسم", callback_data="new_container_root:section"),
        InlineKeyboardButton("➕ مجلد", callback_data="new_container_root:folder")
    ]
    keyboard_layout.append(control_buttons)
    
    keyboard_layout.append([InlineKeyboardButton("🔙 رجوع", callback_data="back_to_main")])
    
    return InlineKeyboardMarkup(keyboard_layout)

def build_shared_spaces_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """
    [معدل] تبني لوحة مفاتيح للمساحات المشتركة.
    """
    keyboard_layout = []
    shared_containers = db.get_shared_containers_for_user(user_id)

    for container in shared_containers:
        icon = "🗂️" if container['type'] == 'section' else "📁"
        # لا نعرض إلا الحاويات التي للمستخدم صلاحية مباشرة عليها في هذه القائمة
        container_button = InlineKeyboardButton(
            f"🔗 {icon} {container['name']}", 
            callback_data=f"container:{container['id']}"
        )
        # يمكن إضافة أزرار تحكم خاصة بالعناصر المشتركة هنا إذا لزم الأمر
        keyboard_layout.append([container_button])

    keyboard_layout.append([InlineKeyboardButton("🔙 رجوع للقائمة الرئيسية", callback_data="back_to_main")])
    
    return InlineKeyboardMarkup(keyboard_layout)

def build_container_view_keyboard(container_id: int, user_id: int) -> InlineKeyboardMarkup:
    """
    [موحد] يبني واجهة عرض الحاوية (قسم أو مجلد) بشكل ديناميكي.
    """
    keyboard_layout = []
    container_details = db.get_container_details(container_id)
    if not container_details:
        return InlineKeyboardMarkup([[InlineKeyboardButton("❌ خطأ: الحاوية غير موجودة", callback_data="my_space")]])

    permission = db.get_permission_level(user_id, container_details['type'], container_id)

    # عرض المحتويات الفرعية (أقسام ومجلدات)
    child_containers = db.get_child_containers(container_id)
    for child in child_containers:
        child_permission = db.get_permission_level(user_id, child['type'], child['id'])
        prefix = "" if child_permission == 'owner' else "🔗 "
        icon = "🗂️" if child['type'] == 'section' else "📁"
        
        child_button = InlineKeyboardButton(f"{prefix}{icon} {child['name']}", callback_data=f"container:{child['id']}")
        keyboard_layout.append([child_button])

        # أزرار التحكم الفرعية (للعهدة أو المدير)
        controls_row = []
        if child_permission == 'owner' or child_permission == 'admin':
            controls_row.append(InlineKeyboardButton("⚙️", callback_data=f"settings_container:{child['id']}"))
        if child_permission == 'owner':
            controls_row.append(InlineKeyboardButton("🔗", callback_data=f"share_menu_container:{child['id']}"))
        
        if controls_row:
            keyboard_layout.append(controls_row)

    # أزرار الإجراءات بناءً على نوع الحاوية الحالية
    action_buttons = []
    if permission in ['owner', 'admin']:
        if container_details['type'] == 'section':
            action_buttons.extend([
                InlineKeyboardButton("➕ قسم فرعي", callback_data=f"new_container_sub:{container_id}:section"),
                InlineKeyboardButton("➕ مجلد جديد", callback_data=f"new_container_sub:{container_id}:folder")
            ])
        elif container_details['type'] == 'folder':
            action_buttons.extend([
                InlineKeyboardButton("➕ إضافة عناصر", callback_data=f"add_items:{container_id}"),
                InlineKeyboardButton("📂 عرض المحتويات", callback_data=f"view_items:{container_id}:0")
            ])
    
    if action_buttons:
        keyboard_layout.append(action_buttons)

    # زر الرجوع
    back_button_data = db.get_back_navigation(user_id, container_id)
    keyboard_layout.append([InlineKeyboardButton("🔙 رجوع", callback_data=back_button_data)])
    
    return InlineKeyboardMarkup(keyboard_layout)


def build_item_view_keyboard(container_id: int, current_offset: int, total_items: int, page_size: int) -> InlineKeyboardMarkup:
    """
    [محدث] يبني زر التنقل لعرض العناصر التالية.
    """
    keyboard = []
    
    # Only show "Show next X items" button if there are more items
    if current_offset < total_items:
        remaining_items = total_items - current_offset
        button_text = f"عرض الـ{min(page_size, remaining_items)} عناصر التالية📥"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"view_items:{container_id}:{current_offset}")])
        
    keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data=f"container:{container_id}")])
    return InlineKeyboardMarkup(keyboard)


def build_settings_keyboard(container_id: int, user_id: int) -> InlineKeyboardMarkup:
    """
    [موحد] يبني قائمة الإعدادات للحاوية.
    """
    details = db.get_container_details(container_id)
    permission = db.get_permission_level(user_id, details['type'], container_id)

    keyboard = [
        [InlineKeyboardButton("✏️ إعادة تسمية", callback_data=f"rename_container:{container_id}")],
        [InlineKeyboardButton("🗑️ حذف", callback_data=f"delete_container_prompt:{container_id}")]
    ]
    # زر مغادرة العنصر للمستخدمين الذين ليسوا المالك
    if permission != 'owner':
         keyboard.append([InlineKeyboardButton("🚪 مغادرة", callback_data=f"leave_item_prompt_container:{container_id}")])

    keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data=f"container:{container_id}")])
    return InlineKeyboardMarkup(keyboard)


def build_share_menu_keyboard(container_id: int) -> InlineKeyboardMarkup:
    """
    [موحد] يبني قائمة المشاركة للحاوية.
    """
    keyboard = [
        [InlineKeyboardButton("👁️ رابط مشاهدة", callback_data=f"get_viewer_link:{container_id}")],
        [InlineKeyboardButton("👥 إضافة مدير", callback_data=f"get_admin_link:{container_id}")],
        [InlineKeyboardButton("🔙 رجوع", callback_data=f"container:{container_id}")]
    ]
    return InlineKeyboardMarkup(keyboard)


def main_menu_keyboard() -> InlineKeyboardMarkup:
    """
    [معدل] يبني القائمة الرئيسية.
    """
    keyboard = [
        [InlineKeyboardButton("👤 مساحتي الخاصة", callback_data="my_space")],
        [InlineKeyboardButton("🤝 المساحات المشتركة", callback_data="shared_spaces")]
    ]
    return InlineKeyboardMarkup(keyboard)


def back_button(callback_data: str) -> InlineKeyboardMarkup:
    """
    [جديد] ينشئ زر رجوع بسيط.
    """
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data=callback_data)]])