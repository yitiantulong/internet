import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from database import Database


class InteractionModel:
    def __init__(self, database: Database) -> None:
        self.database = database

    def toggle_like(self, user_id: int, post_id: str) -> bool:
        existing = self.database.fetch_one(
            """
            SELECT id FROM likes WHERE user_id = ? AND post_id = ?
            """,
            (user_id, post_id),
        )
        if existing:
            self.database.execute("DELETE FROM likes WHERE id = ?", (existing["id"],))
            return False
        now = datetime.utcnow().isoformat()
        self.database.execute(
            """
            INSERT INTO likes (id, post_id, user_id, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (
                uuid.uuid4().hex,
                post_id,
                user_id,
                now,
            ),
        )
        return True

    def toggle_favorite(self, user_id: int, post_id: str) -> bool:
        existing = self.database.fetch_one(
            """
            SELECT id FROM favorites WHERE user_id = ? AND post_id = ?
            """,
            (user_id, post_id),
        )
        if existing:
            self.database.execute("DELETE FROM favorites WHERE id = ?", (existing["id"],))
            return False
        now = datetime.utcnow().isoformat()
        self.database.execute(
            """
            INSERT INTO favorites (id, post_id, user_id, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (
                uuid.uuid4().hex,
                post_id,
                user_id,
                now,
            ),
        )
        return True

    def count_likes(self, post_id: str) -> int:
        row = self.database.fetch_one(
            """
            SELECT COUNT(1) AS total FROM likes WHERE post_id = ?
            """,
            (post_id,),
        )
        if row is None:
            return 0
        return int(row["total"])

    def count_favorites(self, post_id: str) -> int:
        row = self.database.fetch_one(
            """
            SELECT COUNT(1) AS total FROM favorites WHERE post_id = ?
            """,
            (post_id,),
        )
        if row is None:
            return 0
        return int(row["total"])

    def list_favorite_post_ids(self, user_id: int) -> List[str]:
        rows = self.database.fetch_all(
            """
            SELECT post_id FROM favorites WHERE user_id = ?
            """,
            (user_id,),
        )
        return [row["post_id"] for row in rows]

    def list_like_post_ids(self, user_id: int) -> List[str]:
        rows = self.database.fetch_all(
            """
            SELECT post_id FROM likes WHERE user_id = ?
            """,
            (user_id,),
        )
        return [row["post_id"] for row in rows]

    def delete_post_records(self, post_id: str) -> None:
        self.database.execute(
            """
            DELETE FROM likes WHERE post_id = ?
            """,
            (post_id,),
        )
        self.database.execute(
            """
            DELETE FROM favorites WHERE post_id = ?
            """,
            (post_id,),
        )

