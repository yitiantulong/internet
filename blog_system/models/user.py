import hashlib
import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List

from database import Database


class UserModel:
    def __init__(self, database: Database) -> None:
        self.database = database

    def create_user(self, username: str, password: str, display_name: Optional[str] = None, email: Optional[str] = None) -> bool:
        if self.get_user_by_username(username) is not None:
            return False
        if display_name is None:
            display_name = username
        now = datetime.utcnow().isoformat()
        password_hash = self._hash_password(password)
        self.database.execute(
            """
            INSERT INTO users (username, password_hash, display_name, email, bio, avatar_url, role, is_vip, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                username,
                password_hash,
                display_name,
                email,
                "",
                "",
                "user",
                0,
                now,
                now,
            ),
        )
        return True

    def update_profile(self, user_id: int, display_name: str, bio: str, email: Optional[str], is_vip: bool) -> None:
        now = datetime.utcnow().isoformat()
        self.database.execute(
            """
            UPDATE users
            SET display_name = ?, bio = ?, email = ?, is_vip = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                display_name,
                bio,
                email,
                1 if is_vip else 0,
                now,
                user_id,
            ),
        )

    def list_users(self) -> List[Dict[str, Any]]:
        rows = self.database.fetch_all(
            """
            SELECT id, username, display_name, email, bio, role, is_vip, created_at, updated_at
            FROM users
            ORDER BY created_at DESC
            """
        )
        result: List[Dict[str, Any]] = []
        for row in rows:
            result.append(self._map_user_row(row))
        return result

    def get_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        row = self.database.fetch_one(
            """
            SELECT id, username, password_hash, display_name, email, bio, role, is_vip, created_at, updated_at
            FROM users
            WHERE username = ?
            """,
            (username,),
        )
        if row is None:
            return None
        return self._map_user_row(row, include_password=True)

    def get_user_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        row = self.database.fetch_one(
            """
            SELECT id, username, password_hash, display_name, email, bio, role, is_vip, created_at, updated_at
            FROM users
            WHERE id = ?
            """,
            (user_id,),
        )
        if row is None:
            return None
        return self._map_user_row(row, include_password=True)

    def verify_password(self, username: str, password: str) -> Optional[Dict[str, Any]]:
        user = self.get_user_by_username(username)
        if user is None:
            return None
        expected_hash = user.get("password_hash")
        if expected_hash is None:
            return None
        provided_hash = self._hash_password(password)
        if expected_hash != provided_hash:
            return None
        return user

    def upgrade_role(self, user_id: int, role: str) -> None:
        now = datetime.utcnow().isoformat()
        self.database.execute(
            """
            UPDATE users
            SET role = ?, updated_at = ?
            WHERE id = ?
            """,
            (role, now, user_id),
        )

    def set_vip_status(self, user_id: int, vip: bool) -> None:
        now = datetime.utcnow().isoformat()
        self.database.execute(
            """
            UPDATE users
            SET is_vip = ?, updated_at = ?
            WHERE id = ?
            """,
            (1 if vip else 0, now, user_id),
        )

    def generate_password_token(self, user_id: int) -> str:
        token = uuid.uuid4().hex
        now = datetime.utcnow().isoformat()
        self.database.execute(
            """
            INSERT INTO notifications (id, user_id, message, type, is_read, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                uuid.uuid4().hex,
                user_id,
                f"重置密码令牌：{token}",
                "password_reset",
                0,
                now,
            ),
        )
        return token

    def update_password(self, user_id: int, new_password: str) -> None:
        now = datetime.utcnow().isoformat()
        password_hash = self._hash_password(new_password)
        self.database.execute(
            """
            UPDATE users
            SET password_hash = ?, updated_at = ?
            WHERE id = ?
            """,
            (password_hash, now, user_id),
        )

    def _hash_password(self, raw_password: str) -> str:
        hasher = hashlib.sha256()
        hasher.update(raw_password.encode("utf-8"))
        return hasher.hexdigest()

    def _map_user_row(self, row: Any, include_password: bool = False) -> Dict[str, Any]:
        user_dict: Dict[str, Any] = {
            "id": row["id"],
            "username": row["username"],
            "display_name": row["display_name"],
            "email": row["email"],
            "bio": row["bio"],
            "role": row["role"],
            "is_vip": bool(row["is_vip"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }
        if include_password:
            user_dict["password_hash"] = row["password_hash"]
        return user_dict

