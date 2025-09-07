PAGE_SIZE = 10

# Conversation states
(
    AWAITING_CONTAINER_NAME,    # For creating new sections or folders
    AWAITING_RENAME_INPUT,      # For renaming any container
    AWAITING_ITEMS_FOR_UPLOAD   # For uploading items to a folder
) = range(3)
