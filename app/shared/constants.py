PAGE_SIZE = 10

# Conversation states
(
    AWAITING_CONTAINER_NAME,    # For creating new sections or folders
    AWAITING_RENAME_INPUT,      # For renaming any container
    AWAITING_ITEMS_FOR_UPLOAD,  # For uploading items to a folder
    AWAITING_CHANNEL_FORWARD,   # For linking a channel
    AWAITING_GUIDE_QUESTION     # [جديد] For asking the AI guide
) = range(5)
