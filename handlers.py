# handlers.py

import asyncio
from telegram import Update, InlineKeyboardMarkup, Message, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler
from telegram.helpers import escape_markdown

import config
import database as db
import keyboards as kb
from constants import *

# --- Helper Functions ---

async def return_to_my_space(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """[معدل] ينقل المستخدم إلى مساحته الخاصة باستخدام الدوال الجديدة."""
    keyboard = kb.build_my_space_keyboard(update.effective_user.id)
    text = """
    👤 *مساحتك الخاصة*

    تصفح أقسامك ومجلداتك، أو أنشئ جديدًا\.
    """
    if update.callback_query:
        await update.callback_query.message.edit_text(text, reply_markup=keyboard, parse_mode='MarkdownV2')
    else:
        await update.message.reply_text(text, reply_markup=keyboard, parse_mode='MarkdownV2')

async def return_to_shared_spaces(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """[معدل] ينقل المستخدم إلى عرض المساحات المشتركة."""
    keyboard = kb.build_shared_spaces_keyboard(update.effective_user.id)
    text = """
    🤝 *المساحة المشتركة*

    تصفح الأقسام والمجلدات التي تمت مشاركتها معك\.
    """
    if update.callback_query:
        await update.callback_query.message.edit_text(text, reply_markup=keyboard, parse_mode='MarkdownV2')
    else:
        await update.message.reply_text(text, reply_markup=keyboard, parse_mode='MarkdownV2')

async def show_container(update: Update, context: ContextTypes.DEFAULT_TYPE, container_id: int):
    """[جديد ومصحح] يعرض محتويات حاوية معينة (قسم أو مجلد)."""
    user_id = update.effective_user.id
    details = db.get_container_details(container_id)

    if not details:
        if update.callback_query:
            await update.callback_query.answer("القسم أو المجلد غير موجود!", show_alert=False)
        return await return_to_my_space(update, context)

    permission = db.get_permission_level(user_id, details['type'], container_id)
    if permission is None:
        if update.callback_query:
            await update.callback_query.answer("ليس لديك صلاحية الوصول.", show_alert=False)
        else:
            await update.message.reply_text("ليس لديك صلاحية الوصول.")
        return

    icon = "🗂️" if details['type'] == 'section' else "📁"
    
    if permission in ['owner', 'admin']:
        text = f"{icon} *{escape_markdown(details['name'], version=2)}*\n\nتصفح، أضف، أو قم بإدارة المحتويات\."
    else:  # viewer
        text = f"{icon} *{escape_markdown(details['name'], version=2)}*\n\nتصفح المحتويات\."
    
    keyboard = kb.build_container_view_keyboard(container_id, user_id)

    if update.callback_query:
        await update.callback_query.message.edit_text(text, reply_markup=keyboard, parse_mode='MarkdownV2')
    else:
        await update.message.reply_text(text, reply_markup=keyboard, parse_mode='MarkdownV2')

async def process_message_for_saving(message: Message) -> dict | None:
    """[بدون تغيير] يعالج الرسائل لتحويلها إلى بيانات قابلة للحفظ."""
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

async def view_and_send_container_contents(update: Update, context: ContextTypes.DEFAULT_TYPE, container_id: int, offset: int = 0):
    """[معدل] يعرض ويرسل محتويات حاوية (مجلد)."""
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    if not db.container_exists(container_id):
        await context.bot.send_message(chat_id, "⚠️ عذرًا، يبدو أن هذا المجلد قد تم حذفه بالفعل.")
        return

    permission = db.get_permission_level(user_id, 'folder', container_id)
    can_delete = permission in ['owner', 'admin']

    items_page, total_items = db.get_items_paginated(container_id, limit=PAGE_SIZE, offset=offset)
    
    if not items_page and offset == 0:
        await context.bot.send_message(chat_id, "📁 المجلد فارغ.", reply_markup=kb.back_button(f"container:{container_id}"))
        return

    if not items_page and offset > 0:
        await context.bot.send_message(chat_id, "✅ تم عرض كل العناصر.", reply_markup=kb.back_button(f"container:{container_id}"))
        return
        
    await context.bot.send_message(chat_id, f"📥 جاري إرسال {len(items_page)} عنصر...")
    
    for item in items_page:
        try:
            reply_markup = None
            if can_delete:
                reply_markup = kb.InlineKeyboardMarkup([[kb.InlineKeyboardButton("🗑️ حذف هذا العنصر", callback_data=f"delete_item_prompt:{item['item_record_id']}:{container_id}")]])
            
            item_type = item['item_type']
            content = item['content']
            file_id = item['file_id']
            
            if item_type == 'text': await context.bot.send_message(chat_id=chat_id, text=content, reply_markup=reply_markup)
            else: # Files
                send_map = {
                    'document': context.bot.send_document,
                    'video': context.bot.send_video,
                    'photo': context.bot.send_photo,
                    'audio': context.bot.send_audio
                }
                kwargs = {'caption': content, 'reply_markup': reply_markup, item_type: file_id}
                await send_map[item_type](chat_id=chat_id, **kwargs)
            
            await asyncio.sleep(0.5)
        except Exception as e:
            await context.bot.send_message(chat_id, f"⚠️ تعذر إرسال: {item['item_name']}\nالخطأ: {e}")
            
    new_offset = offset + len(items_page)
    
    if new_offset < total_items:
        keyboard = kb.build_item_view_keyboard(container_id, new_offset, total_items, PAGE_SIZE)
        await context.bot.send_message(chat_id, "👇 توجد عناصر أخرى.", reply_markup=keyboard)
    else:
        await context.bot.send_message(chat_id, "✅ تم عرض كل العناصر.", reply_markup=kb.back_button(f"container:{container_id}"))


# --- Main Interface and Browsing ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """[معدل] يبدأ البوت ويعالج روابط المشاركة."""
    context.user_data.clear() 
    user = update.effective_user
    db.add_user_if_not_exists(user_id=user.id, first_name=user.first_name)

    if context.args:
        token = context.args[0]
        share = db.get_share_by_token(token)
        
        if share and not share['is_used']:
            details = db.get_container_details(share['content_id'])
            if details:
                current_permission = db.get_permission_level(user.id, details['type'], share['content_id'])
                is_already_privileged = current_permission in ['owner', 'admin']
                container_type_ar = "قسم" if details['type'] == 'section' else "مجلد"

                if share['link_type'] == 'admin' and is_already_privileged:
                    await update.message.reply_text(f"👍 أنت بالفعل مشرف لـ {container_type_ar} '{details['name']}'.")
                else:
                    db.grant_permission(user.id, details['type'], share['content_id'], share['link_type'])
                    if share['link_type'] == 'admin':
                        db.deactivate_share_link(token, user.id)
                    
                    await update.message.reply_text(
                        f"✅ لقد حصلت على صلاحية وصول إلى {container_type_ar} '{details['name']}'.\n\nيمكنك تصفحه في المساحات المشتركة."
                    )
            else:
                 await update.message.reply_text("⚠️ عذرًا، المحتوى المشار إليه لم يعد موجودًا.")
        else:
            await update.message.reply_text("⚠️ عذرًا، الرابط غير صالح أو مستخدم.")

    first_name = escape_markdown(user.first_name, version=2)
    keyboard = kb.main_menu_keyboard()
    reply_text = f"""
مرحبًا {first_name}، يسعدنا تواجدك في *TeleSpace* \!

مساحتك الرقمية على Telegram لتحويل الفوضى إلى مساحة عمل منظمة \.

🗂️ *نظّم* أفكارك ومشاريعك\.
💾 *احفظ* ملفاتك ورسائلك المهمة\.
🤝 *شارك* محتواك بسهولة وأمان\.
    
استكشف مساحتك أو ابدأ بتصفح ما شاركه الآخرون معك\.
"""
    
    if update.callback_query:
        await update.callback_query.message.edit_text(reply_text, reply_markup=keyboard, parse_mode='MarkdownV2')
    else:
        await update.message.reply_text(reply_text, reply_markup=keyboard, parse_mode='MarkdownV2')
        
    return ConversationHandler.END

async def button_press_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """[معدل] الموجه الرئيسي لضغطات الأزرار."""
    query = update.callback_query
    data = query.data
    user_id = query.from_user.id
    db.update_user_last_active(user_id) # Update user activity

    # --- Basic Navigation ---
    if data == "my_space": await return_to_my_space(update, context)
    elif data == "shared_spaces": await return_to_shared_spaces(update, context)
    elif data == "back_to_main": await start(update, context)
    elif data.startswith("container:"): await show_container(update, context, int(data.split(':')[1]))
    
    # --- Content Viewing ---
    elif data.startswith("view_items:"):
        _, container_id, offset = data.split(':')
        await view_and_send_container_contents(update, context, int(container_id), int(offset))

    # --- Settings ---
    elif data.startswith("settings_container:"):
        container_id = int(data.split(':')[1])
        if not db.container_exists(container_id):
            await query.answer("⚠️ عذرًا، يبدو أن هذا العنصر قد تم حذفه بالفعل.", show_alert=False)
            return await query.message.delete()
        details = db.get_container_details(container_id)
        text = f"⚙️ *إعدادات: {escape_markdown(details['name'], version=2)}*\n\."
        keyboard = kb.build_settings_keyboard(container_id, user_id)
        await query.message.edit_text(text, reply_markup=keyboard, parse_mode='MarkdownV2')

    # --- Sharing ---
    elif data.startswith("share_menu_container:"):
        container_id = int(data.split(':')[1])
        if not db.container_exists(container_id):
            await query.answer("⚠️ عذرًا، يبدو أن هذا العنصر قد تم حذفه بالفعل.", show_alert=False)
            return await query.message.delete()
        details = db.get_container_details(container_id)
        text = f"🔗 *مشاركة: {escape_markdown(details['name'], version=2)}*\n\."
        keyboard = kb.build_share_menu_keyboard(container_id)
        await query.message.edit_text(text, reply_markup=keyboard, parse_mode='MarkdownV2')

    elif data.startswith(("get_viewer_link:", "get_admin_link:")):
        parts = data.split(':')
        link_type = 'viewer' if parts[0] == "get_viewer_link" else 'admin'
        container_id = int(parts[1])
        if not db.container_exists(container_id):
            await query.answer("⚠️ عذرًا، يبدو أن هذا العنصر قد تم حذفه بالفعل.", show_alert=False)
            return await query.message.delete()
        details = db.get_container_details(container_id)
        
        if link_type == 'viewer':
            token = db.get_or_create_viewer_share_link(user_id, details['type'], container_id)
            title = "رابط المشاركة \(مشاهدة فقط\)\n_انقر نقرة واحدة لنسخه_"
        else: # admin
            token = db.create_share_link(user_id, details['type'], container_id, 'admin')
            title = "رابط دعوة مشرف \(يستخدم لمرة واحدة\)\n_انقر نقرة واحدة لنسخه_"

        bot_username = (await context.bot.get_me()).username
        share_link = f"https://t.me/{bot_username}?start={token}"
        text = f"✅ {title}:\n\n`{share_link}`"
        await query.message.edit_text(text, reply_markup=kb.back_button(f"share_menu_container:{container_id}"), parse_mode='MarkdownV2')

    # --- Deletion ---
    elif data.startswith("delete_container_prompt:"):
        container_id = int(data.split(':')[1])
        details = db.get_container_details(container_id)
        if not details:
            await query.answer("⚠️ عذرًا، يبدو أن هذا العنصر قد تم حذفه بالفعل.", show_alert=False)
            return await query.message.delete()

        container_type_ar = "القسم" if details['type'] == 'section' else "المجلد"
        text = f"⚠️ تحذير !\nسيتم حذف هذا {container_type_ar} وكل محتوياته نهائيًا. هل أنت متأكد؟"
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔥 نعم، متأكد", callback_data=f"delete_container_confirm:{container_id}"), InlineKeyboardButton("❌ تراجع", callback_data=f"settings_container:{container_id}")]])
        await query.message.edit_text(text, reply_markup=keyboard)

    elif data.startswith("delete_container_confirm:"):
        container_id = int(data.split(':')[1])
        
        if not db.container_exists(container_id):
            await query.answer("⚠️ عذرًا، يبدو أن هذا العنصر قد تم حذفه بالفعل.", show_alert=False)
            return await query.message.delete()

        parent_id = db.get_parent_container_id(container_id)
        db.delete_container_recursively(container_id, user_id)
        await query.answer("✅ تم الحذف بنجاح.", show_alert=False)
        
        if parent_id and db.container_exists(parent_id):
            await show_container(update, context, parent_id)
        else:
            await return_to_my_space(update, context)

    elif data.startswith("delete_item_prompt:"):
        _, item_id, container_id = data.split(':')
        item_id = int(item_id)
        
        if not db.item_exists(item_id):
            await query.answer("العنصر لم يعد موجودًا!", show_alert=False)
            return
        item_details = db.get_item_details(item_id)

        text = "⚠️ هل أنت متأكد من حذف هذا العنصر؟"
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ نعم", callback_data=f"delete_item_confirm:{item_id}:{container_id}"),
                InlineKeyboardButton("❌ لا", callback_data=f"undo_delete_item:{item_id}:{container_id}")
            ]
        ])
        
        try:
            if item_details['item_type'] == 'text':
                await query.message.edit_text(text, reply_markup=keyboard)
            else:
                await query.message.edit_caption(caption=text, reply_markup=keyboard)
        except Exception as e:
            print(f"Error editing message for delete prompt: {e}")
            await query.answer("حدث خطأ أثناء تحرير الرسالة.", show_alert=False)

    elif data.startswith("undo_delete_item:"):
        _, item_id, container_id = data.split(':')
        item_id = int(item_id)

        if not db.item_exists(item_id):
            await query.answer("العنصر لم يعد موجودًا!", show_alert=False)
            await query.message.edit_text("تم حذف هذا العنصر بالفعل.")
            return
        item_details = db.get_item_details(item_id)

        reply_markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("🗑️ حذف هذا العنصر", callback_data=f"delete_item_prompt:{item_id}:{container_id}")]
        ])

        try:
            if item_details['item_type'] == 'text':
                await query.message.edit_text(item_details['content'], reply_markup=reply_markup)
            else:
                await query.message.edit_caption(caption=item_details['content'], reply_markup=reply_markup)
        except Exception as e:
            print(f"Error restoring message: {e}")
            await query.answer("حدث خطأ أثناء استعادة الرسالة.", show_alert=False)

    elif data.startswith("delete_item_confirm:"):
        _, item_id_str, container_id_str = data.split(':')
        item_id = int(item_id_str)

        if not db.item_exists(item_id):
            await query.answer("⚠️ عذرًا، يبدو أن هذا العنصر قد تم حذفه بالفعل.", show_alert=False)
            return await query.message.delete()

        db.delete_item(item_id, user_id)
        await query.answer("✅ تم حذف العنصر بنجاح.", show_alert=False)
        await query.message.delete()

    # --- Leaving Shared Items ---
    elif data.startswith("leave_item_prompt_container:"):
        container_id = int(data.split(':')[1])
        if not db.container_exists(container_id):
            await query.answer("⚠️ عذرًا، يبدو أن هذا العنصر قد تم حذفه بالفعل.", show_alert=False)
            return await query.message.delete()
        details = db.get_container_details(container_id)
        container_type_ar = "القسم" if details['type'] == 'section' else "المجلد"
        text = f"⚠️ هل أنت متأكد أنك تريد مغادرة هذا {container_type_ar} المشترك؟"
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("✅ نعم، مغادرة", callback_data=f"leave_item_confirm_container:{container_id}"), InlineKeyboardButton("❌ تراجع", callback_data=f"container:{container_id}")]])
        await query.message.edit_text(text, reply_markup=keyboard)

    elif data.startswith("leave_item_confirm_container:"):
        container_id = int(data.split(':')[1])
        if not db.container_exists(container_id):
            await query.answer("⚠️ عذرًا، لم تعد عضوًا هنا أو أن العنصر قد حذف.", show_alert=False)
            return await query.message.delete()
        details = db.get_container_details(container_id)
        db.revoke_permission(user_id, details['type'], container_id)
        await query.answer("✅ تمت المغادرة.", show_alert=False)
        await return_to_shared_spaces(update, context)

