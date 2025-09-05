# handlers.py

import asyncio
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, Message
from telegram.ext import ContextTypes, ConversationHandler
from telegram.helpers import escape_markdown

import config
import database
from keyboards import build_main_menu_keyboard, build_section_view_keyboard
from constants import *
from database import (
    get_folder_details, rename_folder, get_section_details, rename_section,
    create_share_link, get_share_by_token, deactivate_share_link, grant_permission,
    get_permission_level, get_or_create_viewer_share_link, revoke_permission
)

# --- الدوال المساعدة ---
async def process_message_for_saving(message: Message) -> dict | None:
    file_type, file_obj = None, None
    if message.document: (file_type, file_obj) = ('document', message.document)
    elif message.video: (file_type, file_obj) = ('video', message.video)
    elif message.photo: (file_type, file_obj) = ('photo', message.photo[-1])
    elif message.audio: (file_type, file_obj) = ('audio', message.audio)
    if file_type and file_obj:
        fwd_msg = await message.forward(chat_id=config.STORAGE_CHANNEL_ID)
        fwd_file_obj = fwd_msg.document or fwd_msg.video or fwd_msg.photo[-1] or fwd_msg.audio
        return {'item_name': getattr(file_obj, 'file_name', f'ملف_{file_type}'), 'item_type': file_type, 'content': message.caption, 'file_unique_id': file_obj.file_unique_id, 'file_id': fwd_file_obj.file_id}
    elif message.text:
        return {'item_name': f"رسالة: {message.text[:20]}...", 'item_type': 'text', 'content': message.text, 'file_unique_id': None, 'file_id': None}
    return None

