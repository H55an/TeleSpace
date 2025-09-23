# handlers.py

import asyncio
import re
from functools import wraps
from telegram import Update, InlineKeyboardMarkup, Message, InlineKeyboardButton
from telegram import ChatMember
from telegram.ext import ContextTypes, ConversationHandler
from telegram.helpers import escape_markdown
from telegram.error import Forbidden

import config
import database as db
import keyboards as kb
from constants import *
from processors import ChannelProcessor, GroupProcessor # [جديد]

# [جديد] خريطة المعالجات
PROCESSORS = {
    'channel': ChannelProcessor(),
    'group': GroupProcessor(),
    'supergroup': GroupProcessor(),
}


# --- بوابة التحقق (الدالة الحارسة) ---

def check_subscription(func):
    """
    [جديد] Decorator للتحقق من أن المستخدم عضو في القناة المطلوبة.
    """
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        # تخطي التحقق إذا لم يتم تعيين القناة أو الرابط
        if config.REQUIRED_CHANNEL_ID == "PLEASE_UPDATE_ME" or config.REQUIRED_CHANNEL_LINK == "PLEASE_UPDATE_ME":
            return await func(update, context, *args, **kwargs)

        user = update.effective_user
        if not user:
            return

        try:
            member = await context.bot.get_chat_member(chat_id=config.REQUIRED_CHANNEL_ID, user_id=user.id)
            # التحقق من أن حالة العضوية صالحة
            if member.status in ['member', 'administrator', 'creator']:
                return await func(update, context, *args, **kwargs)
            else:
                # إذا كانت الحالة left, kicked, etc.
                raise Forbidden("User is not a member.")
        except Forbidden:
            # هذا الخطأ يحدث إذا لم يكن المستخدم عضواً
            text = """
🛂 أهلاً بك في TeleSpace!
لاستخدام خدمات البوت، يرجى أولاً الانضمام إلى قناتنا الرسمية. هذا يضمن حصولك على آخر التحديثات والأخبار.

اضغط على الزر أدناه للانضمام، ثم عد إلى هنا واضغط '✅ لقد اشتركت'.
            """
            keyboard = kb.build_subscription_keyboard()
            
            # إذا كان التفاعل عبر زر، نعدل الرسالة، وإلا نرسل رسالة جديدة
            query = update.callback_query
            if query:
                # نجيب على الـ query أولاً لمنع ظهور علامة التحميل
                await query.answer()
                await query.message.edit_text(text, reply_markup=keyboard)
            else:
                await update.message.reply_text(text, reply_markup=keyboard)
            return # نوقف تنفيذ الدالة الأصلية
        except Exception as e:
            print(f"An unexpected error occurred in subscription check: {e}")
            await update.message.reply_text("حدث خطأ أثناء التحقق من اشتراكك. يرجى المحاولة مرة أخرى.")
            return

    return wrapper


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
    """[معدل ومصحح] يعالج الرسائل لتحويلها إلى بيانات قابلة للحفظ بطريقة آمنة."""
    file_type, file_obj = None, None
    if message.document: (file_type, file_obj) = ('document', message.document)
    elif message.video: (file_type, file_obj) = ('video', message.video)
    elif message.photo: (file_type, file_obj) = ('photo', message.photo[-1])
    elif message.audio: (file_type, file_obj) = ('audio', message.audio)
    elif message.voice: (file_type, file_obj) = ('voice', message.voice)

    if file_type and file_obj:
        try:
            fwd_msg = await message.forward(chat_id=config.STORAGE_CHANNEL_ID)
        except Forbidden:
            print(f"Error: Bot is not an admin in the storage channel {config.STORAGE_CHANNEL_ID} or cannot forward messages.")
            return None
        
        fwd_file_obj = None
        if fwd_msg:
            if file_type == 'document' and fwd_msg.document: fwd_file_obj = fwd_msg.document
            elif file_type == 'video' and fwd_msg.video: fwd_file_obj = fwd_msg.video
            elif file_type == 'photo' and fwd_msg.photo: fwd_file_obj = fwd_msg.photo[-1]
            elif file_type == 'audio' and fwd_msg.audio: fwd_file_obj = fwd_msg.audio
            elif file_type == 'voice' and fwd_msg.voice: fwd_file_obj = fwd_msg.voice

        if fwd_file_obj:
            return {
                'item_name': getattr(file_obj, 'file_name', f'ملف_{file_type}'),
                'item_type': file_type,
                'content': message.caption,
                'file_unique_id': file_obj.file_unique_id,
                'file_id': fwd_file_obj.file_id
            }
        else:
            print(f"Could not get forwarded file object for a message of type {file_type}")
            return None

    elif message.text:
        return {
            'item_name': f"رسالة: {message.text[:20]}...",
            'item_type': 'text',
            'content': message.text,
            'file_unique_id': None,
            'file_id': None
        }
        
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
                    'audio': context.bot.send_audio,
                    'voice': context.bot.send_voice,
                }
                if content != None:
                    content = content if len(content) <= 1024 else content[:1020] + " ..."
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
@check_subscription
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """[معدل] يبدأ البوت ويعالج روابط المشاركة والروابط العميقة للقنوات."""
    user = update.effective_user
    db.add_user_if_not_exists(user_id=user.id, first_name=user.first_name)

    # [جديد] معالجة الروابط العميقة من أزرار القنوات
    if context.args and context.args[0].startswith("folder_"):
        try:
            _, section_id_str, folder_id_str = context.args[0].split('_')
            section_id = int(section_id_str)
            folder_id = int(folder_id_str)

            # منح المستخدم صلاحية مشاهدة للقسم الرئيسي تلقائيًا
            db.grant_viewer_permission_for_section(user.id, section_id)
            
            # مسح بيانات المحادثة السابقة ونقل المستخدم مباشرة إلى المجلد
            context.user_data.clear()
            await show_container(update, context, folder_id)
            return ConversationHandler.END
        except (ValueError, IndexError) as e:
            print(f"Error processing deep link: {e}")
            # في حالة الخطأ، يتم توجيهه إلى القائمة الرئيسية
            pass # Fall through to the main menu

    # معالجة روابط المشاركة الحالية
    context.user_data.clear()
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

    # عرض القائمة الرئيسية
    first_name = escape_markdown(user.first_name, version=2)
    developer_link = f"[{escape_markdown(config.DEVELOPER_NAME, version=2)}](tg://user?id={config.DEVELOPER_ID})"
    keyboard = kb.main_menu_keyboard()
    reply_text = f"""
مرحبًا {first_name}، يسعدنا تواجدك في *TeleSpace* \! 

مساحتك الرقمية على Telegram لتحويل الفوضى إلى مساحة عمل منظمة \. 

🗂️ *نظّم* أفكارك ومشاريعك\.
💾 *احفظ* ملفاتك ورسائلك المهمة\.
🤝 *شارك* محتواك بسهولة وأمان\.
    
*استكشف مساحتك أو ابدأ بتصفح ما شاركه الآخرون معك*\.

_ارسل /info لقرائة دليل استخدام TeleSpace_\.
"""
    
    if update.callback_query:
        await update.callback_query.message.edit_text(reply_text, reply_markup=keyboard, parse_mode='MarkdownV2')
    else:
        await update.message.reply_text(reply_text, reply_markup=keyboard, parse_mode='MarkdownV2')
        
    return ConversationHandler.END

