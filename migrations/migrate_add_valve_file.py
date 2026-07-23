import sqlite3
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "instance", "valves.db")
if not os.path.exists(DB_PATH):
    DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "valves.db")

conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

c.execute("CREATE TABLE IF NOT EXISTS valve_files ("
          "id INTEGER PRIMARY KEY AUTOINCREMENT, "
          "file_hash VARCHAR(64) UNIQUE NOT NULL, "
          "filename VARCHAR(200) NOT NULL, "
          "file_size INTEGER, "
          "ref_count INTEGER DEFAULT 0, "
          "created_at DATETIME DEFAULT CURRENT_TIMESTAMP"
          ")")

try:
    c.execute("ALTER TABLE valve_documents ADD COLUMN file_id INTEGER REFERENCES valve_files(id)")
except sqlite3.OperationalError as e:
    if "duplicate column" in str(e).lower():
        pass
    else:
        raise

conn.commit()
conn.close()
print("迁移完成")
