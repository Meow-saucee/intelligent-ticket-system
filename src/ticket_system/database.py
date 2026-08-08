from contextlib import contextmanager
import sqlite3
from pathlib import Path


SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY CHECK (version > 0)
);

CREATE TABLE IF NOT EXISTS ticket_sequences (
    day TEXT PRIMARY KEY CHECK (length(day) = 8),
    value INTEGER NOT NULL CHECK (value > 0)
);

CREATE TABLE IF NOT EXISTS tickets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE CHECK (length(trim(public_id)) > 0),
    title TEXT NOT NULL CHECK (length(trim(title)) > 0),
    description TEXT NOT NULL CHECK (length(trim(description)) > 0),
    submitter TEXT NOT NULL CHECK (length(trim(submitter)) > 0),
    status TEXT NOT NULL DEFAULT 'new' CHECK (status IN ('new', 'triaged', 'in_progress', 'resolved', 'closed')),
    category TEXT NOT NULL DEFAULT 'unclassified' CHECK (category IN ('unclassified', 'account_access', 'software', 'network', 'hardware', 'facilities', 'other')),
    priority TEXT NOT NULL DEFAULT 'P2' CHECK (priority IN ('P0', 'P1', 'P2', 'P3')),
    version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0),
    fingerprint TEXT NOT NULL CHECK (length(trim(fingerprint)) > 0),
    created_at TEXT NOT NULL CHECK (length(trim(created_at)) > 0),
    updated_at TEXT NOT NULL CHECK (length(trim(updated_at)) > 0),
    seed_key TEXT UNIQUE
);

CREATE TABLE IF NOT EXISTS ai_suggestions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id INTEGER NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
    model TEXT NOT NULL CHECK (length(trim(model)) > 0),
    prompt_version TEXT NOT NULL CHECK (length(trim(prompt_version)) > 0),
    original_category TEXT CHECK (original_category IS NULL OR original_category IN ('unclassified', 'account_access', 'software', 'network', 'hardware', 'facilities', 'other')),
    original_priority TEXT CHECK (original_priority IS NULL OR original_priority IN ('P0', 'P1', 'P2', 'P3')),
    summary TEXT,
    reason TEXT,
    raw_response TEXT,
    status TEXT NOT NULL CHECK (status IN ('pending', 'confirmed', 'modified', 'rejected', 'failed')),
    created_at TEXT NOT NULL CHECK (length(trim(created_at)) > 0),
    final_category TEXT CHECK (final_category IS NULL OR final_category IN ('account_access', 'software', 'network', 'hardware', 'facilities', 'other')),
    final_priority TEXT CHECK (final_priority IS NULL OR final_priority IN ('P0', 'P1', 'P2', 'P3')),
    reviewer TEXT,
    reviewed_at TEXT,
    failure_code TEXT
);

CREATE TABLE IF NOT EXISTS audit_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id INTEGER NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL CHECK (length(trim(event_type)) > 0),
    actor TEXT,
    payload TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL CHECK (length(trim(created_at)) > 0)
);

CREATE INDEX IF NOT EXISTS idx_tickets_status ON tickets(status);
CREATE INDEX IF NOT EXISTS idx_tickets_category ON tickets(category);
CREATE INDEX IF NOT EXISTS idx_tickets_priority ON tickets(priority);
CREATE INDEX IF NOT EXISTS idx_tickets_submitter ON tickets(submitter);
CREATE INDEX IF NOT EXISTS idx_tickets_fingerprint_created_at ON tickets(fingerprint, created_at);
CREATE INDEX IF NOT EXISTS idx_audit_events_ticket_created_at ON audit_events(ticket_id, created_at, id);
CREATE INDEX IF NOT EXISTS idx_ai_suggestions_ticket_created_at ON ai_suggestions(ticket_id, created_at);
"""


def connect_database(path: str | Path) -> sqlite3.Connection:
    database_path = Path(path)
    database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(database_path), isolation_level=None)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA busy_timeout = 5000")
    return connection


def initialize_database(connection: sqlite3.Connection) -> None:
    connection.executescript(SCHEMA)
    connection.execute("INSERT OR IGNORE INTO schema_version(version) VALUES (?)", (1,))


@contextmanager
def immediate_transaction(connection: sqlite3.Connection):
    connection.execute("BEGIN IMMEDIATE")
    try:
        yield
    except BaseException:
        connection.rollback()
        raise
    else:
        connection.commit()
