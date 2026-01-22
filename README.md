# TeleSpace

> **Cloud-Native File Management & Smart Automation for Telegram**

**TeleSpace** is a sophisticated Telegram bot designed to transform your chat experience into a powerful cloud storage and file management system. It separates content management from storage, offering a professional hierarchical structure, seamless sharing protocols, and intelligent automation features that integrate directly with your existing Telegram workflow.

## 🚀 Key Features

### 🗂️ Intelligent Organization

Move beyond simple file dumps. TeleSpace introduces a structured two-tier hierarchy:

- **Sections**: Broad categories to group related content (e.g., "Work", "Personal", "Media").
- **Folders**: Dedicated storage units within sections for your files, documents, and media.

### ☁️ Reverse Upload & Storage Gateway

TeleSpace utilizes a **Reverse Upload** mechanism. Files are physically stored in a private, dedicated storage channel (`STORAGE_CHANNEL_ID`) for reliability and permanence, while the bot maintains a metadata database. This ensures:

- **Distributed Retrieval**: Fast and efficient file delivery using `copy_message` logic.
- **Clean Interface**: Users interact with a clean UI, while the "heavy lifting" of storage is handled in the background.

### 🤖 Smart Automation & Hashtags

Link your public Channels or Groups directly to your TeleSpace Sections.

- **Hashtag Archiving**: Simply post in your linked channel with a hashtag matching a folder name (e.g., `#Documents`, `#Images`).
- **Auto-Save**: The bot detects the tag and automatically archives the post into the corresponding TeleSpace folder.

### 🔗 Deep Link Sharing

Streamline data collection and collaboration:

- Generate unique **Deep Links** for specific folders.
- When a user clicks the link, they are instantly taken to an upload session for that specific folder, bypassing navigation menus.

### 🤝 Shared Spaces

Collaborate effectively with team members or friends. Share access to specific sections or folders with granular permission levels (Viewer, Editor, Admin).

## 🛠️ Tech Stack

- **Core**: Python 3.x
- **Framework**: `python-telegram-bot` (v22+)
- **Database**: PostgreSQL
- **Driver**: `psycopg2-binary`
- **Architecture**: Modular Handler System (Navigation, Upload, Automation)

## ⚙️ Installation & Setup

### Prerequisites

- Python 3.9+
- PostgreSQL Database
- A Telegram Bot Token (from @BotFather)
- A dedicated Telegram Channel (for storage)

### Steps

1.  **Clone the Repository**

    ```bash
    git clone https://github.com/username/TeleSpace.git
    cd TeleSpace
    ```

2.  **Install Dependencies**

    ```bash
    pip install -r requirements.txt
    ```

3.  **Environment Configuration**
    Create a `.env` file in the root directory and configure the following:

    ```env
    # Telegram Keys
    TELEGRAM_BOT_TOKEN=your_token_here
    STORAGE_CHANNEL_ID=-100xxxxxxxxxx

    # Database Connection
    DB_HOST=localhost
    DB_PORT=5432
    DB_NAME=telespace
    DB_USER=postgres
    DB_PASSWORD=your_password
    ```

4.  **Run the Bot**
    ```bash
    python -m app.bot.main
    ```

## 📖 Usage Guide

1.  **Initialize**: Send `/start` to open the interactive dashboard.
2.  **Create Structure**: Use the **"My Space"** menu to create your first **Section** and **Folder**.
3.  **Upload**: Open a folder and click **"Add Items"**, or use the Deep Link feature to upload directly.
4.  **Automate**:
    - Navigate to a Section.
    - Click **"Automation"** -> **"Link Channel/Group"**.
    - Follow the instructions to connect your community.
    - Start posting with hashtags!

---

_TeleSpace - Your Personal Cloud on Telegram._
