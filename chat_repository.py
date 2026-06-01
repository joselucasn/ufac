"""
chat_repository.py — Persistência do chat por O.S. (SQLite)
"""
import sqlite3
import os
from datetime import datetime, timezone
from typing import Optional

DB_PATH = os.path.join(os.path.dirname(__file__), "chat_ufac.db")


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """Cria tabela messages se não existir"""
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER NOT NULL,
            autor_tipo TEXT NOT NULL CHECK(autor_tipo IN ('cliente', 'interno')),
            mensagem TEXT NOT NULL,
            timestamp TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_messages_task_id ON messages(task_id)
    """)
    conn.commit()
    conn.close()


def add_message(task_id: int, autor_tipo: str, mensagem: str) -> int:
    """Adiciona mensagem ao chat de uma O.S. Retorna o id da mensagem"""
    sanitized = mensagem.replace("<", "&lt;").replace(">", "&gt;")
    conn = get_connection()
    now = datetime.now(timezone.utc).isoformat()
    cursor = conn.execute(
        "INSERT INTO messages (task_id, autor_tipo, mensagem, timestamp) VALUES (?, ?, ?, ?)",
        (task_id, autor_tipo, sanitized, now),
    )
    conn.commit()
    msg_id = cursor.lastrowid
    conn.close()
    return msg_id


def get_messages(task_id: int, limit: int = 200) -> list[dict]:
    """Retorna histórico de mensagens de uma O.S."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, task_id, autor_tipo, mensagem, timestamp FROM messages WHERE task_id = ? ORDER BY timestamp ASC LIMIT ?",
        (task_id, limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_task_messages(task_id: int):
    """Remove todas as mensagens de uma O.S. (segurança)"""
    conn = get_connection()
    conn.execute("DELETE FROM messages WHERE task_id = ?", (task_id,))
    conn.commit()
    conn.close()


# Inicializa na importação
init_db()