async def info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Sends a formatted guide and cancels any ongoing conversation."""
    user_id = update.effective_user.id
    db.update_user_last_active(user_id)

    # Check if we are in a conversation and notify the user
    if context.user_data:
        context.user_data.clear()
        await update.message.reply_text("✅ تم إلغاء العملية الحالية.")

    info_text = """
🤖 *دليل استخدام TeleSpace*

أهلاً بك\! إليك كيفية الاستفادة القصوى من مساحتك الرقمية:

*🗂️ نظّم مساحتك ببراعة*
اذهب إلى "👤 مساحتي الخاصة" لإنشاء _أقسام_ لمواضيعك الرئيسية \(مثل "العمل"، "الدراسة"\)\.
*للتنظيم المتقدم*، يمكنك الدخول إلى أي قسم وإنشاء _أقسام فرعية_ بداخله، مما يسمح لك ببناء هيكل تنظيمي متكامل لمشاريعك\. أخيرًا، أنشئ _مجلدات_ داخل أي قسم لحفظ ملفاتك\.

*📥 احفظ كل شيء بسهولة*
داخل أي مجلد، اضغط "➕ إضافة عناصر" وأرسل ما تشاء من ملفات، صور، أو نصوص\. عند الانتهاء، اكتب `/done`\.

*ملاحظة هامة:* تُستخدم _المجلدات_ لحفظ ملفاتك ومحتوياتك، وتُستخدم _الأقسام_ لعمل تنظيم هرمي من الأقسام المتداخلة\.


