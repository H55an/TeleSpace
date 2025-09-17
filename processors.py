# processors.py
import re
from telegram import Message
from telegram.ext import ContextTypes
from telegram.error import Forbidden
import keyboards as kb
import database as db

class EntityProcessor:
    """Base class for processing updates from different entity types."""

    async def process_message(self, message: Message, linked_entity: dict, context: ContextTypes.DEFAULT_TYPE, saving_function) -> None:
        """
        Orchestrates the message processing workflow. This is the main entry point for the handler.
        """
        entity_id = message.chat.id
        message_id = message.message_id
        section_id = linked_entity['container_id']
        user_id = linked_entity['user_id']

        # 1. Get all available folders for the section.
        all_folders_in_section = db.get_all_folders_recursively(section_id)
        if not all_folders_in_section:
            return # No folders to archive to.

        # 2. Determine target folders based on entity type and content.
        current_matched_folder_ids = await self.get_target_folders(message, linked_entity, all_folders_in_section)

        # 3. Get previously archived folders for this message.
        previously_archived = db.get_archived_folders_for_content(entity_id, message_id)
        previously_archived_ids = set(previously_archived.keys())

        # 4. Calculate changes.
        folders_to_add = current_matched_folder_ids - previously_archived_ids
        folders_to_remove = previously_archived_ids - current_matched_folder_ids

        # 5. Execute deletions.
        for folder_id in folders_to_remove:
            item_id_to_delete = previously_archived.get(folder_id)
            if item_id_to_delete:
                db.delete_item(item_id_to_delete, user_id)
                db.remove_archived_content(entity_id, message_id, folder_id)
                print(f"Removed item {item_id_to_delete} from folder {folder_id} for message {message_id}")

        # 6. Execute additions.
        if folders_to_add:
            item_data = await saving_function(message)
            if item_data:
                for folder_id in folders_to_add:
                    if folder_id not in previously_archived_ids:
                        item_id = db.add_item(container_id=folder_id, user_id=user_id, **item_data)
                        if item_id:
                            db.add_archived_content(entity_id, message_id, folder_id, item_id)
                            print(f"Archived message {message_id} to folder {folder_id} with item_id {item_id}")

        # 7. Update UI if necessary.
        final_archived_folder_ids = current_matched_folder_ids
        await self.update_ui(context, message, linked_entity, final_archived_folder_ids, all_folders_in_section)

    async def get_target_folders(self, message, linked_entity, all_folders_in_section) -> set:
        """
        Determines the target folder IDs based on the message and entity type.
        Returns a set of folder IDs.
        """
        raise NotImplementedError("Each processor must implement this method.")

    async def update_ui(self, context: ContextTypes.DEFAULT_TYPE, message, linked_entity, final_folder_ids, all_folders_in_section):
        """
        Updates the user interface (e.g., inline keyboard) after archiving.
        """
        raise NotImplementedError("Each processor must implement this method.")

class ChannelProcessor(EntityProcessor):
    """Processes messages and UI for linked channels."""
    async def get_target_folders(self, message, linked_entity, all_folders_in_section) -> set:
        text = message.text or message.caption or ""
        hashtags = set(re.findall(r"#(\w+)", text))
        normalized_hashtags = {tag.replace('_', ' ').lower() for tag in hashtags}
        
        folder_name_map = {folder['name'].lower(): folder['id'] for folder in all_folders_in_section}
        
        matched_folder_ids = {folder_name_map[ht] for ht in normalized_hashtags if ht in folder_name_map}
        return matched_folder_ids

    async def update_ui(self, context: ContextTypes.DEFAULT_TYPE, message, linked_entity, final_folder_ids, all_folders_in_section):
        folder_id_map = {folder['id']: folder['name'] for folder in all_folders_in_section}
        final_folders_for_keyboard = [
            {'id': fid, 'name': folder_id_map[fid]} 
            for fid in final_folder_ids 
            if fid in folder_id_map
        ]

        try:
            bot_username = (await context.bot.get_me()).username
            keyboard = kb.build_channel_post_keyboard(final_folders_for_keyboard, linked_entity['container_id'], bot_username)
            
            await context.bot.edit_message_reply_markup(
                chat_id=message.chat.id,
                message_id=message.message_id,
                reply_markup=keyboard
            )
        except Forbidden as e:
            print(f"Failed to edit reply markup for message {message.message_id} in channel {message.chat.id}. Reason: {e}")
        except Exception as e:
            print(f"An unexpected error occurred while editing reply markup: {e}")

class GroupProcessor(EntityProcessor):
    """Processes messages and UI for linked groups."""
    async def get_target_folders(self, message, linked_entity, all_folders_in_section) -> set:
        # NOTE: This is a simplified implementation. It does not yet handle
        # topic-based groups as described in the specification, as that requires
        # a more complex setup to map thread_ids to topic names.
        # For now, it searches for hashtag folders within the entire linked section.
        text = message.text or message.caption or ""
        hashtags = set(re.findall(r"#(\w+)", text))
        if not hashtags:
            return set()
            
        normalized_hashtags = {tag.replace('_', ' ').lower() for tag in hashtags}

        folder_name_map = {folder['name'].lower(): folder['id'] for folder in all_folders_in_section}
        
        matched_folder_ids = {folder_name_map[ht] for ht in normalized_hashtags if ht in folder_name_map}
        return matched_folder_ids

    async def update_ui(self, context: ContextTypes.DEFAULT_TYPE, message, linked_entity, final_folder_ids, all_folders_in_section):
        # Do nothing for groups to ensure silent archiving
        pass