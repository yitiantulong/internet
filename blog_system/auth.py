from typing import Optional, Dict, Any

from database import Database
from models.user import UserModel
from session import SessionManager


class AuthService:
    def __init__(self, database: Database, session_manager: SessionManager) -> None:
        self.database = database
        self.users = UserModel(database)
        self.sessions = session_manager

    def register(self, username: str, password: str, display_name: Optional[str], email: Optional[str]) -> Dict[str, Any]:
        created = self.users.create_user(username, password, display_name, email)
        if not created:
            return {"success": False, "message": "用户名已存在"}
        return {"success": True, "message": "注册成功，请登录"}

    def login(self, username: str, password: str) -> Dict[str, Any]:
        user = self.users.verify_password(username, password)
        if user is None:
            return {"success": False, "message": "用户名或密码错误"}
        session_id = self.sessions.create_session(username)
        return {"success": True, "session_id": session_id, "user": user}

    def logout(self, session_id: str) -> None:
        self.sessions.destroy_session(session_id)

    def get_current_user(self, request) -> Optional[Dict[str, Any]]:
        username = self.sessions.get_current_user(request)
        if username is None:
            return None
        user = self.users.get_user_by_username(username)
        return user