*🤝 شارك بذكاء وأمان*
اضغط على زر "🔗" داخل أي قسم أو مجلد تملكه للوصول لخيارات المشاركة:

*👁️ رابط مشاهدة \(للعرض فقط\):*
• *ما هو؟* رابط دائم يمكن لأي شخص الوصول لمحتويات القسم/المجلد دون القدرة على تعديله أو حذفه\.
• *متى تستخدمه؟* مثالي لمشاركة محتواك مع آلاف المستخدمين\.

*👥 دعوة مشرف \(للتعديل والإضافة\):*
• *ما هو؟* رابط يُستخدم _لمرة واحدة فقط_ لدعوة شخص ليصبح مشرفًا على المجلد أو القسم\.
• *متى تستخدمه؟* مثالي للعمل المشترك على المشاريع، حيث يحتاج زميلك لإضافة ملفات أو تعديل المحتوى\.


*🤖 الأتمتة الذكية \(للقنوات والمجموعات\)*
حوّل البوت إلى مساعدك الذكي الذي يقوم بأرشفة المحتوى تلقائيًا\.

*📢 في القنوات:*
حوّل قناتك إلى واجهة تفاعلية ومنظمة\.
• *الإعداد:* أضف البوت إلى قناتك وامنحه صلاحيات المشرف\.
• *الربط:* في البوت، اذهب للقسم الذي تريده واربطه بالقناة\.
• *الأرشفة:* انشر رسالة في القناة مع هاشتاج يطابق اسم أحد المجلدات في قسمك\.
• *النتيجة:* سيقوم البوت بحفظ الرسالة في المجلد الصحيح ويضيف زرًا تفاعليًا تحت الرسالة الأصلية، مما يسمح للأعضاء بالوصول للمحتوى المنظم بضغطة زر\!

*👥 في المجموعات:*
نظّم محتوى مجموعاتك تلقائيًا، سواء كانت عادية أو مقسمة لمواضيع\.
• *الإعداد:* أضف البوت إلى مجموعتك وامنحه صلاحيات المشرف\.
• *الربط:* في البوت، اذهب للقسم الذي تريده واربطه بالمجموعة\.
• *الأرشفة:*
 \- *للمجموعات العادية:* انشر رسالة مع هاشتاج يطابق اسم "مجلد" في قسمك\.
 \- *للمجموعات ذات المواضيع:* انشر الرسالة في "موضوع" معين مع هاشتاج يطابق اسم "مجلد" موجود داخل "قسم فرعي" يحمل نفس اسم الموضوع\.
• *النتيجة:* سيقوم البوت بحفظ الرسالة في المكان الصحيح _بشكل صامت_، للحفاظ على سلاسة المحادثات في المجموعات\.
"""
    await update.message.reply_text(info_text, parse_mode='MarkdownV2', reply_markup=kb.back_button("back_to_main"))
    return ConversationHandler.END

@check_subscription
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
    
    # --- Content Viewing ---\
    elif data.startswith("view_items:"):
        _, container_id, offset = data.split(':')
        await view_and_send_container_contents(update, context, int(container_id), int(offset))

    # --- Settings ---\
    elif data.startswith("settings_container:"):
        container_id = int(data.split(':')[1])
        if not db.container_exists(container_id):
            await query.answer("⚠️ عذرًا، يبدو أن هذا العنصر قد تم حذفه بالفعل.", show_alert=False)
            return await query.message.delete()
        details = db.get_container_details(container_id)
        text = f"⚙️ *إعدادات: {escape_markdown(details['name'], version=2)}*\n\."
        keyboard = kb.build_settings_keyboard(container_id, user_id)
        await query.message.edit_text(text, reply_markup=keyboard, parse_mode='MarkdownV2')

    # --- Sharing ---\
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

    elif data.startswith("statistics_container:"):
        container_id = int(data.split(':')[1])
        if not db.container_exists(container_id):
            await query.answer("⚠️ عذرًا، يبدو أن هذا العنصر قد تم حذفه بالفعل.", show_alert=False)
            return await query.message.delete()
        
        details = db.get_container_details(container_id)
        stats = db.get_container_statistics(container_id)
        
        text = f"""📊 *إحصائيات: {escape_markdown(details['name'], version=2)}*

