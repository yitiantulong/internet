import os
import sqlite3
import threading
from typing import Callable, Iterable, Optional, Any, Dict


class Database:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self.lock = threading.Lock()
        self._ensure_directory()
        self._initialize_schema()

    def _ensure_directory(self) -> None:
        directory = os.path.dirname(self.db_path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)

    def _initialize_schema(self) -> None:
        with self.get_connection() as connection:
            cursor = connection.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    display_name TEXT NOT NULL,
                    email TEXT,
                    bio TEXT,
                    avatar_url TEXT,
                    role TEXT NOT NULL DEFAULT 'user',
                    is_vip INTEGER NOT NULL DEFAULT 0,
                    is_subscription_public INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            try:
                cursor.execute("ALTER TABLE users ADD COLUMN is_subscription_public INTEGER NOT NULL DEFAULT 1")
            except sqlite3.OperationalError:
                pass
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS posts (
                    id TEXT PRIMARY KEY,
                    author_id INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    summary TEXT,
                    category TEXT,
                    tags TEXT,
                    cover_image TEXT,
                    permission_type TEXT NOT NULL DEFAULT 'public',
                    password_hint TEXT,
                    password_hash TEXT,
                    allow_comments INTEGER NOT NULL DEFAULT 1,
                    is_encrypted INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(author_id) REFERENCES users(id)
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS comments (
                    id TEXT PRIMARY KEY,
                    post_id TEXT NOT NULL,
                    author_id INTEGER NOT NULL,
                    parent_id TEXT,
                    content TEXT NOT NULL,
                    emoji TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(post_id) REFERENCES posts(id),
                    FOREIGN KEY(author_id) REFERENCES users(id)
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS likes (
                    id TEXT PRIMARY KEY,
                    post_id TEXT NOT NULL,
                    user_id INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(post_id) REFERENCES posts(id),
                    FOREIGN KEY(user_id) REFERENCES users(id)
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS favorites (
                    id TEXT PRIMARY KEY,
                    post_id TEXT NOT NULL,
                    user_id INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(post_id) REFERENCES posts(id),
                    FOREIGN KEY(user_id) REFERENCES users(id)
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS subscriptions (
                    id TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    subscription_type TEXT NOT NULL,
                    subscription_value TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(user_id) REFERENCES users(id)
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY,
                    sender_id INTEGER NOT NULL,
                    receiver_id INTEGER NOT NULL,
                    content TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'normal',
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(sender_id) REFERENCES users(id),
                    FOREIGN KEY(receiver_id) REFERENCES users(id)
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS user_privacy_settings (
                    user_id INTEGER PRIMARY KEY,
                    hide_posts INTEGER NOT NULL DEFAULT 0,
                    hide_favorites INTEGER NOT NULL DEFAULT 0,
                    access_password_hash TEXT,
                    FOREIGN KEY(user_id) REFERENCES users(id)
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS performance_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    latency_ms REAL NOT NULL,
                    throughput REAL NOT NULL,
                    rtt REAL NOT NULL,
                    request_count INTEGER NOT NULL
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS notifications (
                    id TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    message TEXT NOT NULL,
                    type TEXT NOT NULL,
                    is_read INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(user_id) REFERENCES users(id)
                )
                """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_posts_author ON posts(author_id)
                """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_comments_post ON comments(post_id)
                """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_likes_post_user ON likes(post_id, user_id)
                """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_favorites_post_user ON favorites(post_id, user_id)
                """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_messages_users ON messages(sender_id, receiver_id)
                """
            )
            # === 新增：宝可梦互动组件表 ===
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS pokemon_interactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    interaction_type TEXT NOT NULL,
                    count INTEGER DEFAULT 0,
                    last_interacted_at TEXT
                )
                """
            )
            # 初始化一个全局计数器（如果不存在）
            cursor.execute("INSERT OR IGNORE INTO pokemon_interactions (id, interaction_type, count) VALUES (1, 'global_pats', 0)")
            connection.commit()

    def get_connection(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path, check_same_thread=False)
        connection.row_factory = sqlite3.Row
        return connection

    def execute(self, query: str, parameters: Iterable[Any] = ()) -> None:
        with self.lock:
            with self.get_connection() as connection:
                cursor = connection.cursor()
                cursor.execute(query, tuple(parameters))
                connection.commit()

    def execute_many(self, query: str, parameter_list: Iterable[Iterable[Any]]) -> None:
        with self.lock:
            with self.get_connection() as connection:
                cursor = connection.cursor()
                cursor.executemany(query, list(parameter_list))
                connection.commit()

    def fetch_one(self, query: str, parameters: Iterable[Any] = ()) -> Optional[sqlite3.Row]:
        with self.lock:
            with self.get_connection() as connection:
                cursor = connection.cursor()
                cursor.execute(query, tuple(parameters))
                return cursor.fetchone()

    def fetch_all(self, query: str, parameters: Iterable[Any] = ()) -> Iterable[sqlite3.Row]:
        with self.lock:
            with self.get_connection() as connection:
                cursor = connection.cursor()
                cursor.execute(query, tuple(parameters))
                return cursor.fetchall()

    def transactional(self, operation: Callable[[sqlite3.Cursor], Any]) -> Any:
        with self.lock:
            with self.get_connection() as connection:
                cursor = connection.cursor()
                try:
                    result = operation(cursor)
                except Exception:
                    connection.rollback()
                    raise
                connection.commit()
                return result


database_instance: Optional[Database] = None


def get_database(db_path: str) -> Database:
    global database_instance
    if database_instance is None:
        database_instance = Database(db_path)
    return database_instance


def reset_database_instance() -> None:
    global database_instance
    database_instance = None

