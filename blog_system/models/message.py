import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from database import Database


class MessageModel:
    def __init__(self, database: Database) -> None:
        self.database = database

    def send_message(self, sender_id: int, receiver_id: int, content: str) -> str:
        message_id = uuid.uuid4().hex
        now = datetime.utcnow().isoformat()
        self.database.execute(
            """
            INSERT INTO messages (
                id,
                sender_id,
                receiver_id,
                content,
                status,
                created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                message_id,
                sender_id,
                receiver_id,
                content,
                "normal",
                now,
            ),
        )
        return message_id

    def get_inbox_messages(self, user_id: int) -> List[Dict[str, Any]]:
        rows = self.database.fetch_all(
            """
            SELECT
                messages.id,
                messages.sender_id,
                messages.receiver_id,
                messages.content,
                messages.status,
                messages.created_at,
                sender.username AS sender_username,
                sender.display_name AS sender_display_name
            FROM messages
            INNER JOIN users AS sender ON sender.id = messages.sender_id
            WHERE messages.receiver_id = ? AND messages.status IN ('normal', 'read')
            ORDER BY messages.created_at DESC
            """,
            (user_id,),
        )
        result: List[Dict[str, Any]] = []
        for row in rows:
            result.append({
                "id": row["id"],
                "sender_id": row["sender_id"],
                "receiver_id": row["receiver_id"],
                "content": row["content"],
                "status": row["status"],
                "created_at": row["created_at"],
                "sender": {
                    "username": row["sender_username"],
                    "display_name": row["sender_display_name"],
                },
            })
        return result

    def get_sent_messages(self, user_id: int) -> List[Dict[str, Any]]:
        rows = self.database.fetch_all(
            """
            SELECT
                messages.id,
                messages.sender_id,
                messages.receiver_id,
                messages.content,
                messages.status,
                messages.created_at,
                receiver.username AS receiver_username,
                receiver.display_name AS receiver_display_name
            FROM messages
            INNER JOIN users AS receiver ON receiver.id = messages.receiver_id
            WHERE messages.sender_id = ? AND messages.status IN ('normal', 'read')
            ORDER BY messages.created_at DESC
            """,
            (user_id,),
        )
        result: List[Dict[str, Any]] = []
        for row in rows:
            result.append({
                "id": row["id"],
                "sender_id": row["sender_id"],
                "receiver_id": row["receiver_id"],
                "content": row["content"],
                "status": row["status"],
                "created_at": row["created_at"],
                "receiver": {
                    "username": row["receiver_username"],
                    "display_name": row["receiver_display_name"],
                },
            })
        return result

    def get_trash_messages(self, user_id: int) -> List[Dict[str, Any]]:
        rows = self.database.fetch_all(
            """
            SELECT
                messages.id,
                messages.sender_id,
                messages.receiver_id,
                messages.content,
                messages.status,
                messages.created_at,
                sender.username AS sender_username,
                sender.display_name AS sender_display_name,
                receiver.username AS receiver_username,
                receiver.display_name AS receiver_display_name
            FROM messages
            INNER JOIN users AS sender ON sender.id = messages.sender_id
            INNER JOIN users AS receiver ON receiver.id = messages.receiver_id
            WHERE (messages.sender_id = ? OR messages.receiver_id = ?) AND messages.status = 'deleted'
            ORDER BY messages.created_at DESC
            """,
            (user_id, user_id),
        )
        result: List[Dict[str, Any]] = []
        for row in rows:
            is_sender = row["sender_id"] == user_id
            other_user = {
                "username": row["receiver_username"] if is_sender else row["sender_username"],
                "display_name": row["receiver_display_name"] if is_sender else row["sender_display_name"],
            }
            result.append({
                "id": row["id"],
                "sender_id": row["sender_id"],
                "receiver_id": row["receiver_id"],
                "content": row["content"],
                "status": row["status"],
                "created_at": row["created_at"],
                "is_sender": is_sender,
                "other_user": other_user,
            })
        return result

    def get_message_by_id(self, message_id: str, user_id: int) -> Optional[Dict[str, Any]]:
        row = self.database.fetch_one(
            """
            SELECT
                messages.id,
                messages.sender_id,
                messages.receiver_id,
                messages.content,
                messages.status,
                messages.created_at,
                sender.username AS sender_username,
                sender.display_name AS sender_display_name,
                receiver.username AS receiver_username,
                receiver.display_name AS receiver_display_name
            FROM messages
            INNER JOIN users AS sender ON sender.id = messages.sender_id
            INNER JOIN users AS receiver ON receiver.id = messages.receiver_id
            WHERE messages.id = ? AND (messages.sender_id = ? OR messages.receiver_id = ?)
            """,
            (message_id, user_id, user_id),
        )
        if row is None:
            return None
        return {
            "id": row["id"],
            "sender_id": row["sender_id"],
            "receiver_id": row["receiver_id"],
            "content": row["content"],
            "status": row["status"],
            "created_at": row["created_at"],
            "sender": {
                "username": row["sender_username"],
                "display_name": row["sender_display_name"],
            },
            "receiver": {
                "username": row["receiver_username"],
                "display_name": row["receiver_display_name"],
            },
        }

    def delete_message(self, message_id: str, user_id: int) -> bool:
        message = self.get_message_by_id(message_id, user_id)
        if not message:
            return False
        self.database.execute(
            """
            UPDATE messages
            SET status = 'deleted'
            WHERE id = ?
            """,
            (message_id,),
        )
        return True

    def restore_message(self, message_id: str, user_id: int) -> bool:
        message = self.get_message_by_id(message_id, user_id)
        if not message or message["status"] != "deleted":
            return False
        self.database.execute(
            """
            UPDATE messages
            SET status = 'normal'
            WHERE id = ?
            """,
            (message_id,),
        )
        return True

    def permanently_delete_message(self, message_id: str, user_id: int) -> bool:
        message = self.get_message_by_id(message_id, user_id)
        if not message:
            return False
        self.database.execute(
            """
            DELETE FROM messages
            WHERE id = ?
            """,
            (message_id,),
        )
        return True

    def mark_as_read(self, message_id: str) -> None:
        self.database.execute(
            """
            UPDATE messages
            SET status = 'read'
            WHERE id = ? AND status = 'normal'
            """,
            (message_id,),
        )

    def list_conversations(self, user_id: int) -> List[Dict[str, Any]]:
        rows = self.database.fetch_all(
            """
            SELECT
                messages.id,
                messages.sender_id,
                messages.receiver_id,
                messages.content,
                messages.status,
                messages.created_at,
                sender.username AS sender_username,
                sender.display_name AS sender_display_name,
                receiver.username AS receiver_username,
                receiver.display_name AS receiver_display_name
            FROM messages
            INNER JOIN users AS sender ON sender.id = messages.sender_id
            INNER JOIN users AS receiver ON receiver.id = messages.receiver_id
            WHERE (messages.sender_id = ? OR messages.receiver_id = ?) AND messages.status IN ('normal', 'read')
            ORDER BY messages.created_at DESC
            """,
            (user_id, user_id),
        )
        result: List[Dict[str, Any]] = []
        for row in rows:
            result.append(self._map_message(row))
        return result

    def list_messages_between(self, user_id: int, target_user_id: int) -> List[Dict[str, Any]]:
        rows = self.database.fetch_all(
            """
            SELECT
                messages.id,
                messages.sender_id,
                messages.receiver_id,
                messages.content,
                messages.status,
                messages.created_at,
                sender.username AS sender_username,
                sender.display_name AS sender_display_name,
                receiver.username AS receiver_username,
                receiver.display_name AS receiver_display_name
            FROM messages
            INNER JOIN users AS sender ON sender.id = messages.sender_id
            INNER JOIN users AS receiver ON receiver.id = messages.receiver_id
            WHERE ((messages.sender_id = ? AND messages.receiver_id = ?)
               OR (messages.sender_id = ? AND messages.receiver_id = ?))
               AND messages.status IN ('normal', 'read')
            ORDER BY messages.created_at ASC
            """,
            (user_id, target_user_id, target_user_id, user_id),
        )
        result: List[Dict[str, Any]] = []
        for row in rows:
            result.append(self._map_message(row))
        return result

    def _map_message(self, row: Any) -> Dict[str, Any]:
        return {
            "id": row["id"],
            "sender_id": row["sender_id"],
            "receiver_id": row["receiver_id"],
            "content": row["content"],
            "status": row["status"],
            "created_at": row["created_at"],
            "sender": {
                "username": row["sender_username"],
                "display_name": row["sender_display_name"],
            },
            "receiver": {
                "username": row["receiver_username"],
                "display_name": row["receiver_display_name"],
            },
        }
