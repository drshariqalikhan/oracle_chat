import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "oracle_chat.db"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class MemoryService:
    def __init__(
        self,
        db_path: Path | str = DEFAULT_DB_PATH,
        max_messages: int = 40,
        max_doc_chars: int = 24000,
    ) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.max_messages = max_messages
        self.max_doc_chars = max_doc_chars
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES sessions (id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS documents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    file_id TEXT NOT NULL,
                    filename TEXT NOT NULL,
                    text TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES sessions (id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id);
                CREATE INDEX IF NOT EXISTS idx_documents_session ON documents(session_id);
                """
            )

    @staticmethod
    def create_session_id() -> str:
        return uuid4().hex

    def ensure_session(self, session_id: str, title: str = "New Chat") -> str:
        cleaned_id = session_id.strip() or self.create_session_id()
        now = utc_now_iso()
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO sessions (id, title, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                """,
                (cleaned_id, title, now, now),
            )
        return cleaned_id

    def list_sessions(self) -> list[dict[str, Any]]:
        with self._get_connection() as conn:
            rows = conn.execute(
                """
                SELECT s.id, s.title, s.created_at, s.updated_at,
                       COUNT(m.id) AS message_count
                FROM sessions s
                LEFT JOIN messages m ON s.id = m.session_id
                GROUP BY s.id
                ORDER BY s.updated_at DESC
                """
            ).fetchall()

            return [
                {
                    "id": row["id"],
                    "title": row["title"],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                    "message_count": row["message_count"],
                }
                for row in rows
            ]

    def get_session_info(self, session_id: str) -> dict[str, Any] | None:
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT id, title, created_at, updated_at FROM sessions WHERE id = ?",
                (session_id,),
            ).fetchone()
            if not row:
                return None
            return dict(row)

    def get_history(self, session_id: str, limit: int | None = None) -> list[dict[str, str]]:
        effective_limit = limit or self.max_messages
        with self._get_connection() as conn:
            rows = conn.execute(
                """
                SELECT role, content FROM (
                    SELECT id, role, content FROM messages
                    WHERE session_id = ?
                    ORDER BY id DESC
                    LIMIT ?
                ) ORDER BY id ASC
                """,
                (session_id, effective_limit),
            ).fetchall()

            return [{"role": row["role"], "content": row["content"]} for row in rows]

    def append_turn(
        self,
        session_id: str,
        user_message: str,
        assistant_reply: str,
    ) -> list[dict[str, str]]:
        self.ensure_session(session_id)
        now = utc_now_iso()

        with self._get_connection() as conn:
            conn.execute(
                "INSERT INTO messages (session_id, role, content, created_at) VALUES (?, 'user', ?, ?)",
                (session_id, user_message, now),
            )
            conn.execute(
                "INSERT INTO messages (session_id, role, content, created_at) VALUES (?, 'assistant', ?, ?)",
                (session_id, assistant_reply, now),
            )

            # Auto-title session from the first user message if still default
            current = conn.execute(
                "SELECT title FROM sessions WHERE id = ?", (session_id,)
            ).fetchone()
            if current and current["title"] in ("New Chat", "Chat"):
                clean_title = user_message.strip()
                if clean_title.startswith("[Uploaded"):
                    clean_title = clean_title.split("]", 1)[-1].strip() or clean_title
                snippet = (clean_title[:38] + "…") if len(clean_title) > 40 else clean_title
                conn.execute(
                    "UPDATE sessions SET title = ?, updated_at = ? WHERE id = ?",
                    (snippet or "New Chat", now, session_id),
                )
            else:
                conn.execute(
                    "UPDATE sessions SET updated_at = ? WHERE id = ?",
                    (now, session_id),
                )

        return self.get_history(session_id)

    def attach_document(
        self,
        session_id: str,
        file_id: str,
        filename: str,
        text: str,
    ) -> None:
        self.ensure_session(session_id)
        now = utc_now_iso()
        trimmed_text = text[: self.max_doc_chars]

        with self._get_connection() as conn:
            conn.execute(
                "DELETE FROM documents WHERE session_id = ? AND file_id = ?",
                (session_id, file_id),
            )
            conn.execute(
                """
                INSERT INTO documents (session_id, file_id, filename, text, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (session_id, file_id, filename, trimmed_text, now),
            )
            conn.execute(
                "UPDATE sessions SET updated_at = ? WHERE id = ?",
                (now, session_id),
            )

    def get_documents_context(self, session_id: str) -> str:
        with self._get_connection() as conn:
            rows = conn.execute(
                """
                SELECT filename, text FROM documents
                WHERE session_id = ?
                ORDER BY id DESC
                LIMIT 2
                """,
                (session_id,),
            ).fetchall()

            if not rows:
                return ""

            sections = [
                f"Document: {row['filename']}\n--- BEGIN DOCUMENT ---\n{row['text']}\n--- END DOCUMENT ---"
                for row in reversed(rows)
            ]
            return "\n\n".join(sections)

    def clear_session(self, session_id: str) -> None:
        with self._get_connection() as conn:
            conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
