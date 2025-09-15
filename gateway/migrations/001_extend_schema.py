
"""
Script to apply changes to the existing DB without data loss.
Execute with: python gateway/migrations/001_extend_schema.py
"""
import sqlite3
from pathlib import Path
import sys

# Add gateway root to path to allow importing from app
project_root = Path(__file__).resolve().parent.parent # gateway folder
sys.path.insert(0, str(project_root))

DB_PATH = project_root.parent / "data" / "gateway.db"

def add_column_if_not_exists(cursor, table_name, column_name, column_def):
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = [col[1] for col in cursor.fetchall()]
    if column_name not in columns:
        print(f"Adding column '{column_name}' to table '{table_name}'...")
        cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_def}")
    else:
        print(f"Column '{column_name}' already exists in table '{table_name}'.")

def main():
    print(f"Running migration on database: {DB_PATH}")
    if not DB_PATH.exists():
        print("Database not found. It will be created by the application on first run.")
        return

    try:
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()

        # === Create new tables if they don't exist ===

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='task_plans'")
        if not cursor.fetchone():
            print("Creating table 'task_plans'...")
            cursor.execute("""
                CREATE TABLE task_plans (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    status TEXT DEFAULT 'proposed',
                    summary TEXT,
                    created_by TEXT DEFAULT 'ai',
                    created_at DATETIME
                )
            """)
            cursor.execute("CREATE INDEX ix_task_plans_project_id ON task_plans (project_id)")
        else:
            print("Table 'task_plans' already exists.")

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='contexts'")
        if not cursor.fetchone():
            print("Creating table 'contexts'...")
            cursor.execute("""
                CREATE TABLE contexts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id TEXT NOT NULL,
                    scope TEXT NOT NULL,
                    task_id INTEGER,
                    content TEXT NOT NULL,
                    created_by TEXT DEFAULT 'system',
                    source TEXT,
                    version INTEGER DEFAULT 1,
                    is_active BOOLEAN DEFAULT 0,
                    created_at DATETIME
                )
            """)
            cursor.execute("CREATE INDEX ix_contexts_project_id ON contexts (project_id)")
        else:
            print("Table 'contexts' already exists.")

        # === Add new columns to existing tables ===

        # projects table
        add_column_if_not_exists(cursor, "projects", "active_context_id", "INTEGER")
        add_column_if_not_exists(cursor, "projects", "active_plan_id", "INTEGER")
        add_column_if_not_exists(cursor, "projects", "current_task_id", "INTEGER")
        add_column_if_not_exists(cursor, "projects", "status", "TEXT DEFAULT 'draft'")

        # tasks table
        add_column_if_not_exists(cursor, "tasks", "plan_id", "INTEGER")
        add_column_if_not_exists(cursor, "tasks", "idx", "INTEGER DEFAULT 0")
        add_column_if_not_exists(cursor, "tasks", "code", "TEXT")
        add_column_if_not_exists(cursor, "tasks", "mcp_tools", "TEXT")
        add_column_if_not_exists(cursor, "tasks", "deliverables", "TEXT")
        add_column_if_not_exists(cursor, "tasks", "estimates", "TEXT")
        add_column_if_not_exists(cursor, "tasks", "priority", "INTEGER DEFAULT 1")
        add_column_if_not_exists(cursor, "tasks", "started_at", "DATETIME")
        add_column_if_not_exists(cursor, "tasks", "completed_at", "DATETIME")

        # artifacts table
        add_column_if_not_exists(cursor, "artifacts", "task_id", "INTEGER")
        add_column_if_not_exists(cursor, "artifacts", "category", "TEXT")
        add_column_if_not_exists(cursor, "artifacts", "validation_status", "TEXT DEFAULT 'pending'")
        add_column_if_not_exists(cursor, "artifacts", "size_bytes", "INTEGER")

        conn.commit()
        print("\nMigration script finished successfully.")

    except sqlite3.Error as e:
        print(f"An error occurred: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    main()
