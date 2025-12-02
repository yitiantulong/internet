import hashlib
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from database import Database


class PostModel:
    def __init__(self, database: Database) -> None:
        self.database = database

    def create_post(
        self,
        author_id: int,
        title: str,
        content: str,
        summary: Optional[str],
        category: Optional[str],
        tags: Optional[List[str]],
        cover_image: Optional[str],
        permission_type: str,
        password_hint: Optional[str],
        password: Optional[str],
        allow_comments: bool,
        is_encrypted: bool,
    ) -> str:
        post_id = uuid.uuid4().hex
        now = datetime.utcnow().isoformat()
        tags_serialized = ",".join(tags) if tags else ""
        password_hash = self._hash_password(password) if password else None
        self.database.execute(
            """
            INSERT INTO posts (
                id,
                author_id,
                title,
                content,
                summary,
                category,
                tags,
                cover_image,
                permission_type,
                password_hint,
                password_hash,
                allow_comments,
                is_encrypted,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                post_id,
                author_id,
                title,
                content,
                summary,
                category,
                tags_serialized,
                cover_image,
                permission_type,
                password_hint,
                password_hash,
                1 if allow_comments else 0,
                1 if is_encrypted else 0,
                now,
                now,
            ),
        )
        return post_id

    def update_post(
        self,
        post_id: str,
        title: str,
        content: str,
        summary: Optional[str],
        category: Optional[str],
        tags: Optional[List[str]],
        cover_image: Optional[str],
        permission_type: str,
        password_hint: Optional[str],
        password: Optional[str],
        allow_comments: bool,
        is_encrypted: bool,
    ) -> None:
        now = datetime.utcnow().isoformat()
        tags_serialized = ",".join(tags) if tags else ""
        password_hash = self._hash_password(password) if password else None
        self.database.execute(
            """
            UPDATE posts
            SET title = ?,
                content = ?,
                summary = ?,
                category = ?,
                tags = ?,
                cover_image = ?,
                permission_type = ?,
                password_hint = ?,
                password_hash = ?,
                allow_comments = ?,
                is_encrypted = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                title,
                content,
                summary,
                category,
                tags_serialized,
                cover_image,
                permission_type,
                password_hint,
                password_hash,
                1 if allow_comments else 0,
                1 if is_encrypted else 0,
                now,
                post_id,
            ),
        )

    def set_permissions(
        self,
        post_id: str,
        permission_type: str,
        password_hint: Optional[str],
        password: Optional[str],
        allow_comments: bool,
        is_encrypted: bool,
    ) -> None:
        now = datetime.utcnow().isoformat()
        password_hash = self._hash_password(password) if password else None
        self.database.execute(
            """
            UPDATE posts
            SET permission_type = ?,
                password_hint = ?,
                password_hash = ?,
                allow_comments = ?,
                is_encrypted = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                permission_type,
                password_hint,
                password_hash,
                1 if allow_comments else 0,
                1 if is_encrypted else 0,
                now,
                post_id,
            ),
        )

    def list_posts(self, limit: int = 50, offset: int = 0, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        base_query = """
            SELECT
                posts.id,
                posts.author_id,
                posts.title,
                posts.summary,
                posts.category,
                posts.tags,
                posts.cover_image,
                posts.permission_type,
                posts.password_hint,
                posts.password_hash,
                posts.allow_comments,
                posts.is_encrypted,
                posts.created_at,
                posts.updated_at,
                users.display_name AS author_name,
                users.username AS author_username,
                users.is_vip AS author_is_vip
            FROM posts
            INNER JOIN users ON users.id = posts.author_id
            """
        clauses: List[str] = []
        parameters: List[Any] = []
        if filters:
            keyword = filters.get("keyword")
            category = filters.get("category")
            author = filters.get("author")
            permission = filters.get("permission_type")
            if keyword:
                clauses.append("(posts.title LIKE ? OR posts.content LIKE ?)")
                parameters.append(f"%{keyword}%")
                parameters.append(f"%{keyword}%")
            if category:
                clauses.append("posts.category = ?")
                parameters.append(category)
            if author:
                clauses.append("users.username = ?")
                parameters.append(author)
            if permission:
                clauses.append("posts.permission_type = ?")
                parameters.append(permission)
        if clauses:
            base_query += " WHERE " + " AND ".join(clauses)
        base_query += " ORDER BY posts.created_at DESC LIMIT ? OFFSET ?"
        parameters.extend([limit, offset])
        rows = self.database.fetch_all(base_query, parameters)
        result: List[Dict[str, Any]] = []
        for row in rows:
            result.append(self._map_post_summary(row))
        return result

    def get_post_by_id(self, post_id: str) -> Optional[Dict[str, Any]]:
        row = self.database.fetch_one(
            """
            SELECT
                posts.id,
                posts.author_id,
                posts.title,
                posts.content,
                posts.summary,
                posts.category,
                posts.tags,
                posts.cover_image,
                posts.permission_type,
                posts.password_hint,
                posts.password_hash,
                posts.allow_comments,
                posts.is_encrypted,
                posts.created_at,
                posts.updated_at,
                users.display_name AS author_name,
                users.username AS author_username,
                users.is_vip AS author_is_vip
            FROM posts
            INNER JOIN users ON users.id = posts.author_id
            WHERE posts.id = ?
            """,
            (post_id,),
        )
        if row is None:
            return None
        return self._map_post_detail(row)

    def list_categories(self) -> List[str]:
        rows = self.database.fetch_all(
            """
            SELECT DISTINCT category
            FROM posts
            WHERE category IS NOT NULL AND category <> ''
            ORDER BY category
            """
        )
        categories: List[str] = []
        for row in rows:
            categories.append(row["category"])
        return categories

    def list_author_posts(self, author_id: int, limit: int = 50) -> List[Dict[str, Any]]:
        rows = self.database.fetch_all(
            """
            SELECT
                id,
                title,
                summary,
                category,
                tags,
                cover_image,
                permission_type,
                allow_comments,
                is_encrypted,
                created_at,
                updated_at
            FROM posts
            WHERE author_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (author_id, limit),
        )
        result: List[Dict[str, Any]] = []
        for row in rows:
            result.append(
                {
                    "id": row["id"],
                    "title": row["title"],
                    "summary": row["summary"],
                    "category": row["category"],
                    "tags": row["tags"].split(",") if row["tags"] else [],
                    "cover_image": row["cover_image"],
                    "permission_type": row["permission_type"],
                    "allow_comments": bool(row["allow_comments"]),
                    "is_encrypted": bool(row["is_encrypted"]),
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                }
            )
        return result

    def delete_post(self, post_id: str) -> None:
        self.database.execute(
            """
            DELETE FROM posts WHERE id = ?
            """,
            (post_id,),
        )

    def find_post_by_title(self, title: str) -> Optional[Dict[str, Any]]:
        row = self.database.fetch_one(
            """
            SELECT
                posts.id,
                posts.author_id,
                posts.title,
                posts.content,
                posts.summary,
                posts.category,
                posts.tags,
                posts.cover_image,
                posts.permission_type,
                posts.password_hint,
                posts.password_hash,
                posts.allow_comments,
                posts.is_encrypted,
                posts.created_at,
                posts.updated_at,
                users.display_name AS author_name,
                users.username AS author_username,
                users.is_vip AS author_is_vip
            FROM posts
            INNER JOIN users ON users.id = posts.author_id
            WHERE posts.title = ?
            """,
            (title,),
        )
        if row is None:
            return None
        return self._map_post_detail(row)

    def verify_post_password(self, post_id: str, password: str) -> bool:
        row = self.database.fetch_one(
            """
            SELECT password_hash FROM posts WHERE id = ?
            """,
            (post_id,),
        )
        if row is None or row["password_hash"] is None:
            return False
        return self._hash_password(password) == row["password_hash"]

    def can_view_post(self, post: Dict[str, Any], user: Optional[Dict[str, Any]], has_password_access: bool) -> bool:
        permission = post.get("security", {}).get("permission_type", "public")
        if permission == "public":
            return True
        if self.is_author(post, user):
            return True
        if permission == "vip":
            return bool(user and user.get("is_vip"))
        if permission == "password":
            return has_password_access
        if permission == "private":
            return False
        return False

    def is_author(self, post: Dict[str, Any], user: Optional[Dict[str, Any]]) -> bool:
        if not user:
            return False
        return post.get("author", {}).get("username") == user.get("username")

    def _map_post_summary(self, row: Any) -> Dict[str, Any]:
        return {
            "id": row["id"],
            "title": row["title"],
            "summary": row["summary"],
            "category": row["category"],
            "tags": row["tags"].split(",") if row["tags"] else [],
            "cover_image": row["cover_image"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "author": {
                "id": row["author_id"],
                "display_name": row["author_name"],
                "username": row["author_username"],
                "is_vip": bool(row["author_is_vip"]),
            },
            "security": {
                "permission_type": row["permission_type"],
                "password_hint": row["password_hint"],
                "allow_comments": bool(row["allow_comments"]),
                "is_encrypted": bool(row["is_encrypted"]),
                "password_protected": row["permission_type"] == "password" and row["password_hash"] is not None,
            },
        }

    def _map_post_detail(self, row: Any) -> Dict[str, Any]:
        mapped = self._map_post_summary(row)
        mapped["content"] = row["content"]
        mapped["security"] = {
            "permission_type": row["permission_type"],
            "password_hint": row["password_hint"],
            "allow_comments": bool(row["allow_comments"]),
            "is_encrypted": bool(row["is_encrypted"]),
            "password_protected": row["permission_type"] == "password" and row["password_hash"] is not None,
        }
        return mapped

    def _hash_password(self, raw_password: Optional[str]) -> Optional[str]:
        if raw_password is None:
            return None
        hasher = hashlib.sha256()
        hasher.update(raw_password.encode("utf-8"))
        return hasher.hexdigest()

