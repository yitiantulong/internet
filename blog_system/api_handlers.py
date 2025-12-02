import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from http_types import HTTPRequest, HTTPResponse
from auth import AuthService
from models.post import PostModel
from models.comment import CommentModel
from models.interaction import InteractionModel
from models.subscription import SubscriptionModel
from models.message import MessageModel
from models.user import UserModel
from models.metric import PerformanceMetricModel


HTTP_STATUS_MESSAGES = {
    200: "OK",
    201: "Created",
    204: "No Content",
    400: "Bad Request",
    401: "Unauthorized",
    403: "Forbidden",
    404: "Not Found",
    422: "Unprocessable Entity",
    500: "Internal Server Error",
}


def json_response(data: Any, status: int = 200) -> HTTPResponse:
    body = json.dumps(data, ensure_ascii=False).encode("utf-8")
    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "Content-Length": str(len(body)),
        "Connection": "close",
    }
    reason = HTTP_STATUS_MESSAGES.get(status, "OK")
    return HTTPResponse(status, reason, body, headers)


def error_response(message: str, status: int = 400) -> HTTPResponse:
    return json_response({"success": False, "message": message}, status=status)


class BaseAPI:
    def __init__(self, auth_service: AuthService) -> None:
        self.auth_service = auth_service

    def _get_user(self, request: HTTPRequest) -> Optional[Dict[str, Any]]:
        return self.auth_service.get_current_user(request)


