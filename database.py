import sqlite3
import os

DB_NAME = "bot.db"

def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            parent_id INTEGER,
            title TEXT NOT NULL,
            emoji TEXT,
            type TEXT CHECK(type IN ('folder', 'link', 'file', 'text')) NOT NULL DEFAULT 'folder',
            content TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (parent_id) REFERENCES sections(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER UNIQUE NOT NULL,
            username TEXT,
            first_name TEXT,
            joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()

def add_section(title, emoji="", section_type="folder", content=None, parent_id=None):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO sections (parent_id, title, emoji, type, content)
        VALUES (?, ?, ?, ?, ?)
    """, (parent_id, title, emoji, section_type, content))
    conn.commit()
    new_id = cursor.lastrowid
    conn.close()
    return new_id

def get_children(parent_id=None):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, parent_id, title, emoji, type, content
        FROM sections
        WHERE parent_id IS ?
        ORDER BY type DESC, title ASC
    """, (parent_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_section(section_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, parent_id, title, emoji, type, content
        FROM sections WHERE id = ?
    """, (section_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def delete_section(section_id):
    conn = get_db()
    cursor = conn.cursor()

    def get_all_children(pid):
        cursor.execute("SELECT id, type, content FROM sections WHERE parent_id = ?", (pid,))
        children = cursor.fetchall()
        all_ids = []
        for child in children:
            all_ids.append(child["id"])
            if child["type"] == "file" and child["content"]:
                try:
                    os.remove(child["content"])
                except:
                    pass
            all_ids.extend(get_all_children(child["id"]))
        return all_ids

    cursor.execute("SELECT type, content FROM sections WHERE id = ?", (section_id,))
    row = cursor.fetchone()
    if row and row["type"] == "file" and row["content"]:
        try:
            os.remove(row["content"])
        except:
            pass

    to_delete = [section_id] + get_all_children(section_id)
    for sid in to_delete:
        cursor.execute("DELETE FROM sections WHERE id = ?", (sid,))

    conn.commit()
    conn.close()
    return len(to_delete)

def update_section(section_id, title=None, emoji=None, content=None):
    conn = get_db()
    cursor = conn.cursor()
    if title is not None:
        cursor.execute("UPDATE sections SET title = ? WHERE id = ?", (title, section_id))
    if emoji is not None:
        cursor.execute("UPDATE sections SET emoji = ? WHERE id = ?", (emoji, section_id))
    if content is not None:
        cursor.execute("UPDATE sections SET content = ? WHERE id = ?", (content, section_id))
    conn.commit()
    conn.close()

def get_all_sections():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, parent_id, title, emoji, type, content FROM sections ORDER BY id")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]
