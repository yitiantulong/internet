import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from database import Database


class SubscriptionModel:
    def __init__(self, database: Database) -> None:
        self.database = database

    def add_subscription(self, user_id: int, subscription_type: str, subscription_value: str) -> None:
        existing = self.database.fetch_one(
            """
            SELECT id FROM subscriptions
            WHERE user_id = ? AND subscription_type = ? AND subscription_value = ?
            """,
            (user_id, subscription_type, subscription_value),
        )
        if existing is not None:
            return
        now = datetime.utcnow().isoformat()
        self.database.execute(
            """
            INSERT INTO subscriptions (id, user_id, subscription_type, subscription_value, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                uuid.uuid4().hex,
                user_id,
                subscription_type,
                subscription_value,
                now,
            ),
        )

    def remove_subscription(self, subscription_id: str) -> None:
        self.database.execute(
            """
            DELETE FROM subscriptions WHERE id = ?
            """,
            (subscription_id,),
        )

    def remove_subscription_by_value(self, user_id: int, subscription_type: str, subscription_value: str) -> None:
        self.database.execute(
            """
            DELETE FROM subscriptions
            WHERE user_id = ? AND subscription_type = ? AND subscription_value = ?
            """,
            (user_id, subscription_type, subscription_value),
        )

    def list_subscriptions(self, user_id: int) -> List[Dict[str, Any]]:
        rows = self.database.fetch_all(
            """
            SELECT id, subscription_type, subscription_value, created_at
            FROM subscriptions
            WHERE user_id = ?
            ORDER BY created_at DESC
            """,
            (user_id,),
        )
        subscriptions: List[Dict[str, Any]] = []
        for row in rows:
            subscriptions.append(
                {
                    "id": row["id"],
                    "type": row["subscription_type"],
                    "value": row["subscription_value"],
                    "created_at": row["created_at"],
                }
            )
        return subscriptions

    def list_author_subscribers(self, author_username: str) -> List[int]:
        rows = self.database.fetch_all(
            """
            SELECT user_id
            FROM subscriptions
            WHERE subscription_type = 'author' AND subscription_value = ?
            """,
            (author_username,),
        )
        subscriber_ids: List[int] = []
        for row in rows:
            subscriber_ids.append(row["user_id"])
        return subscriber_ids

    def get_subscriber_count(self, author_username: str) -> int:
        row = self.database.fetch_one(
            """
            SELECT COUNT(*) as count
            FROM subscriptions
            WHERE subscription_type = 'author' AND subscription_value = ?
            """,
            (author_username,),
        )
        if row is None:
            return 0
        return row["count"] or 0

    def is_subscribed(self, user_id: int, subscription_type: str, subscription_value: str) -> bool:
        row = self.database.fetch_one(
            """
            SELECT id FROM subscriptions
            WHERE user_id = ? AND subscription_type = ? AND subscription_value = ?
            """,
            (user_id, subscription_type, subscription_value),
        )
        return row is not None

    def get_subscription_count(self, user_id: int, subscription_type: Optional[str] = None) -> int:
        if subscription_type:
            row = self.database.fetch_one(
                """
                SELECT COUNT(*) as count
                FROM subscriptions
                WHERE user_id = ? AND subscription_type = ?
                """,
                (user_id, subscription_type),
            )
        else:
            row = self.database.fetch_one(
                """
                SELECT COUNT(*) as count
                FROM subscriptions
                WHERE user_id = ?
                """,
                (user_id,),
            )
        if row is None:
            return 0
        return row["count"] or 0

    def notify_author_subscribers(
        self,
        author_username: str,
        author_display_name: str,
        post_title: str,
        post_id: str,
        exclude_user_id: Optional[int] = None,
    ) -> None:
        subscriber_ids = self.list_author_subscribers(author_username)
        if not subscriber_ids:
            return
        now = datetime.utcnow().isoformat()
        notifications: List[Tuple[str, int, str, str, int, str]] = []
        message = f"{author_display_name} 发布了新文章《{post_title}》"
        for subscriber_id in subscriber_ids:
            if exclude_user_id is not None and subscriber_id == exclude_user_id:
                continue
            notifications.append(
                (
                    uuid.uuid4().hex,
                    subscriber_id,
                    f"{message}，点击查看：/posts/{post_id}",
                    "author_update",
                    0,
                    now,
                )
            )
        if notifications:
            self.database.execute_many(
                """
                INSERT INTO notifications (id, user_id, message, type, is_read, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                notifications,
            )

