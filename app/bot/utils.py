from functools import wraps
from telegram import Update
from telegram.ext import ContextTypes
from app.shared import config

# --- Decorators ---
def check_subscription(func):
    """
    Decorator to check if the user is subscribed to the required channel.
    If not, it asks them to subscribe.
    """
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = update.effective_user.id
        
        # Skip check for developer
        if user_id == config.DEVELOPER_ID:
            return await func(update, context, *args, **kwargs)

        # Skip check if REQUIRED_CHANNEL_ID is not configured
        if config.REQUIRED_CHANNEL_ID == "PLEASE_UPDATE_ME":
             return await func(update, context, *args, **kwargs)

        try:
            member = await context.bot.get_chat_member(chat_id=config.REQUIRED_CHANNEL_ID, user_id=user_id)
            if member.status in ['left', 'kicked', 'restricted']:
                # Import here to avoid circular dependencies if keyboards.py imports utils (unlikely but safe)
                # Actually keyboards might use utils? No.
                # But we need to build the keyboard.
                # Assuming app.bot.keyboards will be available.
                from app.bot.keyboards import get_subscription_keyboard
                
                await update.message.reply_text(
                    "⚠️ عذراً، يجب عليك الاشتراك في قناة البوت لاستخدامه.",
                    reply_markup=get_subscription_keyboard()
                )
                return # Stop execution
        except Exception as e:
            print(f"Error checking subscription: {e}")
            # If error (e.g., bot not admin in channel), pass for now? Or block?
            # Safest is to log and allow, or block if critical. 
            # Original code probably just crashed or allowed.
            # Let's allow but log.
            pass

        return await func(update, context, *args, **kwargs)
    return wrapper
