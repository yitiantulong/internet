import os
import socket
import threading
import time
from datetime import datetime
from typing import Dict, List, Optional

from router import Router
from handlers import TemplateRenderer, BasicHandlers, UserHandlers, ArticleHandlers, SubscriptionHandlers, MessageHandlers
from api_handlers import (
    PostAPI,
    CommentAPI,
    SubscriptionAPI as SubscriptionAPIHandler,
    MessageAPI as MessageAPIHandler,
    PerformanceAPI,
    PokemonAPI
)
from database import get_database
from auth import AuthService
from models.user import UserModel
from models.post import PostModel
from models.comment import CommentModel
from models.subscription import SubscriptionModel
from models.interaction import InteractionModel
from models.message import MessageModel
from models.metric import PerformanceMetricModel
from models.privacy import PrivacyModel
from http_types import HTTPRequest, HTTPResponse
from session import SessionManager
from models.pokemon import PokemonModel



class HTTPServer:
    def __init__(self, host: str = "127.0.0.1", port: int = 8080) -> None:
        self.host = host
        self.port = port
        self.router = Router()
        self.static_root = os.path.join(os.path.dirname(__file__), "static")
        self.template_root = os.path.join(os.path.dirname(__file__), "templates")
        data_path = os.path.join(os.path.dirname(__file__), "data", "blog_system.sqlite3")
        self.database = get_database(data_path)
        self.session_manager = SessionManager()
        self.auth_service = AuthService(self.database, self.session_manager)
        self.user_model = UserModel(self.database)
        self.post_model = PostModel(self.database)
        self.comment_model = CommentModel(self.database)
        self.subscription_model = SubscriptionModel(self.database)
        self.interaction_model = InteractionModel(self.database)
        self.message_model = MessageModel(self.database)
        self.metrics_model = PerformanceMetricModel(self.database)
        self.privacy_model = PrivacyModel(self.database)
        self.renderer = TemplateRenderer(self.template_root)
        self.basic_handlers = BasicHandlers(
            self.renderer,
            self.auth_service,
            self.post_model,
            self.interaction_model,
            self.subscription_model,
            self.user_model,
            self.privacy_model,
        )
        self.user_handlers = UserHandlers(self.renderer, self.auth_service)
        self.article_handlers = ArticleHandlers(
            self.renderer,
            self.auth_service,
            self.post_model,
            self.comment_model,
            self.interaction_model,
            self.subscription_model,
        )
        self.subscription_handlers = SubscriptionHandlers(
            self.renderer,
            self.auth_service,
            self.subscription_model,
            self.post_model,
            self.user_model,
        )
        self.message_handlers = MessageHandlers(
            self.renderer,
            self.auth_service,
            self.message_model,
            self.user_model,
        )
        self.post_api = PostAPI(self.auth_service, self.post_model, self.interaction_model, self.subscription_model)
        self.comment_api = CommentAPI(self.auth_service, self.post_model, self.comment_model)
        self.subscription_api = SubscriptionAPIHandler(self.auth_service, self.subscription_model, self.post_model)
        self.message_api = MessageAPIHandler(self.auth_service, self.message_model, self.user_model)
        self.performance_api = PerformanceAPI(self.auth_service, self.metrics_model)
        self._request_counter = 0
        self.pokemon_model = PokemonModel(self.database)
        self.pokemon_api = PokemonAPI(self.auth_service, self.pokemon_model)
        self._seed_demo_content()
        self._configure_routes()

    def _configure_routes(self) -> None:
        self.router.add_route("/", "GET", self.basic_handlers.homepage)
        self.router.add_route("/profile", "GET", self.basic_handlers.profile)
        self.router.add_route("/profile", "POST", self.basic_handlers.update_profile)
        self.router.add_route("/profile/privacy", "POST", self.basic_handlers.update_privacy_settings)
        self.router.add_route("/register", "GET", self.user_handlers.show_register)
        self.router.add_route("/register", "POST", self.user_handlers.register)
        self.router.add_route("/login", "GET", self.user_handlers.show_login)
        self.router.add_route("/login", "POST", self.user_handlers.login)
        self.router.add_route("/logout", "GET", self.user_handlers.logout)
        self.router.add_route("/posts/new", "GET", self.article_handlers.show_create_post)
        self.router.add_route("/posts/new", "POST", self.article_handlers.create_post)
        self.router.add_route("/posts/<post_id>", "GET", self.article_handlers.view_post)
        self.router.add_route("/posts/<post_id>/comment", "POST", self.article_handlers.add_comment)
        self.router.add_route("/posts/<post_id>/favorite", "POST", self.article_handlers.handle_favorite)
        self.router.add_route("/posts/<post_id>/like", "POST", self.article_handlers.handle_like)
        self.router.add_route("/posts/<post_id>/unlock", "POST", self.article_handlers.unlock_post)
        self.router.add_route("/posts/<post_id>/delete", "POST", self.article_handlers.delete_post)
        self.router.add_route("/subscriptions", "GET", self.subscription_handlers.show_subscriptions)
        self.router.add_route("/subscriptions/category", "POST", self.subscription_handlers.subscribe_category)
        self.router.add_route("/subscriptions/author", "POST", self.subscription_handlers.subscribe_author)
        self.router.add_route("/subscriptions/cancel", "POST", self.subscription_handlers.cancel_subscription)
        self.router.add_route("/messages", "GET", self.message_handlers.mailbox)
        self.router.add_route("/api/posts", "GET", self.post_api.list_posts)
        self.router.add_route("/api/posts", "POST", self.post_api.create_post)
        self.router.add_route("/api/posts/<post_id>", "GET", self.post_api.get_post)
        self.router.add_route("/api/posts/<post_id>/permissions", "POST", self.post_api.update_permissions)
        self.router.add_route("/api/posts/<post_id>/like", "POST", self.post_api.toggle_like)
        self.router.add_route("/api/posts/<post_id>/favorite", "POST", self.post_api.toggle_favorite)
        self.router.add_route("/api/posts/<post_id>/comments", "GET", self.comment_api.list_comments)
        self.router.add_route("/api/posts/<post_id>/comments", "POST", self.comment_api.create_comment)
        self.router.add_route("/api/subscriptions", "GET", self.subscription_api.list_subscriptions)
        self.router.add_route("/api/subscriptions", "POST", self.subscription_api.create_subscription)
        self.router.add_route("/api/subscriptions/<subscription_id>", "DELETE", self.subscription_api.remove_subscription)
        self.router.add_route("/api/messages", "GET", self.message_api.list_messages)
        self.router.add_route("/api/messages", "POST", self.message_api.send_message)
        self.router.add_route("/api/messages/inbox", "GET", self.message_api.get_inbox)
        self.router.add_route("/api/messages/sent", "GET", self.message_api.get_sent)
        self.router.add_route("/api/messages/trash", "GET", self.message_api.get_trash)
        self.router.add_route("/api/messages/<message_id>", "GET", self.message_api.get_message)
        self.router.add_route("/api/messages/<message_id>/delete", "POST", self.message_api.delete_message)
        self.router.add_route("/api/messages/<message_id>/restore", "POST", self.message_api.restore_message)
        self.router.add_route("/api/messages/<message_id>/permanent-delete", "POST", self.message_api.permanently_delete_message)
        self.router.add_route("/api/messages/<target_username>", "GET", self.message_api.get_conversation)
        self.router.add_route("/api/performance/metrics", "GET", self.performance_api.list_metrics)
        self.router.add_route("/api/performance/metrics", "POST", self.performance_api.record_metric)
        # === 功能 1：文章密码解锁 ===
        # 配合前端 POST /api/posts/<id>/unlock
        self.router.add_route("/api/posts/<post_id>/unlock", "POST", self.post_api.unlock)

        # === 功能 3：宝可梦互动 ===
        self.router.add_route("/api/pokemon/status", "GET", self.pokemon_api.get_status)
        self.router.add_route("/api/pokemon/interact", "POST", self.pokemon_api.interact)

        # === 功能 2：网络性能 (已在原代码的 /api/performance/metrics 中，这里确保前端能调到) ===
        # 原代码已包含: self.router.add_route("/api/performance/metrics", "GET", self.performance_api.list_metrics)
    def serve_static(self, path: str) -> Optional[HTTPResponse]:
        normalized = os.path.normpath(path).lstrip("/")
        absolute_path = os.path.join(self.static_root, normalized)
        if not absolute_path.startswith(self.static_root):
            return self._forbidden()
        if not os.path.exists(absolute_path) or not os.path.isfile(absolute_path):
            return None
        with open(absolute_path, "rb") as file_handler:
            data = file_handler.read()
        content_type = self._guess_content_type(absolute_path)
        headers = {
            "Content-Type": content_type,
            "Content-Length": str(len(data)),
            "Connection": "close",
        }
        return HTTPResponse(200, "OK", data, headers)

    def _guess_content_type(self, path: str) -> str:
        if path.endswith(".css"):
            return "text/css; charset=utf-8"
        if path.endswith(".js"):
            return "application/javascript; charset=utf-8"
        if path.endswith(".png"):
            return "image/png"
        if path.endswith(".jpg") or path.endswith(".jpeg"):
            return "image/jpeg"
        if path.endswith(".ico"):
            return "image/x-icon"
        return "application/octet-stream"

    def _forbidden(self) -> HTTPResponse:
        body = b"403 Forbidden"
        headers = {
            "Content-Type": "text/plain; charset=utf-8",
            "Content-Length": str(len(body)),
            "Connection": "close",
        }
        return HTTPResponse(403, "Forbidden", body, headers)

    def start(self) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_socket.bind((self.host, self.port))
            server_socket.listen(5)
            print(f"Server running on http://{self.host}:{self.port}")
            while True:
                client_socket, _ = server_socket.accept()
                thread = threading.Thread(target=self._handle_client, args=(client_socket,))
                thread.daemon = True
                thread.start()

    def _handle_client(self, client_socket: socket.socket) -> None:
        with client_socket:
            request_data = b""
            while True:
                chunk = client_socket.recv(4096)
                if not chunk:
                    break
                request_data += chunk
                if b"\r\n\r\n" in request_data:
                    content_length = self._extract_content_length(request_data)
                    if content_length == 0:
                        break
                    if len(request_data.split(b"\r\n\r\n", 1)[1]) >= content_length:
                        break
            if not request_data:
                return
            request = HTTPRequest(request_data)

            response = self._dispatch(request)
            client_socket.sendall(response.to_bytes())

    def _extract_content_length(self, request_data: bytes) -> int:
        header_section = request_data.split(b"\r\n\r\n", 1)[0].decode("utf-8", errors="replace")
        for line in header_section.split("\r\n"):
            if line.lower().startswith("content-length:"):
                value = line.split(":", 1)[1].strip()
                try:
                    return int(value)
                except ValueError:
                    return 0
        return 0

    def _dispatch(self, request: HTTPRequest) -> HTTPResponse:
        if request.path.startswith("/static/"):
            static_response = self.serve_static(request.path[len("/static/"):])
            if static_response is not None:
                return static_response

        match = self.router.resolve(request.path, request.method)
        if match is None:
            return self._not_found()

        start_time = time.perf_counter()
        try:
            response = match.handler(request, **match.params)
        except Exception as exc:
            error_message = f"Internal Server Error: {exc}".encode("utf-8")
            headers = {
                "Content-Type": "text/plain; charset=utf-8",
                "Content-Length": str(len(error_message)),
                "Connection": "close",
            }
            response = HTTPResponse(500, "Internal Server Error", error_message, headers)
        finally:
            elapsed = time.perf_counter() - start_time
            self._record_metric(elapsed)
        return response

    def _not_found(self) -> HTTPResponse:
        body = b"404 Not Found"
        headers = {
            "Content-Type": "text/plain; charset=utf-8",
            "Content-Length": str(len(body)),
            "Connection": "close",
        }
        return HTTPResponse(404, "Not Found", body, headers)

    def _record_metric(self, elapsed_seconds: float) -> None:
        if elapsed_seconds < 0:
            return
        self._request_counter += 1
        latency_ms = elapsed_seconds * 1000.0
        throughput = 0.0 if elapsed_seconds <= 0 else 1.0 / elapsed_seconds
        rtt = latency_ms
        self.metrics_model.record_metric(latency_ms, throughput, rtt, self._request_counter)

    def _seed_demo_content(self) -> None:
        demo_username = "handsome_slash"
        demo_password = "demo123"
        demo_display = "帅的被人砍"
        demo_email = "handsome@example.com"
        user = self.user_model.get_user_by_username(demo_username)
        if user is None:
            self.user_model.create_user(demo_username, demo_password, demo_display, demo_email)
            user = self.user_model.get_user_by_username(demo_username)
        if user is None:
            return
        self._remove_posts_by_titles(
            [
                "把自己交给风景",
                "把自己交给风景：一场说走就走的逃离计划",
                "关于被生活轻轻敲醒的五次顿悟",
                "在雨夜里与灵感共舞的是个瞬间",
                "在雨夜里与灵感共舞的十个瞬间",
            ]
        )
        # === [修改] 植入特定的加密文章 ===
        # 检查是否已存在，不存在则创建
        encrypted_title = "【机密】只有有缘人能看"
        if self.post_model.find_post_by_title(encrypted_title) is None:
            # 获取用户ID (假设 demo_username 已创建)
            user = self.user_model.get_user_by_username("handsome_slash")
            if user:
                self.post_model.create_post(
                    author_id=user["id"],
                    title=encrypted_title,
                    content="<p>你解开了封印！<br/>唵嘛呢叭咪吽（OM MANI PADME HUM）<br/>这是实验要求的加密内容。</p>",
                    summary="这是一篇被古老咒语封印的文章...",
                    category="Secret",
                    tags=["Buddhism", "Code"],
                    cover_image=None,
                    permission_type="password", # 设置为密码保护
                    password_hint="佛教六字真言",
                    password="六字大明咒",      # 设置指定密码
                    allow_comments=True,
                    is_encrypted=True
                )
                print(f"[Demo] Created encrypted post: {encrypted_title}")
        sample_posts: List[Dict[str, str]] = []
        for post in sample_posts:
            if self.post_model.find_post_by_title(post["title"]) is not None:
                continue
            self.post_model.create_post(
                author_id=user["id"],
                title=post["title"],
                content=post["content"],
                summary=post["content"][:160],
                category=post["category"],
                tags=post.get("tags"),
                cover_image=None,
                permission_type="public",
                password_hint=None,
                password=None,
                allow_comments=True,
                is_encrypted=False,
            )

    def _remove_posts_by_titles(self, titles: List[str]) -> None:
        for title in titles:
            post = self.post_model.find_post_by_title(title)
            if post is None:
                continue
            post_id = post["id"]
            self.comment_model.delete_comments_by_post(post_id)
            self.interaction_model.delete_post_records(post_id)
            self.post_model.delete_post(post_id)


def create_server(host: str = "127.0.0.1", port: int = 8080) -> HTTPServer:
    server = HTTPServer(host, port)
    return server


if __name__ == "__main__":
    http_server = create_server()
    http_server.start()

