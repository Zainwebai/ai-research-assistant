"""
Persistent research library using SQLite — basic Zotero-style reference manager.
Saves papers with collections (folders), tags, and notes, permanently,
to a local file (research_library.db).
"""

import sqlite3

DB_PATH = "research_library.db"


def init_db():
    """
    Creates the saved_papers table if it doesn't exist, and adds any new
    columns (collection, tags) to an existing table without losing old data.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS saved_papers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            authors TEXT,
            year TEXT,
            source TEXT,
            url TEXT,
            abstract TEXT,
            notes TEXT,
            collection TEXT DEFAULT 'General',
            tags TEXT DEFAULT '',
            saved_at TEXT
        )
    """)

    # Safe migration: add columns if this is an older database from before
    # collections/tags existed, without touching existing saved papers.
    cursor.execute("PRAGMA table_info(saved_papers)")
    existing_columns = [row[1] for row in cursor.fetchall()]

    if "collection" not in existing_columns:
        cursor.execute("ALTER TABLE saved_papers ADD COLUMN collection TEXT DEFAULT 'General'")
    if "tags" not in existing_columns:
        cursor.execute("ALTER TABLE saved_papers ADD COLUMN tags TEXT DEFAULT ''")

    conn.commit()
    conn.close()


def save_paper(title, authors, year, source, url, abstract, notes="", collection="General", tags=""):
    """Saves one paper permanently to the library, into a given collection, with optional tags."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO saved_papers (title, authors, year, source, url, abstract, notes, collection, tags, saved_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
    """, (title, authors, year, source, url, abstract, notes, collection or "General", tags))
    conn.commit()
    conn.close()


def get_all_saved_papers(collection=None):
    """
    Returns saved papers, most recently saved first.
    If collection is given, only returns papers in that collection.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    if collection and collection != "All collections":
        cursor.execute(
            "SELECT * FROM saved_papers WHERE collection = ? ORDER BY saved_at DESC",
            (collection,)
        )
    else:
        cursor.execute("SELECT * FROM saved_papers ORDER BY saved_at DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_all_collections():
    """Returns the distinct list of collection names currently in use, for the filter dropdown."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT collection FROM saved_papers ORDER BY collection ASC")
    rows = cursor.fetchall()
    conn.close()
    return [row[0] for row in rows if row[0]]


def update_paper_details(paper_id, collection, tags, notes):
    """Updates a saved paper's collection, tags, and notes (used by the edit form in the UI)."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE saved_papers
        SET collection = ?, tags = ?, notes = ?
        WHERE id = ?
    """, (collection or "General", tags, notes, paper_id))
    conn.commit()
    conn.close()


def delete_paper(paper_id):
    """Removes one saved paper by its id."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM saved_papers WHERE id = ?", (paper_id,))
    conn.commit()
    conn.close()


def is_paper_saved(title):
    """Checks whether a paper with this exact title is already saved, to avoid duplicates."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM saved_papers WHERE title = ?", (title,))
    count = cursor.fetchone()[0]
    conn.close()
    return count > 0