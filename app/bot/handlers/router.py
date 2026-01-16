from telegram import Update
from telegram.ext import ContextTypes
from telegram.helpers import escape_markdown

from app.shared.database import users as db_users
from app.shared.database import containers as db_containers
from app.shared.database import auth as db_auth
from app.shared.database import automation as db_automation
from app.bot import keyboards as kb
from app.bot.utils import check_subscription

from . import main_menu
from . import navigation
from . import admin
from . import automation

@check_subscription
async def button_press_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """[معدل] الموجه الرئيسي لضغطات الأزرار."""
    query = update.callback_query
    data = query.data
    user_id = query.from_user.id
    db_users.update_user_last_active(user_id) # Update user activity

    # --- Basic Navigation ---
    if data == "my_space": await navigation.return_to_my_space(update, context)
    elif data == "shared_spaces": await navigation.return_to_shared_spaces(update, context)
    elif data == "back_to_main": await main_menu.start(update, context)
    elif data.startswith("container:"): await navigation.show_container(update, context, int(data.split(':')[1]))
    
    # --- Content Viewing ---
    elif data.startswith("view_items:"):
        _, container_id, offset = data.split(':')
        await navigation.view_and_send_container_contents(update, context, int(container_id), int(offset))

    # --- Settings ---
    elif data.startswith("settings_container:"):
        container_id = int(data.split(':')[1])
        if not db_containers.container_exists(container_id):
            await query.answer("⚠️ عذرًا، يبدو أن هذا العنصر قد تم حذفه بالفعل.", show_alert=False)
            return await query.message.delete()
        details = db_containers.get_container_details(container_id)
        text = f"⚙️ *إعدادات: {escape_markdown(details['name'], version=2)}*\n\."
        keyboard = kb.build_settings_keyboard(container_id, user_id)
        await query.message.edit_text(text, reply_markup=keyboard, parse_mode='MarkdownV2')

    # --- Sharing ---
    elif data.startswith("share_menu_container:"):
        container_id = int(data.split(':')[1])
        if not db_containers.container_exists(container_id):
            await query.answer("⚠️ عذرًا، يبدو أن هذا العنصر قد تم حذفه بالفعل.", show_alert=False)
            return await query.message.delete()
        details = db_containers.get_container_details(container_id)
        text = f"🔗 *مشاركة: {escape_markdown(details['name'], version=2)}*\n\."
        # [تعديل] مرر user_id هنا
        keyboard = kb.build_share_menu_keyboard(container_id, user_id)
        await query.message.edit_text(text, reply_markup=keyboard, parse_mode='MarkdownV2')

    elif data.startswith("get_viewer_link:"):
        # هذا الجزء يبقى كما هو تقريبًا
        container_id = int(data.split(':')[1])
        if not db_containers.container_exists(container_id):
            await query.answer("⚠️ عذرًا، يبدو أن هذا العنصر قد تم حذفه بالفعل.", show_alert=False)
            return await query.message.delete()
        details = db_containers.get_container_details(container_id)
        token = db_auth.get_or_create_viewer_share_link(user_id, details['type'], container_id)
        title = "رابط المشاركة \(مشاهدة فقط\)\n_انقر نقرة واحدة لنسخه_"
        bot_username = (await context.bot.get_me()).username
        share_link = f"https://t.me/{bot_username}?start={token}"
        text = f"✅ {title}:\n\n`{share_link}`"
        await query.message.edit_text(text, reply_markup=kb.back_button(f"share_menu_container:{container_id}"), parse_mode='MarkdownV2')

    elif data.startswith("get_admin_link:"):
        # [جديد] هذا البلوك سيعرض السؤال
        container_id = int(data.split(':')[1])
        text = "❓ هل تريد السماح لهذا المشرف بإضافة مشرفين آخرين؟"
        keyboard = kb.InlineKeyboardMarkup([
            [kb.InlineKeyboardButton("✅ نعم", callback_data=f"create_admin_link:1:{container_id}")],
            [kb.InlineKeyboardButton("❌ لا", callback_data=f"create_admin_link:0:{container_id}")],
            [kb.InlineKeyboardButton("🔙 رجوع", callback_data=f"share_menu_container:{container_id}")]
        ])
        await query.message.edit_text(text, reply_markup=keyboard)

    elif data.startswith("create_admin_link:"):
        # [جديد] هذا البلوك سينشئ الرابط بناءً على اختيار المستخدم
        _, can_add, container_id_str = data.split(':')
        container_id = int(container_id_str)
        grants_can_add_admins = int(can_add)

        if not db_containers.container_exists(container_id):
            await query.answer("⚠️ عذرًا، يبدو أن هذا العنصر قد تم حذفه بالفعل.", show_alert=False)
            return await query.message.delete()

        details = db_containers.get_container_details(container_id)

        token = db_auth.create_share_link(user_id, details['type'], container_id, 'admin', grants_can_add_admins=grants_can_add_admins)
        title = "رابط دعوة مشرف \(يستخدم لمرة واحدة\)\n_انقر نقرة واحدة لنسخه_"

        bot_username = (await context.bot.get_me()).username
        share_link = f"https://t.me/{bot_username}?start={token}"
        text = f"✅ {title}:\n\n`{share_link}`"
        await query.message.edit_text(text, reply_markup=kb.back_button(f"share_menu_container:{container_id}"), parse_mode='MarkdownV2')

    elif data.startswith("statistics_container:"):
        container_id = int(data.split(':')[1])
        if not db_containers.container_exists(container_id):
            await query.answer("⚠️ عذرًا، يبدو أن هذا العنصر قد تم حذفه بالفعل.", show_alert=False)
            return await query.message.delete()
        
        details = db_containers.get_container_details(container_id)
        stats = db_containers.get_container_statistics(container_id)
        
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

    # --- Automation (New and Modified) ---
    elif data.startswith("automation_menu:"):
        container_id = int(data.split(':')[1])
        await automation.show_automation_menu(update, context, container_id)

    elif data.startswith("link_group_start:"):
        container_id = int(data.split(':')[1])
        await automation.link_group_start(update, context, container_id)

    elif data.startswith("start_watch:"):
        container_id = int(data.split(':')[1])
        db_automation.update_watching_status(container_id, True, user_id)
        await query.answer("✅ تم بدء المراقبة.")
        await automation.show_automation_menu(update, context, container_id)

    elif data.startswith("stop_watch:"):
        container_id = int(data.split(':')[1])
        db_automation.update_watching_status(container_id, False, user_id)
        await query.answer("⏸️ تم إيقاف المراقبة.")
        await automation.show_automation_menu(update, context, container_id)

    elif data.startswith("unlink_entity_prompt:"):
        container_id = int(data.split(':')[1])
        linked_entity = db_automation.get_linked_entity_by_container(container_id)
        entity_type_str = "الكيان"
        if linked_entity:
            entity_type_str = "القناة" if linked_entity['entity_type'] == 'channel' else "المجموعة"
        
        text = f"⚠️ هل أنت متأكد من إلغاء ربط {entity_type_str}؟ سيتم إيقاف الأتمتة."
        keyboard = kb.InlineKeyboardMarkup([
            [kb.InlineKeyboardButton("🔥 نعم، إلغاء الربط", callback_data=f"unlink_entity_confirm:{container_id}")],
            [kb.InlineKeyboardButton("❌ تراجع", callback_data=f"automation_menu:{container_id}")]
        ])
        await query.message.edit_text(text, reply_markup=keyboard)

    elif data.startswith("unlink_entity_confirm:"):
        container_id = int(data.split(':')[1])
        db_automation.delete_linked_entity(container_id, user_id)
        await query.answer("✅ تم إلغاء الربط بنجاح.")
        await automation.show_automation_menu(update, context, container_id)

    # --- Deletion ---
    elif data.startswith("delete_container_prompt:"):
        await admin.delete_container_prompt(update, context)

    elif data.startswith("delete_container_confirm:"):
        await admin.delete_container_confirm(update, context)

    elif data.startswith("delete_item_prompt:"):
        await admin.delete_item_prompt(update, context)

    elif data.startswith("delete_item_confirm:"):
        await admin.delete_item_confirm(update, context)

    elif data.startswith("undo_delete_item:"):
        await admin.undo_delete_item(update, context)

    # --- Leaving Shared Items ---
    elif data.startswith("leave_item_prompt_container:"):
        await admin.leave_item_prompt_container(update, context)

    elif data.startswith("leave_item_confirm_container:"):
        await admin.leave_item_confirm_container(update, context)

    # --- New Feature: AI Guide ---
    elif data == "ask_ai_guide":
        # We need to transition to a conversation state if possible, but button callback cannot simply "return state".
        # However, start and other handlers set state via ConversationHandler entry points.
        # But here we are inside a button handler.
        # If 'ask_ai_guide_start' is an entry point, we can't switch to it easily from here if it is not a CallbackQueryHandler in the ConversationHandler ENTRY POINTS.
        # It IS an entry point. But usually ConversationHandlers are top-level.
        # If we call 'ask_ai_guide_start', it returns a state. But we are inside 'button_press_router' which returns None.
        # This implies 'button_press_router' is NOT the conversation handler itself, but a function CALLED by it?
        # No, 'button_press_router' IS usually the handler.
        # If 'ask_ai_guide' is a separate ConversationHandler, we must trigger it.
        # But we can't trigger another handler from inside a handler easily in PTB without returning a state if we are IN a conversation.
        # Check 'main.py' structure. We haven't created it yet but we know the structure.
        # Assuming 'ask_ai_guide' is a separate ConversationHandler with 'ask_ai_guide' pattern as entry point.
        # If 'button_press_router' handles 'ask_ai_guide', then 'ask_ai_guide' conversation must be Nested or handled differently.
        # OR: 'ask_ai_guide' is just a function that sets user context and we use a message handler state?
        # The file 'handlers.py' had 'ask_ai_guide' as an entry point for a ConversationHandler?
        # Let's check original 'handlers.py'. 
        pass 
        # Actually 'ask_ai_guide_start' was used as entry point for 'guide_conv'.
        # And 'button_press_router' handles callbacks.
        # If 'ask_ai_guide' is a callback button, 'button_press_router' will catch it if it's registered as a global CallbackQueryHandler.
        # If we return 'AWAITING_GUIDE_QUESTION', it only works if we are INSIDE that conversation check.
        # But 'ask_ai_guide_start' is the ENTRY POINT.
        # So we should return ConversationHandler.END here? No.
        # If the button is clicked, we want to START the conversation.
        # So 'button_press_router' should probably NOT handle 'ask_ai_guide' if it's meant to be an entry point for a separate conversation handler.
        # We should remove 'ask_ai_guide' from here and let the specific ConversationHandler catch it?
        # Yes, if 'ask_ai_guide' pattern is caught by 'guide_conv' entry points.
        # So I will NOT include 'ask_ai_guide' here, assuming main.py routes it to the conversation handler directly.
        # Wait, if `button_press_router` is a "fall-through" or global handler, it might catch it.
        # I'll check `main.py` later. For now I'll comment it out or leave it to be safe.
        # If I leave it, it executes the function but the state return value is lost if this handler isn't part of that conv.
        
        # In original code 'ask_ai_guide_start' was an async function returning int.
        # Calling it here `await main_menu.ask_ai_guide_start(update, context)` executes logic (sends message).
        # But the state transition to `AWAITING_GUIDE_QUESTION` only happens if `button_press_router` is the entry point or part of the conv.
        # Usually separate conversations have separate entry points.
        # I will remove 'ask_ai_guide' from here and ensure `main.py` registers it correctly.
        # Same for 'link_channel_start' and 'new_container_prompt' etc.
        # Wait! 'new_container_prompt' is triggered by "new_container_root:..." button.
        # If 'button_press_router' catches this, it consumes the update.
        # So 'button_press_router' should NOT catch things that are entry points for other conversations, UNLESS 'button_press_router' IS the entry point?
        # Providing a single entry point for multiple conversations is hard.
        # Typically one registers multiple ConversationHandlers with different `entry_points` filters (e.g. Pattern('^new_container...')).
        # So I will remove all Conversation Starting patterns from `button_press_router` and rely on `main.py` to route them to valid ConversationHandlers.
        # Patterns to remove/ignore (let main.py handle):
        # - "new_container_root:..."
        # - "new_container_sub:..."
        # - "rename_container:..."
        # - "add_items:..."
        # - "link_channel_start:..."
        # - "link_group_start:..." -> actually this is just a dialogue, not a conversation state? 'link_group_start' just sends a message with token. It doesn't enter state. So it CAN remain here.
        # - "ask_ai_guide"
        
        # 'link_group_start' in `automation.py` is `async def link_group_start`. It returns None (implicit). It's not a conversation. So it stays.
        # 'link_channel_start' returns `AWAITING_CHANNEL_FORWARD`. It IS a conversation. So remove from here.
        
        # So:
        # Remove: new_container_*, rename_container_*, add_items_*, link_channel_start_*, ask_ai_guide.
        # Keep: link_group_start (token based), delete_*, settings_*, share_*, navigation stuff.
        
    # Check 'check_subscription' callback?
    if data == 'check_subscription':
        await main_menu.check_subscription_callback(update, context)
