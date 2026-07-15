from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class MetadataStore:
    """Small app-owned index around the hosted conversation store.

    Message history remains in ``ChatSession`` on the Iztro server. SQLite only keeps
    UI metadata that the OpenAI-style session protocol does not own: titles, branch
    relationships, list previews, and the chart tools observed while streaming.
    """

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialize(self) -> None:
        with self._connect() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS conversations (
                    conversation_id TEXT PRIMARY KEY,
                    external_user_id TEXT NOT NULL,
                    title TEXT NOT NULL DEFAULT '新会话',
                    parent_conversation_id TEXT,
                    forked_at_item INTEGER,
                    last_message TEXT NOT NULL DEFAULT '',
                    item_count INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS conversations_user_updated
                    ON conversations (external_user_id, updated_at DESC);

                CREATE TABLE IF NOT EXISTS chart_calls (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id TEXT NOT NULL,
                    item_index INTEGER NOT NULL,
                    tool_name TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE (conversation_id, item_index, tool_name),
                    FOREIGN KEY (conversation_id)
                        REFERENCES conversations(conversation_id) ON DELETE CASCADE
                );
                """
            )

    def ensure_conversation(
        self,
        conversation_id: str,
        external_user_id: str,
        *,
        title: str | None = None,
        parent_conversation_id: str | None = None,
        forked_at_item: int | None = None,
    ) -> dict[str, Any]:
        now = _now()
        with self._connect() as db:
            db.execute(
                """
                INSERT OR IGNORE INTO conversations (
                    conversation_id, external_user_id, title,
                    parent_conversation_id, forked_at_item, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    conversation_id,
                    external_user_id,
                    title or "新会话",
                    parent_conversation_id,
                    forked_at_item,
                    now,
                    now,
                ),
            )
            row = db.execute(
                "SELECT * FROM conversations WHERE conversation_id = ?",
                (conversation_id,),
            ).fetchone()
        return dict(row)

    def get_conversation(self, conversation_id: str) -> dict[str, Any] | None:
        with self._connect() as db:
            row = db.execute(
                "SELECT * FROM conversations WHERE conversation_id = ?",
                (conversation_id,),
            ).fetchone()
        return dict(row) if row else None

    def list_conversations(self, external_user_id: str) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute(
                """
                SELECT * FROM conversations
                WHERE external_user_id = ?
                ORDER BY updated_at DESC
                """,
                (external_user_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def rename_conversation(self, conversation_id: str, title: str) -> None:
        with self._connect() as db:
            db.execute(
                "UPDATE conversations SET title = ?, updated_at = ? WHERE conversation_id = ?",
                (title, _now(), conversation_id),
            )

    def update_activity(
        self,
        conversation_id: str,
        *,
        last_message: str | None = None,
        item_count: int | None = None,
    ) -> None:
        assignments = ["updated_at = ?"]
        values: list[Any] = [_now()]
        if last_message is not None:
            assignments.append("last_message = ?")
            values.append(last_message)
        if item_count is not None:
            assignments.append("item_count = ?")
            values.append(item_count)
        values.append(conversation_id)
        with self._connect() as db:
            db.execute(
                f"UPDATE conversations SET {', '.join(assignments)} WHERE conversation_id = ?",
                values,
            )

    def title_from_first_message(self, conversation_id: str, message: str) -> None:
        title = " ".join(message.split())[:30]
        if len(" ".join(message.split())) > 30:
            title += "…"
        if not title:
            return
        with self._connect() as db:
            db.execute(
                """
                UPDATE conversations
                SET title = ?, updated_at = ?
                WHERE conversation_id = ? AND title = '新会话'
                """,
                (title, _now(), conversation_id),
            )

    def record_chart_calls(
        self,
        conversation_id: str,
        item_index: int,
        tools: list[str],
    ) -> None:
        rows = [
            (conversation_id, item_index, tool, _now())
            for tool in dict.fromkeys(tools)
            if tool
        ]
        if not rows:
            return
        with self._connect() as db:
            db.executemany(
                """
                INSERT OR IGNORE INTO chart_calls (
                    conversation_id, item_index, tool_name, created_at
                ) VALUES (?, ?, ?, ?)
                """,
                rows,
            )

    def copy_chart_calls(
        self,
        source_id: str,
        target_id: str,
        *,
        item_count: int | None,
    ) -> None:
        condition = "" if item_count is None else "AND item_index < ?"
        params: list[Any] = [source_id]
        if item_count is not None:
            params.append(item_count)
        with self._connect() as db:
            rows = db.execute(
                f"SELECT item_index, tool_name FROM chart_calls "
                f"WHERE conversation_id = ? {condition}",
                params,
            ).fetchall()
            db.executemany(
                """
                INSERT OR IGNORE INTO chart_calls (
                    conversation_id, item_index, tool_name, created_at
                ) VALUES (?, ?, ?, ?)
                """,
                [(target_id, row["item_index"], row["tool_name"], _now()) for row in rows],
            )

    def charts_by_item(self, conversation_id: str) -> dict[int, list[str]]:
        with self._connect() as db:
            rows = db.execute(
                """
                SELECT item_index, tool_name FROM chart_calls
                WHERE conversation_id = ?
                ORDER BY item_index, id
                """,
                (conversation_id,),
            ).fetchall()
        result: dict[int, list[str]] = {}
        for row in rows:
            result.setdefault(int(row["item_index"]), []).append(str(row["tool_name"]))
        return result

    def charts_for_conversation(self, conversation_id: str) -> list[str]:
        with self._connect() as db:
            rows = db.execute(
                """
                SELECT tool_name, MIN(id) AS first_seen FROM chart_calls
                WHERE conversation_id = ?
                GROUP BY tool_name
                ORDER BY first_seen
                """,
                (conversation_id,),
            ).fetchall()
        return [str(row["tool_name"]) for row in rows]

    def delete_conversation(self, conversation_id: str) -> None:
        with self._connect() as db:
            db.execute(
                "DELETE FROM conversations WHERE conversation_id = ?",
                (conversation_id,),
            )