# --- Conversation Handlers ---

# (1) New Container Conversation
async def new_container_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    db.update_user_last_active(update.effective_user.id)
    
    parts = query.data.split(':')
    context.user_data['container_type'] = parts[-1]
    parent_id = None
    if len(parts) == 3:
        parent_id = int(parts[1])
        if not db.container_exists(parent_id):
            await query.answer("⚠️ عذرًا، يبدو أن المجلد الأصل قد تم حذفه بالفعل.", show_alert=False)
            await query.message.delete()
            return ConversationHandler.END
        context.user_data['previous_menu'] = f"container:{parent_id}"
    else:
        context.user_data['previous_menu'] = "my_space"
    context.user_data['parent_id'] = parent_id
    
    type_text = "القسم" if context.user_data['container_type'] == 'section' else "المجلد"
    await query.message.edit_text(text=f"📝 أرسل اسم {type_text} الجديد:\n\n*لإلغاء العملية، أرسل /cancel*")
    return AWAITING_CONTAINER_NAME

async def receive_container_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # --- Robustness Check ---
    if 'container_type' not in context.user_data:
        await update.message.reply_text("⚠️ عذرًا، يبدو أن العملية قد انقطعت. يرجى المحاولة مرة أخرى من البداية.")
        context.user_data.clear()
        await start(update, context) # Go back to the main menu
        return ConversationHandler.END

    user_id = update.effective_user.id
    name = update.message.text.strip()

    if not (1 <= len(name) <= 100):
        await update.message.reply_text("⚠️ الاسم غير صالح. يجب أن يكون طوله بين 1 و 100 حرف. يرجى المحاولة مرة أخرى.\n\n*لإلغاء العملية، أرسل /cancel*")
        return AWAITING_CONTAINER_NAME

    container_type = context.user_data['container_type']
    parent_id = context.user_data.get('parent_id')

    owner_id = user_id
    if parent_id:
        if not db.container_exists(parent_id):
            await update.message.reply_text("⚠️ عذرًا، يبدو أن المجلد الأصل الذي تحاول الإضافة إليه قد تم حذفه.")
            context.user_data.clear()
            await return_to_my_space(update, context)
            return ConversationHandler.END
        
        parent_details = db.get_container_details(parent_id)
        if parent_details: owner_id = parent_details['owner_user_id']

    db.add_container(owner_user_id=owner_id, name=name, type=container_type, parent_id=parent_id)
    await update.message.reply_text(f"✅ تم إنشاء \"{name}\" بنجاح\.", parse_mode='MarkdownV2')
    
    context.user_data.clear()
    if parent_id:
        await show_container(update, context, parent_id)
    else:
        await return_to_my_space(update, context)
    return ConversationHandler.END

