import os
from telegram import Update
from telegram.ext import ContextTypes
from app.shared.database import users as db_users
from app.shared import config

async def check_user_updates(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user:
        return

    # 1. Update basic info
    user_id = user.id
    first_name = user.first_name
    last_name = user.last_name
    username = user.username
    language_code = user.language_code
    is_premium = getattr(user, 'is_premium', False)
    
    profile_photo_path = None

    # Logic: Check if profile photo exists locally. If yes, skip download.
    save_dir = os.path.join(os.getcwd(), 'static', 'profiles')
    os.makedirs(save_dir, exist_ok=True)
    filename = f"{user_id}.jpg"
    expected_path = os.path.join(save_dir, filename)

    if not os.path.exists(expected_path):
        should_check_photo = True
    else:
        should_check_photo = False
        profile_photo_path = f"static/profiles/{filename}"

    if should_check_photo:
        try:
            photos = await user.get_profile_photos(limit=1)
            if photos and photos.total_count > 0:
                # Get the biggest photo
                photo = photos.photos[0][-1]
                file_id = photo.file_id
                
                # Check Local API first then Cloud Fallback
                success = False
                try:
                    # 1. Try standard download (Local API)
                    new_file = await context.bot.get_file(file_id)
                    await new_file.download_to_drive(expected_path)
                    success = True
                except Exception as local_err:
                    # 2. If Local API fails (Not Found), try Cloud API
                    print(f"Local API download failed ({local_err}), retrying with Cloud API...")
                    success = await download_directly_from_cloud(config.TELEGRAM_BOT_TOKEN, file_id, expected_path)
                
                if success:
                    profile_photo_path = f"static/profiles/{filename}"
                    print(f"✅ Profile photo saved: {profile_photo_path}")

        except Exception as e:
            print(f"Warning: Could not download profile photo for {user_id}: {e}")
            profile_photo_path = None

    # Database update
    db_users.add_user_if_not_exists(
        user_id=user_id,
        first_name=first_name,
        last_name=last_name,
        username=username,
        language_code=language_code,
        is_premium=is_premium,
        profile_photo_path=profile_photo_path
    )