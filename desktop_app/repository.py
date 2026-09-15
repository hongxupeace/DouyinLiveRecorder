from __future__ import annotations

import sqlite3
from pathlib import Path

from .domain import Room, utc_now


class DuplicateRoomError(ValueError):
    pass


class RoomRepository:
    """Persist room definitions behind a small, UI-independent interface."""

    def __init__(self, database_path: str | Path):
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(self.database_path)
        self._connection.row_factory = sqlite3.Row
        self._create_schema()

    def _create_schema(self) -> None:
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS rooms (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                url TEXT NOT NULL UNIQUE COLLATE NOCASE,
                platform TEXT NOT NULL,
                monitor_enabled INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        self._connection.commit()

    def list_rooms(self) -> list[Room]:
        rows = self._connection.execute(
            """
            SELECT id, name, url, platform, monitor_enabled, created_at, updated_at
            FROM rooms
            ORDER BY created_at ASC
            """
        ).fetchall()
        return [
            Room(
                id=row["id"],
                name=row["name"],
                url=row["url"],
                platform=row["platform"],
                monitor_enabled=bool(row["monitor_enabled"]),
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            for row in rows
        ]

    def add(self, room: Room) -> None:
        try:
            self._connection.execute(
                """
                INSERT INTO rooms (
                    id, name, url, platform, monitor_enabled, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    room.id,
                    room.name,
                    room.url,
                    room.platform,
                    int(room.monitor_enabled),
                    room.created_at,
                    room.updated_at,
                ),
            )
            self._connection.commit()
        except sqlite3.IntegrityError as error:
            raise DuplicateRoomError("该直播间已经添加") from error

    def set_monitor_enabled(self, room_id: str, enabled: bool) -> None:
        updated_at = utc_now()
        cursor = self._connection.execute(
            """
            UPDATE rooms
            SET monitor_enabled = ?, updated_at = ?
            WHERE id = ?
            """,
            (int(enabled), updated_at, room_id),
        )
        if cursor.rowcount != 1:
            raise KeyError(f"找不到直播间：{room_id}")
        self._connection.commit()

    def delete(self, room_id: str) -> None:
        self._connection.execute("DELETE FROM rooms WHERE id = ?", (room_id,))
        self._connection.commit()

    def close(self) -> None:
        self._connection.close()