# (2) Rename Container Conversation
async def rename_container_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    db.update_user_last_active(update.effective_user.id)
    
    container_id = int(query.data.split(':')[1])

    details = db.get_container_details(container_id)
    if not details:
        await query.answer("⚠️ عذرًا، يبدو أن هذا العنصر قد تم حذفه بالفعل.", show_alert=False)
        await query.message.delete()
        return ConversationHandler.END

    context.user_data['container_to_rename'] = container_id
    context.user_data['previous_menu'] = f"container:{container_id}"
    
    await query.message.edit_text(f"📝 الاسم الحالي: *{escape_markdown(details['name'], version=2)}*\n\nأرسل الاسم الجديد\.\n\n*لإلغاء العملية، أرسل /cancel*", parse_mode='MarkdownV2')
    return AWAITING_RENAME_INPUT

async def receive_new_container_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    new_name = update.message.text.strip()
    container_id = context.user_data['container_to_rename']

    if not (1 <= len(new_name) <= 100):
        await update.message.reply_text("⚠️ الاسم غير صالح. يجب أن يكون طوله بين 1 و 100 حرف. يرجى المحاولة مرة أخرى.\n\n*لإلغاء العملية، أرسل /cancel*")
        return AWAITING_RENAME_INPUT

    if not db.container_exists(container_id):
        await update.message.reply_text("⚠️ عذرًا، يبدو أن هذا العنصر قد تم حذفه بالفعل.")
        context.user_data.clear()
        await return_to_my_space(update, context)
        return ConversationHandler.END

    db.rename_container(container_id, new_name, user_id)
    await update.message.reply_text(f"✅ تم تغيير الاسم إلى: {new_name}")
    
    context.user_data.clear()
    await show_container(update, context, container_id)
    return ConversationHandler.END

