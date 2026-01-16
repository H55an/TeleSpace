from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler
from telegram.error import Forbidden
from telegram.helpers import escape_markdown

from app.shared.database import containers as db_containers
from app.shared.database import automation as db_automation
from app.shared.database import users as db_users
from app.bot import keyboards as kb
from app.shared.constants import AWAITING_CHANNEL_FORWARD
from app.bot.processors import PROCESSORS # Need to check if this creates circular dependency

# process_message_for_saving is in upload.py.
# processors.py will import process_message_for_saving? 
# or entity_post_handler calls processor.process_message passing the function.
# The original code passed 'process_message_for_saving' to processor.process_message.
# So we need to import it here.
from .upload import process_message_for_saving

async def show_automation_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, container_id: int):
    """[معدل] يعرض قائمة التحكم في الأتمتة للكيانات (قنوات ومجموعات)."""
    query = update.callback_query
    user_id = update.effective_user.id
    
    details = db_containers.get_container_details(container_id)
    if not details or details['owner_user_id'] != user_id:
        if query:
            await query.answer("ليس لديك الصلاحية للوصول إلى هنا.", show_alert=True)
        else:
            await context.bot.send_message(user_id, "ليس لديك الصلاحية للوصول إلى هنا.")
        return

    linked_entity = db_automation.get_linked_entity_by_container(container_id)
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
    details = db_containers.get_container_details(container_id)
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
    existing_link = db_automation.get_linked_entity_by_entity_id(channel_id)
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
    success = db_automation.link_entity(
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
    details = db_containers.get_container_details(container_id)
    if not details or details['owner_user_id'] != user_id:
        await query.answer("فقط مالك القسم يمكنه ربط المجموعات.", show_alert=True)
        return

    token = db_automation.create_linking_token(user_id, container_id)
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
    token_data = db_automation.get_linking_token_data(token)

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
    existing_link = db_automation.get_linked_entity_by_entity_id(chat.id)
    if existing_link and existing_link['container_id'] != container_id:
        await context.bot.send_message(user_id, f"⚠️ هذه المجموعة مرتبطة بالفعل بقسم آخر. لا يمكن ربط نفس المجموعة مرتين.")
        return

    success = db_automation.link_entity(
        container_id=container_id,
        user_id=user_id,
        entity_id=chat.id,
        entity_name=chat.title,
        entity_type=chat.type,
        is_group_with_topics=chat.is_forum
    )

    if success:
        db_automation.delete_linking_token(token)
        await update.message.reply_text(f"✅ تم ربط هذه المجموعة بنجاح بالقسم المستهدف!")
        
        # --- [جديد] إرسال رسالة تأكيد مع قائمة الأتمتة ---
        container_id = token_data['container_id']
        details = db_containers.get_container_details(container_id)

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
    linked_entity = db_automation.get_linked_entity_by_entity_id(chat.id)

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
    if not db_automation.get_linked_entity_by_entity_id(chat.id):
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
    
    db_automation.add_or_update_topic(chat.id, thread_id, topic_name)
    print(f"Unified topic name updated in DB for chat {chat.id}: Thread {thread_id} -> '{topic_name}'")