\- عدد المشرفين: *{stats['admin_count']}*
\- إجمالي المشتركين: *{stats['subscriber_count']}*

_لا تشمل هذه الإحصائيات المالك \._
"""
        
        await query.message.edit_text(
            text,
            reply_markup=kb.back_button(f"share_menu_container:{container_id}"),
            parse_mode='MarkdownV2'
        )

    # --- Automation (New and Modified) ---\
    elif data.startswith("automation_menu:"):
        container_id = int(data.split(':')[1])
        await show_automation_menu(update, context, container_id)

    elif data.startswith("link_group_start:"):
        container_id = int(data.split(':')[1])
        await link_group_start(update, context, container_id)

    elif data.startswith("start_watch:"):
        container_id = int(data.split(':')[1])
        db.update_watching_status(container_id, True, user_id)
        await query.answer("✅ تم بدء المراقبة.")
        await show_automation_menu(update, context, container_id)

    elif data.startswith("stop_watch:"):
        container_id = int(data.split(':')[1])
        db.update_watching_status(container_id, False, user_id)
        await query.answer("⏸️ تم إيقاف المراقبة.")
        await show_automation_menu(update, context, container_id)

    elif data.startswith("unlink_entity_prompt:"):
        container_id = int(data.split(':')[1])
        linked_entity = db.get_linked_entity_by_container(container_id)
        entity_type_str = "الكيان"
        if linked_entity:
            entity_type_str = "القناة" if linked_entity['entity_type'] == 'channel' else "المجموعة"
        
        text = f"⚠️ هل أنت متأكد من إلغاء ربط {entity_type_str}؟ سيتم إيقاف الأتمتة."
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔥 نعم، إلغاء الربط", callback_data=f"unlink_entity_confirm:{container_id}")],
            [InlineKeyboardButton("❌ تراجع", callback_data=f"automation_menu:{container_id}")]
        ])
        await query.message.edit_text(text, reply_markup=keyboard)

    elif data.startswith("unlink_entity_confirm:"):
        container_id = int(data.split(':')[1])
        db.delete_linked_entity(container_id, user_id)
        await query.answer("✅ تم إلغاء الربط بنجاح.")
        await show_automation_menu(update, context, container_id)

    # --- Deletion ---\
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

    # --- Leaving Shared Items ---\
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
        await update.message.reply_text("⚠️ لم ترسل أي عناصر. تم الخروج من وضع الإضافة.", reply_markup=kb.back_button(f"container:{container_id}"))
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

# --- Automation Handlers ---

async def show_automation_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, container_id: int):
    """[معدل] يعرض قائمة التحكم في الأتمتة للكيانات (قنوات ومجموعات)."""
    query = update.callback_query
    user_id = update.effective_user.id
    
    details = db.get_container_details(container_id)
    if not details or details['owner_user_id'] != user_id:
        if query:
            await query.answer("ليس لديك الصلاحية للوصول إلى هنا.", show_alert=True)
        else:
            await context.bot.send_message(user_id, "ليس لديك الصلاحية للوصول إلى هنا.")
        return

    linked_entity = db.get_linked_entity_by_container(container_id)
    text = f"🤖 *الأتمتة للقسم: {escape_markdown(details['name'], version=2)}*\n\n"

    if not linked_entity:
        text += "لم يتم ربط أي قناة بعد\. يمكنك ربط قناة عامة أو خاصة أنت مشرف بها\.\n\n"
        text += "سيقوم البوت بأرشفة الرسائل الجديدة أو المعدلة من القناة التي تحتوي على هاشتاجات تتطابق مع أسماء المجلدات داخل هذا القسم\."
    else:
        entity_type_str = "القناة" if linked_entity['entity_type'] == 'channel' else "المجموعة"
        status = "مفعلة" if linked_entity['is_watching'] else "متوقفة"
        text += f"{entity_type_str} المرتبطة: *{escape_markdown(linked_entity['entity_name'], version=2)}*\n"
        text += f"حالة المراقبة: *{status}*"

    keyboard = kb.build_automation_keyboard(container_id)
    
    if query:
        await query.message.edit_text(text, reply_markup=keyboard, parse_mode='MarkdownV2')
    else:
        await context.bot.send_message(chat_id=user_id, text=text, reply_markup=keyboard, parse_mode='MarkdownV2')


async def link_channel_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """[جديد] يبدأ محادثة ربط القناة."""
    query = update.callback_query
    container_id = int(query.data.split(':')[1])
    
    # Security check: ensure user owns the container
    details = db.get_container_details(container_id)
    if not details or details['owner_user_id'] != query.from_user.id:
        await query.answer("فقط مالك القسم يمكنه ربط القنوات.", show_alert=True)
        return ConversationHandler.END

    context.user_data['automation_container_id'] = container_id
    context.user_data['previous_menu'] = f"automation_menu:{container_id}"

    text = """