async def view_and_send_folder_contents(update: Update, context: ContextTypes.DEFAULT_TYPE, folder_id: int, offset: int = 0):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    permission = get_permission_level(user_id, 'folder', folder_id)
    can_delete = permission in ['owner', 'admin']

    items_page, total_items = database.get_items_paginated(folder_id, limit=PAGE_SIZE, offset=offset)
    
    if not items_page and offset == 0:
        await context.bot.send_message(chat_id, "هذا المجلد فارغ.")
        return

    if not items_page:
        await context.bot.send_message(chat_id, "لا توجد عناصر أخرى لعرضها.")
        return
        
    await context.bot.send_message(chat_id, f"إرسال {len(items_page)} عناصر (من {offset + 1} إلى {total_items})...")
    
    for item in items_page:
        try:
            reply_markup = None
            if can_delete:
                keyboard = [[InlineKeyboardButton("🗑️ حذف هذا العنصر", callback_data=f"delete_prompt:{item['item_record_id']}")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
            
            item_type = item['item_type']
            content = item['content']
            file_id = item['file_id']
            
            if item_type == 'text':
                await context.bot.send_message(chat_id=chat_id, text=content, reply_markup=reply_markup)
            elif item_type == 'document': await context.bot.send_document(chat_id=chat_id, document=file_id, caption=content, reply_markup=reply_markup)
            elif item_type == 'video': await context.bot.send_video(chat_id=chat_id, video=file_id, caption=content, reply_markup=reply_markup)
            elif item_type == 'photo': await context.bot.send_photo(chat_id=chat_id, photo=file_id, caption=content, reply_markup=reply_markup)
            elif item_type == 'audio': await context.bot.send_audio(chat_id=chat_id, audio=file_id, caption=content, reply_markup=reply_markup)
            
            await asyncio.sleep(0.5)
        except Exception as e:
            await context.bot.send_message(chat_id, f"لم يتم إرسال العنصر '{item['item_name']}'. الخطأ: {e}")
            
    new_offset = offset + len(items_page)
    if new_offset < total_items:
        next_keyboard = [[InlineKeyboardButton(f"📥 عرض الـ {min(PAGE_SIZE, total_items - new_offset)} عناصر التالية", callback_data=f"view_files:{folder_id}:{new_offset}")]]
        await context.bot.send_message(chat_id, "لا يزال هناك المزيد من العناصر.", reply_markup=InlineKeyboardMarkup(next_keyboard))
    else:
        await context.bot.send_message(chat_id, "تم عرض كل العناصر في هذا المجلد.")

# --- دوال الواجهة الرئيسية والتصفح ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    database.add_user_if_not_exists(user_id=user.id, first_name=user.first_name)

    if context.args:
        token = context.args[0]
        share = database.get_share_by_token(token)
        
        if share and not share['is_used']:
            content_type = share['content_type']
            content_id = share['content_id']
            permission_level = share['link_type']

            database.grant_permission(user.id, content_type, content_id, permission_level)

            if permission_level == 'admin':
                database.deactivate_share_link(token)

            item_name = ""
            if content_type == 'section':
                item_details = database.get_section_details(content_id)
                item_name = item_details['section_name'] if item_details else ''
            elif content_type == 'folder':
                item_details = database.get_folder_details(content_id)
                item_name = item_details['folder_name'] if item_details else ''

            await update.message.reply_text(
                f"أهلاً بك! لقد تم منحك صلاحيات '{permission_level}' على {content_type} \"{item_name}\" بنجاح."
            )
        else:
            await update.message.reply_text("عذرًا، هذا الرابط غير صالح أو تم استخدامه بالفعل.")

    keyboard = build_main_menu_keyboard(user.id)
    # [تعديل] تم تهريب النقاط وتغيير النص ليتوافق مع MarkdownV2
    reply_text = """*مرحبًا بك في TeleSpace* \.

مساحتك الخاصة على تيليجرام لبناء بيئتك المثالية وتخصيصها بنفسك ، وتخزين كل ما يهمك من المحتوى \(ملفات، رسائل، صور، وسائط\) بطريقة منظمة ومرنة \.

🗂️ يمكنك إنشاء الأقسام والأقسام الفرعية \.
📂 يمكنك إنشاء المجلدات وتخزين ملفاتك فيها \."""
    
    if update.callback_query:
        try: 
            # [تعديل] تغيير parse_mode إلى MarkdownV2
            await update.callback_query.message.edit_text(reply_text, reply_markup=keyboard, parse_mode='MarkdownV2')
        except Exception: pass
    else:
        # [تعديل] تغيير reply_html إلى reply_text مع parse_mode='MarkdownV2'
        await update.message.reply_text(reply_text, reply_markup=keyboard, parse_mode='MarkdownV2')
        
    return ConversationHandler.END

async def button_press_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()
    data = query.data

    if data.startswith("section:"):
        section_id = int(data.split(':')[1])
        permission = database.get_permission_level(user_id, 'section', section_id)

        if permission is None:
            await query.answer("ليس لديك صلاحية للوصول إلى هذا القسم.", show_alert=True)
            return

        section_details = database.get_section_details(section_id)
        section_name = section_details['section_name'] if section_details else "غير مسمى"
        
        text = ""
        if permission in ['owner', 'admin']:
            text = f"""📂 *قسم: {escape_markdown(section_name, version=2)}*
            
            تصفح المحتويات وأضف أقسام/مجلدات أو استخدم `⚙️` للإدارة و `🔗` للمشاركة\."""
        else: # viewer
            text = f"🔗 *أنت تتصفح: {escape_markdown(section_name, version=2)}*"

        keyboard = build_section_view_keyboard(section_id, user_id)
        await query.message.edit_text(text, reply_markup=keyboard, parse_mode='MarkdownV2')

    elif data == "back_to_main":
        await start(update, context)

    elif data.startswith("folder:"):
        folder_id = int(data.split(':')[1])
        permission = database.get_permission_level(user_id, 'folder', folder_id)

        if permission is None:
            await query.answer("ليس لديك صلاحية للوصول إلى هذا المجلد.", show_alert=True)
            return

        folder_details = database.get_folder_details(folder_id)
        folder_name = folder_details['folder_name'] if folder_details else "غير مسمى"
        section_id = folder_details['section_id'] if folder_details else None

        text = ""
        keyboard_layout = []
        
        prefix = "🔗 " if permission in ['admin', 'viewer'] else ""
        view_contents_button_text = f"{prefix}📂 عرض المحتويات"
        view_contents_button = InlineKeyboardButton(view_contents_button_text, callback_data=f"view_files:{folder_id}:0")

        if permission in ['owner', 'admin']:
            text = f"""📁 *مجلد: {escape_markdown(folder_name, version=2)}*
            
            اختر الإجراء المطلوب\."""
            keyboard_layout.append([view_contents_button])
            keyboard_layout.append([InlineKeyboardButton("➕ إضافة عناصر", callback_data=f"add_files_to:{folder_id}")])
        else: # viewer
            text = f"🔗 *مجلد: {escape_markdown(folder_name, version=2)}*"
            keyboard_layout.append([view_contents_button])

        back_button_data = f"section:{section_id}" if section_id else "back_to_main"
        keyboard_layout.append([InlineKeyboardButton("🔙 عودة", callback_data=back_button_data)])
        
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard_layout), parse_mode='MarkdownV2')

    elif data.startswith("share_menu_"):
        parts = data.split(':')
        content_type = parts[0].split('_')[2]
        content_id = int(parts[1])
        
        permission = database.get_permission_level(user_id, content_type, content_id)

        item_name = ""
        text = ""
        back_button_data = ""

        if content_type == 'section':
            details = database.get_section_details(content_id)
            item_name = details['section_name'] if details else ""
            text = f"🔗 *إعدادات مشاركة القسم: {escape_markdown(item_name, version=2)}*"
            back_button_data = f"section:{content_id}"
        else: # folder
            details = database.get_folder_details(content_id)
            item_name = details['folder_name'] if details else ""
            text = f"🔗 *إعدادات مشاركة المجلد: {escape_markdown(item_name, version=2)}*"
            back_button_data = f"folder:{content_id}" # Go back to folder view

        keyboard = [
            [InlineKeyboardButton("🤝 مشاركة (مشاهدة)", callback_data=f"generate_viewer_link:{content_type}:{content_id}")]
        ]

        if permission == 'owner':
            keyboard.append([InlineKeyboardButton("👑 إضافة مشرف", callback_data=f"generate_admin_link:{content_type}:{content_id}")])

        keyboard.append([InlineKeyboardButton("🔙 عودة", callback_data=back_button_data)])
        
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='MarkdownV2')

    elif data.startswith("generate_viewer_link:"):
        parts = data.split(':')
        content_type = parts[1]
        content_id = int(parts[2])
        token = database.get_or_create_viewer_share_link(user_id, content_type, content_id)
        bot_username = (await context.bot.get_me()).username
        share_link = f"https://t.me/{bot_username}?start={token}"
        text = f"""رابط مباشر لمشاركة هذا القسم/المجلد مع الجميع\:
        `{share_link}`"""
        await query.message.edit_text(text, parse_mode='MarkdownV2')

    elif data.startswith("get_viewer_link:"):
        parts = query.data.split(':')
        content_type = parts[1]
        content_id = int(parts[2])

        owner_id = None
        if content_type == 'section':
            details = database.get_section_details(content_id)
            if details: owner_id = details['user_id']
        elif content_type == 'folder':
            details = database.get_folder_details(content_id)
            if details: owner_id = details['owner_user_id']

        if not owner_id:
            await query.edit_message_text("عذرًا، حدث خطأ أثناء العثور على مالك العنصر.")
            return

        token = database.get_or_create_viewer_share_link(owner_id, content_type, content_id)
        bot_username = (await context.bot.get_me()).username
        share_link = f"https://t.me/{bot_username}?start={token}"
        
        text = f"""🔗 *الرابط الدائم للمشاهدة*

هذا هو الرابط الذي يمكنك مشاركته مع الآخرين لمنحهم صلاحية المشاهدة\.

`{share_link}`"""
        
        keyboard = [[InlineKeyboardButton("🔙 عودة إلى القائمة الرئيسية", callback_data="back_to_main")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='MarkdownV2')

    elif data.startswith("generate_admin_link:"):
        parts = data.split(':')
        content_type = parts[1]
        content_id = int(parts[2])
        token = database.create_share_link(user_id, content_type, content_id, 'admin')
        bot_username = (await context.bot.get_me()).username
        share_link = f"https://t.me/{bot_username}?start={token}"
        text = f"""رابط دعوة مشرف يستخدم لمرة واحدة جاهز للمشاركة\:
        `{share_link}`"""
        await query.message.edit_text(text, parse_mode='MarkdownV2')

    elif data.startswith("settings_section:"):
        section_id = int(data.split(':')[1])
        section_details = get_section_details(section_id)
        section_name = section_details['section_name'] if section_details else ""
        parent_id = section_details['parent_section_id'] if section_details else None
        back_button_data = f"section:{parent_id}" if parent_id else "back_to_main"
        
        text = f"⚙️ *إعدادات القسم: {escape_markdown(section_name, version=2)}*"

        keyboard = [
            [InlineKeyboardButton("✏️ تعديل الاسم", callback_data=f"rename_section_prompt:{section_id}")],
            [InlineKeyboardButton("🗑️ حذف القسم بالكامل", callback_data=f"delete_section_prompt:{section_id}")],
            [InlineKeyboardButton("🔙 عودة", callback_data=back_button_data)]
        ]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='MarkdownV2')

    elif data.startswith("settings_folder:"):
        folder_id = int(data.split(':')[1])
        folder_details = get_folder_details(folder_id)
        folder_name = folder_details['folder_name'] if folder_details else ""
        
        back_button_data = f"folder:{folder_id}"
        
        text = f"⚙️ *إعدادات المجلد: {escape_markdown(folder_name, version=2)}*"

        keyboard = [
            [InlineKeyboardButton("✏️ تعديل الاسم", callback_data=f"rename_folder_prompt:{folder_id}")],
            [InlineKeyboardButton("🔥 حذف كل المحتويات فقط", callback_data=f"delete_all_prompt:{folder_id}")],
            [InlineKeyboardButton("🗑️ حذف المجلد بالكامل", callback_data=f"delete_folder_prompt:{folder_id}")],
            [InlineKeyboardButton("🔙 عودة", callback_data=back_button_data)] 
        ]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='MarkdownV2')


    elif data.startswith("view_files:"):
        _, folder_id, offset = data.split(':')
        await view_and_send_folder_contents(update, context, int(folder_id), int(offset))
    
    elif data.startswith("delete_prompt:"):
        item_id = int(data.split(':')[1])
        text = "⚠️ هل أنت متأكد من أنك تريد حذف هذا العنصر بشكل دائم؟"
        keyboard = [[InlineKeyboardButton("✅ نعم، احذف", callback_data=f"delete_confirm:{item_id}"), InlineKeyboardButton("❌ لا، تراجع", callback_data="delete_cancel")]]
        await context.bot.send_message(chat_id=update.effective_chat.id, text=text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif data.startswith("delete_confirm:"):
        item_id = int(data.split(':')[1])
        database.delete_item(item_id)
        await query.message.edit_text(text="✅ تم حذف العنصر بنجاح.")
    
    elif data == "delete_cancel":
        await query.message.delete() 
        
    elif data.startswith("delete_folder_prompt:"):
        folder_id = int(data.split(':')[1])
        text = "⚠️ <b>تحذير!</b>\nهل تريد بالتأكيد حذف هذا المجلد <b>وكل محتوياته</b> بشكل دائم؟"
        keyboard = [[ 
            InlineKeyboardButton("✅ نعم، احذف المجلد", callback_data=f"delete_folder_confirm:{folder_id}"),
            InlineKeyboardButton("❌ لا، تراجع", callback_data=f"settings_folder:{folder_id}")
        ]]
        await query.message.edit_text(text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')

    elif data.startswith("delete_folder_confirm:"):
        folder_id = int(data.split(':')[1])
        database.delete_folder(folder_id)
        await query.answer("✅ تم حذف المجلد بنجاح!")
        await start(update, context)

    elif data.startswith("delete_section_prompt:"):
        section_id = int(data.split(':')[1])
        text = "🔥 <b>تحذير خطير جدا!</b>\nهل تريد بالتأكيد حذف هذا القسم <b>وكل ما بداخله</b> بشكل دائم؟"
        keyboard = [[ 
            InlineKeyboardButton("🔥 نعم، متأكد تمامًا", callback_data=f"delete_section_confirm:{section_id}"),
            InlineKeyboardButton("❌ لا، تراجع", callback_data=f"settings_section:{section_id}")
        ]]
        await query.message.edit_text(text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')

    elif data.startswith("delete_section_confirm:"):
        section_id = int(data.split(':')[1])
        database.delete_section_recursively(section_id)
        await query.answer("✅ تم حذف القسم وكل محتوياته بنجاح!")
        await start(update, context)

    elif data.startswith("delete_all_prompt:"):
        folder_id = int(data.split(':')[1])
        text = "⚠️ <b>تحذير!</b>\nهل تريد بالتأكيد حذف <b>كل محتويات</b> هذا المجلد (سيبقى المجلد فارغًا)؟"
        keyboard = [[ 
            InlineKeyboardButton("✅ نعم، احذف المحتويات", callback_data=f"delete_all_confirm:{folder_id}"),
            InlineKeyboardButton("❌ لا، تراجع", callback_data=f"settings_folder:{folder_id}")
        ]]
        await query.message.edit_text(text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
    
    elif data.startswith("delete_all_confirm:"):
        folder_id = int(data.split(':')[1])
        deleted_count = database.delete_all_items_in_folder(folder_id)
        await query.message.edit_text(f"✅ تم حذف {deleted_count} عنصر بنجاح. المجلد الآن فارغ.")
    
    elif data.startswith("leave_item_prompt_"):
        parts = data.split(':')
        content_type = parts[0].split('_')[-1]
        content_id = int(parts[1])

        text = "⚠️ هل أنت متأكد من أنك تريد مغادرة هذا العنصر المشترك؟ ستتم إزالته من قائمتك."
        keyboard = [[ 
            InlineKeyboardButton("✅ نعم، مغادرة", callback_data=f"leave_item_confirm:{content_type}:{content_id}"),
            InlineKeyboardButton("❌ تراجع", callback_data="back_to_main")
        ]]
        await query.message.edit_text(text=text, reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("leave_item_confirm:"):
        parts = data.split(':')
        content_type = parts[1]
        content_id = int(parts[2])

        database.revoke_permission(user_id, content_type, content_id)

        await query.answer("✅ تمت مغادرة العنصر بنجاح!", show_alert=True)
        await start(update, context)

# --- دوال المحادثات ---
async def new_section_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id

    parent_id = int(data.split(':')[1]) if data.startswith("new_section_sub:") else None
    context.user_data['parent_section_id'] = parent_id

    # --- [تعديل وراثة الملكية] ---
    owner_id = user_id
    if parent_id:
        parent_section_details = database.get_section_details(parent_id)
        if parent_section_details:
            owner_id = parent_section_details['user_id']
    context.user_data['owner_id'] = owner_id
    # --- نهاية التعديل ---

    await query.message.edit_text(text="يرجى إرسال اسم القسم الجديد:")
    return AWAITING_SECTION_NAME

async def receive_section_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    section_name = update.message.text
    parent_id = context.user_data.get('parent_section_id')
    # --- [تعديل وراثة الملكية] ---
    owner_id = context.user_data.get('owner_id')
    # --- نهاية التعديل ---

    database.add_section(user_id=owner_id, section_name=section_name, parent_section_id=parent_id)
    await update.message.reply_text(f"✅ تم إنشاء قسم '{section_name}' بنجاح!")
    context.user_data.clear()
    await start(update, context)
    return ConversationHandler.END

async def new_folder_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id

    parent_section_id = int(data.split(':')[1]) if data.startswith("new_folder_in_sec:") else None
    context.user_data['parent_section_id_for_folder'] = parent_section_id

    # --- [تعديل وراثة الملكية] ---
    owner_id = user_id
    if parent_section_id:
        parent_section_details = database.get_section_details(parent_section_id)
        if parent_section_details:
            owner_id = parent_section_details['user_id']
    context.user_data['owner_id'] = owner_id
    # --- نهاية التعديل ---

    await query.message.edit_text(text="يرجى إرسال اسم المجلد الجديد:")
    return AWAITING_FOLDER_NAME

async def receive_folder_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    folder_name = update.message.text
    parent_section_id = context.user_data.get('parent_section_id_for_folder')
    # --- [تعديل وراثة الملكية] ---
    owner_id = context.user_data.get('owner_id')
    # --- نهاية التعديل ---

    database.add_folder(owner_user_id=owner_id, folder_name=folder_name, section_id=parent_section_id)
    await update.message.reply_text(f"✅ تم إنشاء مجلد '{folder_name}' بنجاح!")
    context.user_data.clear(); await start(update, context); return ConversationHandler.END

async def add_files_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query; await query.answer(); folder_id = int(query.data.split(':')[1])
    context.user_data['target_folder_id'] = folder_id; context.user_data['files_to_add_buffer'] = []
    await query.message.edit_text(text="أنت الآن في وضع الإضافة.\nأرسل أي عدد من العناصر. عندما تنتهي، أرسل كلمة `حفظ`.")
    return AWAITING_FILES_FOR_UPLOAD

async def collect_files_and_save(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    message_text = update.message.text
    if message_text and message_text.lower() == "حفظ":
        target_folder_id = context.user_data.get('target_folder_id')
        message_buffer = context.user_data.get('files_to_add_buffer', [])
        if not message_buffer:
            await update.message.reply_text("لم يتم إرسال أي عناصر للحفظ."); context.user_data.clear(); await start(update, context); return ConversationHandler.END
        await update.message.reply_text(f"جاري حفظ {len(message_buffer)} عنصر...")
        count = 0
        for msg in message_buffer:
            item_info = await process_message_for_saving(msg)
            if item_info:
                database.add_item(
                    folder_id=target_folder_id, item_name=item_info['item_name'], item_type=item_info['item_type'],
                    content=item_info['content'], file_unique_id=item_info['file_unique_id'], file_id=item_info['file_id']
                )
                count += 1
        await update.message.reply_text(f"✅ تم حفظ {count} عنصر بنجاح!")
        context.user_data.clear(); await start(update, context); return ConversationHandler.END
    else:
        context.user_data.get('files_to_add_buffer', []).append(update.message)
        await update.message.reply_text("👍 تم الاستلام. أرسل المزيد أو أرسل `حفظ`.")
        return AWAITING_FILES_FOR_UPLOAD

async def rename_folder_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    folder_id = int(query.data.split(':')[1])
    context.user_data['folder_to_rename'] = folder_id
    
    folder_details = get_folder_details(folder_id)
    if folder_details:
        folder_name = escape_markdown(folder_details['folder_name'], version=2)
        await query.message.edit_text(f"الاسم الحالي للمجلد هو: <b>{folder_name}</b>\n\nالرجاء إرسال الاسم الجديد.", parse_mode='HTML')
        return AWAITING_RENAME_INPUT
    else:
        await query.message.edit_text("عذرًا، لم يتم العثور على المجلد.")
        context.user_data.clear()
        return ConversationHandler.END

async def receive_new_folder_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    new_name = update.message.text
    folder_id = context.user_data.get('folder_to_rename')
    
    if not folder_id:
        await update.message.reply_text("حدث خطأ ما. يرجى المحاولة مرة أخرى.")
        context.user_data.clear()
        await start(update, context)
        return ConversationHandler.END

    rename_folder(folder_id, new_name)
    
    await update.message.reply_text(f"✅ تم تغيير اسم المجلد بنجاح إلى: {new_name}")
    
    context.user_data.clear()
    await start(update, context)
    return ConversationHandler.END

async def rename_section_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    section_id = int(query.data.split(':')[1])
    context.user_data['section_to_rename'] = section_id
    
    section_details = get_section_details(section_id)
    if section_details:
        section_name = escape_markdown(section_details['section_name'], version=2)
        await query.message.edit_text(f"الاسم الحالي للقسم هو: <b>{section_name}</b>\n\nالرجاء إرسال الاسم الجديد.", parse_mode='HTML')
        return AWAITING_RENAME_INPUT
    else:
        await query.message.edit_text("عذرًا، لم يتم العثور على القسم.")
        context.user_data.clear()
        return ConversationHandler.END

async def receive_new_section_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    new_name = update.message.text
    section_id = context.user_data.get('section_to_rename')
    
    if not section_id:
        await update.message.reply_text("حدث خطأ ما. يرجى المحاولة مرة أخرى.")
        context.user_data.clear()
        await start(update, context)
        return ConversationHandler.END

    rename_section(section_id, new_name)
    
    await update.message.reply_text(f"✅ تم تغيير اسم القسم بنجاح إلى: {new_name}")
    
    context.user_data.clear()
    await start(update, context)
    return ConversationHandler.END

async def cancel_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text("تم إلغاء العملية.")
    await start(update, context)
    return ConversationHandler.END
