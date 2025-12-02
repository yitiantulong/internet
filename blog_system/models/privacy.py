import hashlib
from typing import Any, Dict, Optional

from database import Database


class PrivacyModel:
    def __init__(self, database: Database) -> None:
        self.database = database

    def get_privacy_settings(self, user_id: int) -> Dict[str, Any]:
        try:
            user_row = self.database.fetch_one(
                """
                SELECT is_subscription_public FROM users WHERE id = ?
                """,
                (user_id,),
            )
            is_subscription_public = True
            if user_row:
                is_subscription_public = bool(user_row.get("is_subscription_public", 1))
        except Exception:
            is_subscription_public = True
        row = self.database.fetch_one(
            """
            SELECT hide_posts, hide_favorites, access_password_hash
            FROM user_privacy_settings
            WHERE user_id = ?
            """,
            (user_id,),
        )
        if row is None:
            return {
                "hide_posts": False,
                "hide_favorites": False,
                "has_password": False,
                "is_subscription_public": is_subscription_public,
            }
        return {
            "hide_posts": bool(row["hide_posts"]),
            "hide_favorites": bool(row["hide_favorites"]),
            "has_password": bool(row["access_password_hash"]),
            "is_subscription_public": is_subscription_public,
        }

    def update_privacy_settings(
        self,
        user_id: int,
        hide_posts: bool,
        hide_favorites: bool,
        is_subscription_public: bool,
        access_password: Optional[str] = None,
    ) -> None:
        password_hash = None
        if access_password:
            password_hash = self._hash_password(access_password)
        self.database.execute(
            """
            UPDATE users
            SET is_subscription_public = ?
            WHERE id = ?
            """,
            (1 if is_subscription_public else 0, user_id),
        )
        existing = self.database.fetch_one(
            """
            SELECT user_id FROM user_privacy_settings WHERE user_id = ?
            """,
            (user_id,),
        )
        if existing:
            if password_hash:
                self.database.execute(
                    """
                    UPDATE user_privacy_settings
                    SET hide_posts = ?, hide_favorites = ?, access_password_hash = ?
                    WHERE user_id = ?
                    """,
                    (1 if hide_posts else 0, 1 if hide_favorites else 0, password_hash, user_id),
                )
            else:
                self.database.execute(
                    """
                    UPDATE user_privacy_settings
                    SET hide_posts = ?, hide_favorites = ?
                    WHERE user_id = ?
                    """,
                    (1 if hide_posts else 0, 1 if hide_favorites else 0, user_id),
                )
        else:
            self.database.execute(
                """
                INSERT INTO user_privacy_settings (user_id, hide_posts, hide_favorites, access_password_hash)
                VALUES (?, ?, ?, ?)
                """,
                (user_id, 1 if hide_posts else 0, 1 if hide_favorites else 0, password_hash),
            )

    def verify_access_password(self, user_id: int, password: str) -> bool:
        row = self.database.fetch_one(
            """
            SELECT access_password_hash FROM user_privacy_settings WHERE user_id = ?
            """,
            (user_id,),
        )
        if not row or not row["access_password_hash"]:
            return False
        provided_hash = self._hash_password(password)
        return provided_hash == row["access_password_hash"]

    def _hash_password(self, raw_password: str) -> str:
        hasher = hashlib.sha256()
        hasher.update(raw_password.encode("utf-8"))
        return hasher.hexdigest()