class PostAPI(BaseAPI):
    def __init__(
        self,
        auth_service: AuthService,
        post_model: PostModel,
        interaction_model: InteractionModel,
        subscription_model: SubscriptionModel,
    ) -> None:
        super().__init__(auth_service)
        self.posts = post_model
        self.interactions = interaction_model
        self.subscriptions = subscription_model

    def list_posts(self, request: HTTPRequest) -> HTTPResponse:
        user = self._get_user(request)
        query = request.get_query_params()
        filters: Dict[str, Any] = {}
        for key in ("keyword", "category", "author", "permission_type"):
            value = query.get(key)
            if value:
                filters[key] = value
        limit = self._safe_int(query.get("limit"), default=50, minimum=1, maximum=200)
        offset = self._safe_int(query.get("offset"), default=0, minimum=0)
        posts = self.posts.list_posts(limit=limit, offset=offset, filters=filters)
        cookies = request.get_cookies()
        payload: List[Dict[str, Any]] = []
        for post in posts:
            if self._post_accessible(post, user, cookies):
                payload.append(self._serialize_post_summary(post))
        return json_response({"success": True, "posts": payload})

    def get_post(self, request: HTTPRequest, post_id: str) -> HTTPResponse:
        user = self._get_user(request)
        post = self.posts.get_post_by_id(post_id)
        if post is None:
            return error_response("文章不存在", status=404)
        cookies = request.get_cookies()
        if not self._post_accessible(post, user, cookies):
            return error_response("没有权限查看该文章", status=403)
        return json_response({"success": True, "post": self._serialize_post_detail(post)})

    def create_post(self, request: HTTPRequest) -> HTTPResponse:
        user = self._get_user(request)
        if not user:
            return error_response("请先登录", status=401)
        data = request.get_json()
        if not isinstance(data, dict):
            return error_response("请求体必须为 JSON", status=400)
        title = (data.get("title") or "").strip()
        content = (data.get("content") or "").strip()
        if not title or not content:
            return error_response("标题和内容不能为空", status=422)
        summary = (data.get("summary") or content[:160]).strip()
        category = (data.get("category") or "").strip() or None
        tags = data.get("tags") or []
        cover_image = (data.get("cover_image") or "").strip() or None
        permission_type = (data.get("permission_type") or "public").strip() or "public"
        password_hint = (data.get("password_hint") or "").strip() or None
        password = (data.get("password") or "").strip()
        if permission_type == "password" and not password:
            return error_response("密码保护文章必须提供密码", status=422)
        if permission_type != "password":
            password = None
            password_hint = None
        allow_comments = bool(data.get("allow_comments", True))
        is_encrypted = bool(data.get("is_encrypted", False))
        post_id = self.posts.create_post(
            author_id=user["id"],
            title=title,
            content=content,
            summary=summary,
            category=category,
            tags=tags if isinstance(tags, list) else [],
            cover_image=cover_image,
            permission_type=permission_type,
            password_hint=password_hint,
            password=password,
            allow_comments=allow_comments,
            is_encrypted=is_encrypted,
        )
        author_username = user.get("username", "")
        if author_username:
            author_display = user.get("display_name", "") or author_username
            self.subscriptions.notify_author_subscribers(
                author_username,
                author_display,
                title,
                post_id,
                exclude_user_id=user["id"],
            )
        return json_response({"success": True, "post_id": post_id}, status=201)

    def update_permissions(self, request: HTTPRequest, post_id: str) -> HTTPResponse:
        user = self._get_user(request)
        if not user:
            return error_response("请先登录", status=401)
        post = self.posts.get_post_by_id(post_id)
        if post is None:
            return error_response("文章不存在", status=404)
        if not self.posts.is_author(post, user):
            return error_response("无权修改该文章权限", status=403)
        data = request.get_json()
        if not isinstance(data, dict):
            return error_response("请求体必须为 JSON", status=400)
        permission_type = (data.get("permission_type") or post["security"]["permission_type"]).strip()
        password_hint = (data.get("password_hint") or "").strip() or None
        password = (data.get("password") or "").strip()
        if permission_type == "password" and not password and not post["security"]["password_protected"]:
            return error_response("密码保护文章必须提供密码", status=422)
        if permission_type != "password":
            password = None
            password_hint = None
        allow_comments = bool(data.get("allow_comments", post["security"]["allow_comments"]))
        is_encrypted = bool(data.get("is_encrypted", post["security"]["is_encrypted"]))
        self.posts.set_permissions(
            post_id=post_id,
            permission_type=permission_type,
            password_hint=password_hint,
            password=password,
            allow_comments=allow_comments,
            is_encrypted=is_encrypted,
        )
        return json_response({"success": True})

    def toggle_like(self, request: HTTPRequest, post_id: str) -> HTTPResponse:
        user = self._get_user(request)
        if not user:
            return error_response("请先登录", status=401)
        post = self.posts.get_post_by_id(post_id)
        if post is None:
            return error_response("文章不存在", status=404)
        toggled = self.interactions.toggle_like(user["id"], post_id)
        like_count = self.interactions.count_likes(post_id)
        return json_response({"success": True, "liked": toggled, "like_count": like_count})

    def toggle_favorite(self, request: HTTPRequest, post_id: str) -> HTTPResponse:
        user = self._get_user(request)
        if not user:
            return error_response("请先登录", status=401)
        post = self.posts.get_post_by_id(post_id)
        if post is None:
            return error_response("文章不存在", status=404)
        toggled = self.interactions.toggle_favorite(user["id"], post_id)
        favorite_count = self.interactions.count_favorites(post_id)
        return json_response({"success": True, "favorited": toggled, "favorite_count": favorite_count})

    def _serialize_post_summary(self, post: Dict[str, Any]) -> Dict[str, Any]:
        security = post.get("security", {})
        return {
            "id": post["id"],
            "title": post["title"],
            "summary": post.get("summary"),
            "category": post.get("category"),
            "tags": post.get("tags", []),
            "cover_image": post.get("cover_image"),
            "created_at": post.get("created_at"),
            "updated_at": post.get("updated_at"),
            "author": {
                "username": post["author"]["username"],
                "display_name": post["author"]["display_name"],
                "is_vip": post["author"].get("is_vip", False),
            },
            "security": {
                "permission_type": security.get("permission_type", "public"),
                "allow_comments": security.get("allow_comments", True),
                "is_encrypted": security.get("is_encrypted", False),
                "password_protected": security.get("password_protected", False),
                "password_hint": security.get("password_hint"),
            },
        }

    def _serialize_post_detail(self, post: Dict[str, Any]) -> Dict[str, Any]:
        data = self._serialize_post_summary(post)
        data["content"] = post.get("content", "")
        return data

    def _post_accessible(self, post: Dict[str, Any], user: Optional[Dict[str, Any]], cookies: Dict[str, str]) -> bool:
        security = post.get("security", {})
        permission_type = security.get("permission_type", "public")
        has_password_access = False
        if permission_type == "password":
            cookie_key = f"post_access_{post['id']}"
            has_password_access = cookies.get(cookie_key) == "granted"
        return self.posts.can_view_post(post, user, has_password_access)

    def _safe_int(self, value: Optional[str], default: int, minimum: int = 0, maximum: Optional[int] = None) -> int:
        try:
            parsed = int(value) if value is not None else default
        except ValueError:
            parsed = default
        if parsed < minimum:
            parsed = minimum
        if maximum is not None and parsed > maximum:
            parsed = maximum
        return parsed