*🔗 لربط قناة، اتبع الخطوات التالية:*

1\. تأكد من أن البوت مشرف في القناة المستهدفة\.
2\. تأكد من أنك *مشرف* أو *مالك* في القناة\.
3\. قم بإعادة توجيه *أي رسالة* من القناة إلى هنا\.

*لإلغاء العملية، أرسل /cancel*\.
    """
    await query.message.edit_text(text, parse_mode='MarkdownV2')
    return AWAITING_CHANNEL_FORWARD

async def receive_channel_forward(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """[معدل] يعالج الرسالة المعاد توجيهها لربط القناة باستخدام `link_entity`."""
    user_id = update.effective_user.id
    container_id = context.user_data.get('automation_container_id')

    if not container_id:
        await update.message.reply_text("⚠️ حدث خطأ ما. يرجى المحاولة مرة أخرى بالدخول إلى إعدادات القسم.")
        context.user_data.clear()
        return ConversationHandler.END

    origin = update.message.forward_origin
    if not origin or origin.type != 'channel':
        await update.message.reply_text(
            "⚠️ هذه ليست رسالة معاد توجيهها من قناة. يرجى إعادة توجيه رسالة من قناة.\n\nأو أرسل /cancel للإلغاء."
        )
        return AWAITING_CHANNEL_FORWARD

    channel = origin.chat
    channel_id = channel.id
    channel_name = channel.title

    # Check if this entity is already linked to another section
    existing_link = db.get_linked_entity_by_entity_id(channel_id)
    if existing_link and existing_link['container_id'] != container_id:
        await update.message.reply_text(f"⚠️ هذه القناة مرتبطة بالفعل بقسم آخر. لا يمكن ربط نفس القناة مرتين.")
        context.user_data.clear()
        await show_automation_menu(update, context, container_id)
        return ConversationHandler.END

    # Check bot and user permissions in the channel
    try:
        bot_member = await context.bot.get_chat_member(channel_id, context.bot.id)
        if bot_member.status not in ['administrator', 'member']:
            raise Forbidden("Bot is not a member or admin")
        user_member = await context.bot.get_chat_member(channel_id, user_id)
        if user_member.status not in ['creator', 'administrator']:
            await update.message.reply_text("⚠️ يجب أن تكون مشرفًا أو مالكًا في القناة لتتمكن من ربطها.")
            return AWAITING_CHANNEL_FORWARD
    except Forbidden as e:
        await update.message.reply_text(f"⚠️ لا يمكنني الوصول للقناة أو التحقق من الصلاحيات. يرجى التأكد من أن البوت مشرف في القناة. ({e})")
        return AWAITING_CHANNEL_FORWARD
    except Exception as e:
        await update.message.reply_text(f"⚠️ خطأ غير متوقع: {e}")
        return AWAITING_CHANNEL_FORWARD

    # All checks passed, link the entity
    success = db.link_entity(
        container_id=container_id, 
        user_id=user_id, 
        entity_id=channel_id, 
        entity_name=channel_name, 
        entity_type='channel'
    )
    
    if success:
        await update.message.reply_text(f"✅ تم ربط القناة '{escape_markdown(channel_name, version=2)}' بنجاح\!", parse_mode='MarkdownV2')
    else:
        # This message is shown if the unique constraint on entity_id fails
        await update.message.reply_text(f"⚠️ فشل ربط القناة. قد تكون القناة مرتبطة بالفعل بقسم آخر.")

    context.user_data.clear()
    await show_automation_menu(update, context, container_id)
    return ConversationHandler.END


async def link_group_start(update: Update, context: ContextTypes.DEFAULT_TYPE, container_id: int):
    """[جديد ومعدل] يبدأ عملية ربط مجموعة عبر إرسال رمز ربط للمستخدم."""
    query = update.callback_query
    user_id = query.from_user.id

    # Security check: ensure user owns the container
    details = db.get_container_details(container_id)
    if not details or details['owner_user_id'] != user_id:
        await query.answer("فقط مالك القسم يمكنه ربط المجموعات.", show_alert=True)
        return

    token = db.create_linking_token(user_id, container_id)
    if not token:
        await query.answer("⚠️ حدث خطأ أثناء إنشاء رمز الربط. يرجى المحاولة مرة أخرى.", show_alert=True)
        return

    bot_username = (await context.bot.get_me()).username
    text = f"""*🔗 لربط مجموعة، اتبع الخطوات التالية:*

