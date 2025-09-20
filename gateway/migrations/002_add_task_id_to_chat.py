"""Add task_id column to chat_messages table."""

import sqlite3
from pathlib import Path


def migrate():
    """Add task_id column to existing chat_messages table."""
    db_path = Path("data/gateway.db")

    if not db_path.exists():
        print("Database does not exist, skipping migration")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Check if column already exists
        cursor.execute("PRAGMA table_info(chat_messages)")
        columns = [column[1] for column in cursor.fetchall()]

        if 'task_id' not in columns:
            # Add the task_id column
            cursor.execute("ALTER TABLE chat_messages ADD COLUMN task_id INTEGER DEFAULT NULL")
            # Create index for performance
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_chat_messages_task_id ON chat_messages (task_id)")
            conn.commit()
            print("SUCCESS: Added task_id column to chat_messages table")
        else:
            print("SUCCESS: task_id column already exists in chat_messages table")

    except Exception as e:
        print(f"ERROR: Migration failed: {e}")
        conn.rollback()
    finally:
        conn.close()


if __name__ == "__main__":
    migrate()