class CommentAPI(BaseAPI):
    def __init__(self, auth_service: AuthService, post_model: PostModel, comment_model: CommentModel) -> None:
        super().__init__(auth_service)
        self.posts = post_model
        self.comments = comment_model

    def list_comments(self, request: HTTPRequest, post_id: str) -> HTTPResponse:
        user = self._get_user(request)
        post = self.posts.get_post_by_id(post_id)
        if post is None:
            return error_response("文章不存在", status=404)
        cookies = request.get_cookies()
        if not self.posts.can_view_post(post, user, cookies.get(f"post_access_{post_id}") == "granted"):
            return error_response("没有权限查看该文章评论", status=403)
        comment_tree = self.comments.list_nested_comments(post_id)
        return json_response({"success": True, "comments": comment_tree})

    def create_comment(self, request: HTTPRequest, post_id: str) -> HTTPResponse:
        user = self._get_user(request)
        if not user:
            return error_response("请先登录", status=401)
        post = self.posts.get_post_by_id(post_id)
        if post is None:
            return error_response("文章不存在", status=404)
        cookies = request.get_cookies()
        if not self.posts.can_view_post(post, user, cookies.get(f"post_access_{post_id}") == "granted"):
            return error_response("没有权限在该文章下评论", status=403)
        payload = request.get_json()
        if not isinstance(payload, dict):
            return error_response("请求体必须为 JSON", status=400)
        content = (payload.get("content") or "").strip()
        if not content:
            return error_response("评论内容不能为空", status=422)
        parent_id = payload.get("parent_id") or None
        emoji = (payload.get("emoji") or "").strip() or None
        comment_id = self.comments.add_comment(
            post_id=post_id,
            author_id=user["id"],
            content=content,
            parent_id=parent_id,
            emoji=emoji,
        )
        return json_response({"success": True, "comment_id": comment_id}, status=201)


class SubscriptionAPI(BaseAPI):
    def __init__(
        self,
        auth_service: AuthService,
        subscription_model: SubscriptionModel,
        post_model: PostModel,
    ) -> None:
        super().__init__(auth_service)
        self.subscriptions = subscription_model
        self.posts = post_model

    def list_subscriptions(self, request: HTTPRequest) -> HTTPResponse:
        user = self._get_user(request)
        if not user:
            return error_response("请先登录", status=401)
        data = self.subscriptions.list_subscriptions(user["id"])
        return json_response({"success": True, "subscriptions": data})

    def create_subscription(self, request: HTTPRequest) -> HTTPResponse:
        user = self._get_user(request)
        if not user:
            return error_response("请先登录", status=401)
        payload = request.get_json()
        if not isinstance(payload, dict):
            return error_response("请求体必须为 JSON", status=400)
        sub_type = (payload.get("type") or "").strip()
        value = (payload.get("value") or "").strip()
        if sub_type not in ("category", "author") or not value:
            return error_response("订阅类型或值无效", status=422)
        self.subscriptions.add_subscription(user["id"], sub_type, value)
        return json_response({"success": True}, status=201)

    def remove_subscription(self, request: HTTPRequest, subscription_id: str) -> HTTPResponse:
        user = self._get_user(request)
        if not user:
            return error_response("请先登录", status=401)
        self.subscriptions.remove_subscription(subscription_id)
        return json_response({"success": True}, status=200)


