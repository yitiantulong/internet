import threading
import uuid
from typing import Dict, Optional

from http_types import HTTPRequest


class SessionManager:
    def __init__(self) -> None:
        self._sessions: Dict[str, str] = {}
        self._lock = threading.Lock()

    def create_session(self, username: str) -> str:
        token = uuid.uuid4().hex
        with self._lock:
            self._sessions[token] = username
        return token

    def get_username(self, session_id: str) -> Optional[str]:
        with self._lock:
            return self._sessions.get(session_id)

    def destroy_session(self, session_id: str) -> None:
        with self._lock:
            if session_id in self._sessions:
                del self._sessions[session_id]

    def get_current_user(self, request: HTTPRequest) -> Optional[str]:
        cookies = request.get_cookies()
        session_id = cookies.get("session_id")
        if session_id is None:
            return None
        return self.get_username(session_id)