1\. أضف البوت إلى مجموعتك وارفعه إلى رتبة *مشرف*\.
2\. انسخ الأمر التالي *بالكامل* وأرسله في المجموعة:

`/link_group@{bot_username} {token}`

*هذا الأمر صالح لمدة 10 دقائق فقط\.*"""
    await query.message.edit_text(text, parse_mode='MarkdownV2', reply_markup=kb.back_button(f"automation_menu:{container_id}"))


async def link_group_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """[جديد] يعالج أمر ربط المجموعة الذي يحتوي على الرمز."""
    user_id = update.effective_user.id
    chat = update.effective_chat

    if not context.args or len(context.args) != 1:
        await update.message.reply_text("⚠️ صيغة الأمر غير صحيحة. يرجى استخدام الصيغة المرسلة لك في الخاص.")
        return

    if not chat.type in ['group', 'supergroup']:
        await update.message.reply_text("⚠️ هذا الأمر يمكن استخدامه داخل المجموعات فقط.")
        return

    token = context.args[0]
    token_data = db.get_linking_token_data(token)

    if not token_data:
        await context.bot.send_message(user_id, "⚠️ رمز الربط غير صالح أو انتهت صلاحيته. يرجى طلب رمز جديد.")
        return

    if token_data['user_id'] != user_id:
        await context.bot.send_message(user_id, "⚠️ هذا الرمز لا يخصك. لا يمكنك استخدامه.")
        return

    # Check bot and user permissions
    try:
        bot_member = await chat.get_member(context.bot.id)
        if bot_member.status != 'administrator':
            await context.bot.send_message(user_id, f"⚠️ يجب أن يكون البوت مشرفًا في المجموعة '{chat.title}' لإتمام الربط.")
            return

        user_member = await chat.get_member(user_id)
        if user_member.status not in ['creator', 'administrator']:
            await context.bot.send_message(user_id, f"⚠️ يجب أن تكون مشرفًا في المجموعة '{chat.title}' لتتمكن من ربطها.")
            return
    except Forbidden:
        await context.bot.send_message(user_id, f"⚠️ لا يمكنني التحقق من الصلاحيات في المجموعة '{chat.title}'. يرجى التأكد من أنني عضو ومشرف.")
        return
    except Exception as e:
        await context.bot.send_message(user_id, f"⚠️ خطأ غير متوقع أثناء التحقق من الصلاحيات: {e}")
        return

    # All checks passed
    container_id = token_data['container_id']
    
    # Check if this group is already linked to another section
    existing_link = db.get_linked_entity_by_entity_id(chat.id)
    if existing_link and existing_link['container_id'] != container_id:
        await context.bot.send_message(user_id, f"⚠️ هذه المجموعة مرتبطة بالفعل بقسم آخر. لا يمكن ربط نفس المجموعة مرتين.")
        return

    success = db.link_entity(
        container_id=container_id,
        user_id=user_id,
        entity_id=chat.id,
        entity_name=chat.title,
        entity_type=chat.type,
        is_group_with_topics=chat.is_forum
    )

    if success:
        db.delete_linking_token(token)
        await update.message.reply_text(f"✅ تم ربط هذه المجموعة بنجاح بالقسم المستهدف!")
        
        # --- [جديد] إرسال رسالة تأكيد مع قائمة الأتمتة ---
        container_id = token_data['container_id']
        details = db.get_container_details(container_id)

        text = f"✅ تم ربط المجموعة *{escape_markdown(chat.title, version=2)}* بالقسم *{escape_markdown(details['name'], version=2)}* بنجاح\\!\n\n"
        text += "الآن يمكنك التحكم بالأتمتة من خلال الأزرار أدناه:"
        
        keyboard = kb.build_automation_keyboard(container_id)
        await context.bot.send_message(user_id, text, reply_markup=keyboard, parse_mode='MarkdownV2')
        # --- نهاية الجزء الجديد ---
    else:
        await context.bot.send_message(user_id, f"⚠️ فشل ربط المجموعة '{chat.title}'. قد تكون مرتبطة بالفعل بقسم آخر.")

async def entity_post_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    [جديد وموحد] يعالج الرسائل من أي كيان مرتبط (قناة أو مجموعة).
    يحدد نوع الكيان ويستدعي المعالج المنطقي (Processor) المناسب له.
    """
    message = update.effective_message
    if not message:
        return

    chat = update.effective_chat
    if not chat:
        return

    # جلب الكيان المرتبط من قاعدة البيانات
    # نستخدم ID الدردشة لتحديد ما إذا كانت هذه الدردشة (قناة أو مجموعة) مراقبة
    linked_entity = db.get_linked_entity_by_entity_id(chat.id)

    # إذا لم يكن الكيان مرتبطًا أو كانت المراقبة متوقفة، نتجاهل الرسالة
    if not linked_entity or not linked_entity['is_watching']:
        return

    # تحديد نوع المعالج المنطقي (Processor) المطلوب
    # ملاحظة: 'supergroup' يتم التعامل معها بنفس منطق 'group'
    processor_key = chat.type if chat.type in ['channel', 'group', 'supergroup'] else None
    processor = PROCESSORS.get(processor_key)

    if not processor:
        # This will effectively ignore messages from private chats or other types.
        return

    # استدعاء المعالج المنطقي مع تمرير دالة الحفظ لحل مشكلة الاعتماد الدائري
    await processor.process_message(message, linked_entity, context, process_message_for_saving)