class MessageAPI(BaseAPI):
    def __init__(self, auth_service: AuthService, message_model: MessageModel, user_model: UserModel) -> None:
        super().__init__(auth_service)
        self.messages = message_model
        self.users = user_model

    @staticmethod
    def _format_timestamp(value: Optional[str]) -> str:
        if not value:
            return ""
        normalized = str(value).strip()
        if not normalized:
            return ""
        candidate = normalized.rstrip("Zz")
        if "T" not in candidate and " " in candidate:
            candidate = candidate.replace(" ", "T")
        try:
            parsed = datetime.fromisoformat(candidate)
        except ValueError:
            try:
                parsed = datetime.strptime(normalized, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                return normalized.replace("T", " ")
        return parsed.strftime("%Y-%m-%d %H:%M:%S")

    def list_messages(self, request: HTTPRequest) -> HTTPResponse:
        user = self._get_user(request)
        if not user:
            return error_response("请先登录", status=401)
        conversations = self.messages.list_conversations(user["id"])
        for item in conversations:
            item["created_at"] = self._format_timestamp(item.get("created_at"))
        return json_response({"success": True, "messages": conversations})

    def get_conversation(self, request: HTTPRequest, target_username: str) -> HTTPResponse:
        user = self._get_user(request)
        if not user:
            return error_response("请先登录", status=401)
        target = self.users.get_user_by_username(target_username)
        if target is None:
            return error_response("用户不存在", status=404)
        conversation = self.messages.list_messages_between(user["id"], target["id"])
        for item in conversation:
            item["created_at"] = self._format_timestamp(item.get("created_at"))
        return json_response({"success": True, "conversation": conversation, "current_user_id": user["id"]})

    def send_message(self, request: HTTPRequest) -> HTTPResponse:
        user = self._get_user(request)
        if not user:
            return error_response("请先登录", status=401)
        payload = request.get_json()
        if not isinstance(payload, dict):
            return error_response("请求体必须为 JSON", status=400)
        target_username = (payload.get("target") or "").strip()
        content = (payload.get("content") or "").strip()
        if not target_username or not content:
            return error_response("收件人和内容不能为空", status=422)
        target = self.users.get_user_by_username(target_username)
        if target is None:
            return error_response("收件人不存在", status=404)
        message_id = self.messages.send_message(user["id"], target["id"], content)
        return json_response({"success": True, "message_id": message_id}, status=201)

    def get_inbox(self, request: HTTPRequest) -> HTTPResponse:
        user = self._get_user(request)
        if not user:
            return error_response("请先登录", status=401)
        messages = self.messages.get_inbox_messages(user["id"])
        for item in messages:
            item["created_at"] = self._format_timestamp(item.get("created_at"))
        return json_response({"success": True, "messages": messages})

    def get_sent(self, request: HTTPRequest) -> HTTPResponse:
        user = self._get_user(request)
        if not user:
            return error_response("请先登录", status=401)
        messages = self.messages.get_sent_messages(user["id"])
        for item in messages:
            item["created_at"] = self._format_timestamp(item.get("created_at"))
        return json_response({"success": True, "messages": messages})

    def get_trash(self, request: HTTPRequest) -> HTTPResponse:
        user = self._get_user(request)
        if not user:
            return error_response("请先登录", status=401)
        messages = self.messages.get_trash_messages(user["id"])
        for item in messages:
            item["created_at"] = self._format_timestamp(item.get("created_at"))
        return json_response({"success": True, "messages": messages})

    def get_message(self, request: HTTPRequest, message_id: str) -> HTTPResponse:
        user = self._get_user(request)
        if not user:
            return error_response("请先登录", status=401)
        message = self.messages.get_message_by_id(message_id, user["id"])
        if not message:
            return error_response("消息不存在", status=404)
        message["created_at"] = self._format_timestamp(message.get("created_at"))
        if message["receiver_id"] == user["id"]:
            self.messages.mark_as_read(message_id)
        return json_response({"success": True, "message": message})

    def delete_message(self, request: HTTPRequest, message_id: str) -> HTTPResponse:
        user = self._get_user(request)
        if not user:
            return error_response("请先登录", status=401)
        success = self.messages.delete_message(message_id, user["id"])
        if not success:
            return error_response("消息不存在或无权操作", status=404)
        return json_response({"success": True})

    def restore_message(self, request: HTTPRequest, message_id: str) -> HTTPResponse:
        user = self._get_user(request)
        if not user:
            return error_response("请先登录", status=401)
        success = self.messages.restore_message(message_id, user["id"])
        if not success:
            return error_response("消息不存在或无法恢复", status=404)
        return json_response({"success": True})

    def permanently_delete_message(self, request: HTTPRequest, message_id: str) -> HTTPResponse:
        user = self._get_user(request)
        if not user:
            return error_response("请先登录", status=401)
        success = self.messages.permanently_delete_message(message_id, user["id"])
        if not success:
            return error_response("消息不存在或无权操作", status=404)
        return json_response({"success": True})


class PerformanceAPI(BaseAPI):
    def __init__(self, auth_service: AuthService, metric_model: PerformanceMetricModel) -> None:
        super().__init__(auth_service)
        self.metrics = metric_model

    def list_metrics(self, request: HTTPRequest) -> HTTPResponse:
        query = request.get_query_params()
        limit = self._safe_int(query.get("limit"), default=20, minimum=1, maximum=200)
        records = self.metrics.list_recent_metrics(limit=limit)
        return json_response({"success": True, "metrics": records})

    def record_metric(self, request: HTTPRequest) -> HTTPResponse:
        payload = request.get_json()
        if not isinstance(payload, dict):
            return error_response("请求体必须为 JSON", status=400)
        try:
            latency = float(payload.get("latency_ms"))
            throughput = float(payload.get("throughput"))
            rtt = float(payload.get("rtt"))
            request_count = int(payload.get("request_count"))
        except (TypeError, ValueError):
            return error_response("性能数据格式不正确", status=422)
        self.metrics.record_metric(latency, throughput, rtt, request_count)
        return json_response({"success": True}, status=201)

    def _safe_int(self, value: Optional[str], default: int, minimum: int = 0, maximum: Optional[int] = None) -> int:
        try:
            parsed = int(value) if value is not None else default
        except ValueError:
            parsed = default
        if parsed < minimum:
            parsed = minimum
        if maximum is not None and parsed > maximum:
            parsed = maximum
        return parsed