# (3) Add Items Conversation
async def add_items_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    db.update_user_last_active(update.effective_user.id)
    
    container_id = int(query.data.split(':')[1])
    if not db.container_exists(container_id):
        await query.answer("⚠️ عذرًا، يبدو أن هذا المجلد قد تم حذفه بالفعل.", show_alert=False)
        await query.message.delete()
        return ConversationHandler.END

    context.user_data['target_container_id'] = container_id
    context.user_data['previous_menu'] = f"container:{container_id}"
    await query.message.edit_text(text="*➕ وضع الإضافة*\n\nأرسل ملفاتك، صورك، أو رسائلك\. \nعند الانتهاء، اضغط /done لحفظها أو /cancel للإلغاء\.", parse_mode='MarkdownV2')
    return AWAITING_ITEMS_FOR_UPLOAD


async def collect_items(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if 'items_to_add_buffer' not in context.user_data:
        context.user_data['items_to_add_buffer'] = []
    context.user_data['items_to_add_buffer'].append(update.message)
    await update.message.reply_text("👍 تم الاستلام\. أرسل المزيد أو اضغط /done للحفظ\.", parse_mode='MarkdownV2')
    return AWAITING_ITEMS_FOR_UPLOAD

async def save_items(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    container_id = context.user_data.get('target_container_id')
    message_buffer = context.user_data.get('items_to_add_buffer', [])

    if not db.container_exists(container_id):
        await update.message.reply_text("⚠️ عذرًا، يبدو أن المجلد الذي تحاول الحفظ فيه قد تم حذفه.")
        context.user_data.clear()
        return ConversationHandler.END

    if not message_buffer:
        await update.message.reply_text("⚠️ لم ترسل أي عناصر. تم الخروج من وضع الإضافة.", reply_markup=kb.back_button(f"container:{container_id}"), parse_mode='MarkdownV2')
    else:
        await update.message.reply_text(f"📥 جاري حفظ {len(message_buffer)} عنصر...")
        count = 0
        for msg in message_buffer:
            item_info = await process_message_for_saving(msg)
            if item_info:
                db.add_item(container_id=container_id, user_id=user_id, **item_info)
                count += 1
        await update.message.reply_text(f"✅ تم حفظ {count} عنصر بنجاح\!", reply_markup=kb.back_button(f"container:{container_id}"), parse_mode='MarkdownV2')
    
    context.user_data.clear()
    return ConversationHandler.END

async def cancel_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """[معدل] يلغي المحادثة الحالية."""
    await update.message.reply_text("❌ تم إلغاء العملية. جارٍ العودة...")
    previous_menu = context.user_data.get('previous_menu')
    context.user_data.clear()

    if previous_menu:
        if previous_menu.startswith("container:"):
            container_id = int(previous_menu.split(':')[1])
            await show_container(update, context, container_id)
        elif previous_menu == "my_space":
            await return_to_my_space(update, context)
        elif previous_menu == "shared_spaces":
            await return_to_shared_spaces(update, context)
        else:
            await start(update, context)
    else:
        await start(update, context)
    return ConversationHandler.END
