import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from database import Database


class CommentModel:
    def __init__(self, database: Database) -> None:
        self.database = database

    def add_comment(
        self,
        post_id: str,
        author_id: int,
        content: str,
        parent_id: Optional[str] = None,
        emoji: Optional[str] = None,
    ) -> str:
        comment_id = uuid.uuid4().hex
        now = datetime.utcnow().isoformat()
        self.database.execute(
            """
            INSERT INTO comments (
                id,
                post_id,
                author_id,
                parent_id,
                content,
                emoji,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                comment_id,
                post_id,
                author_id,
                parent_id,
                content,
                emoji,
                now,
                now,
            ),
        )
        return comment_id

    def list_comments(self, post_id: str) -> List[Dict[str, Any]]:
        rows = self.database.fetch_all(
            """
            SELECT
                comments.id,
                comments.post_id,
                comments.author_id,
                comments.parent_id,
                comments.content,
                comments.emoji,
                comments.created_at,
                comments.updated_at,
                users.username AS author_username,
                users.display_name AS author_display_name
            FROM comments
            INNER JOIN users ON users.id = comments.author_id
            WHERE comments.post_id = ?
            ORDER BY comments.created_at ASC
            """,
            (post_id,),
        )
        result: List[Dict[str, Any]] = []
        for row in rows:
            result.append(
                {
                    "id": row["id"],
                    "post_id": row["post_id"],
                    "author_id": row["author_id"],
                    "parent_id": row["parent_id"],
                    "content": row["content"],
                    "emoji": row["emoji"],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                    "author": {
                        "username": row["author_username"],
                        "display_name": row["author_display_name"],
                    },
                    "children": [],
                }
            )
        return result

    def list_nested_comments(self, post_id: str) -> List[Dict[str, Any]]:
        comments = self.list_comments(post_id)
        comment_map: Dict[str, Dict[str, Any]] = {}
        roots: List[Dict[str, Any]] = []
        for comment in comments:
            comment["children"] = []
            comment_map[comment["id"]] = comment
        for comment in comments:
            parent_id = comment.get("parent_id")
            if parent_id and parent_id in comment_map:
                comment_map[parent_id]["children"].append(comment)
            else:
                roots.append(comment)
        return roots

    def delete_comment(self, comment_id: str) -> None:
        self.database.execute(
            """
            DELETE FROM comments WHERE id = ?
            """,
            (comment_id,),
        )

    def delete_comments_by_post(self, post_id: str) -> None:
        self.database.execute(
            """
            DELETE FROM comments WHERE post_id = ?
            """,
            (post_id,),
        )