async def forum_topic_activity_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    [مبسط وموحد] يلتقط جميع أحداث المواضيع ويحفظها في جدول forum_topics.
    يستخدم '0' كمعرف للموضوع العام.
    """
    chat = update.effective_chat
    if not chat or not chat.is_forum:
        return

    # تجاهل الحدث إذا كانت المجموعة غير مرتبطة
    if not db.get_linked_entity_by_entity_id(chat.id):
        return

    topic_created = update.message.forum_topic_created
    topic_edited = update.message.forum_topic_edited
    
    topic_name = None
    if topic_created:
        topic_name = topic_created.name
    elif topic_edited:
        topic_name = topic_edited.name

    if not topic_name:
        return

    # توحيد المعرف: استخدم 0 إذا كان None، وإلا استخدم المعرف الحقيقي
    thread_id = update.message.message_thread_id if update.message.message_thread_id is not None else 0
    
    db.add_or_update_topic(chat.id, thread_id, topic_name)
    print(f"Unified topic name updated in DB for chat {chat.id}: Thread {thread_id} -> '{topic_name}'")

@check_subscription
async def check_subscription_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    [جديد] يتم استدعاؤه عند الضغط على زر "لقد اشتركت".
    الـ decorator سيقوم بالتحقق، وإذا نجح، سنقوم ببساطة باستدعاء دالة البدء.
    """
    query = update.callback_query
    await query.answer("✅ شكرًا لاشتراكك! أهلاً بك.", show_alert=False)
    # بعد التحقق الناجح، نعرض القائمة الرئيسية
    await start(update, context)
