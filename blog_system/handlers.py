import os
import html
import re
import uuid
from datetime import datetime
from html.parser import HTMLParser
from typing import Dict, Any, List, Optional
from urllib.parse import quote_plus

from http_types import HTTPRequest, HTTPResponse
from auth import AuthService
from models.user import UserModel
from models.post import PostModel
from models.comment import CommentModel
from models.subscription import SubscriptionModel
from models.interaction import InteractionModel
from models.message import MessageModel


def create_redirect(location: str) -> HTTPResponse:
    headers = {
        "Location": location,
        "Content-Length": "0",
        "Connection": "close",
    }
    return HTTPResponse(302, "Found", b"", headers)


class TemplateRenderer:
    RAW_KEYS = {
        "main_content",
        "navbar_links",
        "header_actions",
        "extra_css_links",
        "extra_js_scripts",
        "message_block",
        "posts_html",
        "subscription_posts_html",
        "subscription_list_html",
        "comment_list_html",
        "comment_form_html",
        "auth_action",
        "authored_posts_html",
        "favorite_posts_html",
        "subscriptions_html",
        "contacts_html",
        "conversation_html",
        "permission_public_selected",
        "permission_vip_selected",
        "permission_password_selected",
        "permission_private_selected",
        "allow_comments_checked",
        "is_encrypted_checked",
        "profile_actions_html",
        "create_button_html",
        "delete_button_html",
        "post_content_html",
        "author_action_items_html",
        "post_feedback_html",
        "bio_html",
        "profile_feedback_html",
        "profile_edit_section_html",
    }

    def __init__(self, template_root: str) -> None:
        self.template_root = template_root

    def render(self, template_name: str, context: Dict[str, Any]) -> HTTPResponse:
        layout_name = context.get("_layout", "layout.html")
        try:
            main_template = self._load_template(template_name)
            layout_template = self._load_template(layout_name)
        except FileNotFoundError as exc:
            return self._template_not_found_response(str(exc))

        content_context = dict(context)
        for key in ("_layout", "navbar_links", "header_actions", "extra_css_links", "extra_js_scripts", "body_class", "page_description", "current_year"):
            content_context.pop(key, None)
        for raw_key in self.RAW_KEYS:
            content_context.setdefault(raw_key, "")

        try:
            main_content = self._format_template(main_template, content_context)
        except KeyError as exc:
            return self._missing_placeholder_response(template_name, exc)

        layout_context = {
            "page_title": context.get("page_title", "NeoBlog"),
            "page_description": context.get("page_description", ""),
            "navbar_links": context.get("navbar_links", ""),
            "header_actions": context.get("header_actions", ""),
            "main_content": main_content,
            "extra_css_links": context.get("extra_css_links", ""),
            "extra_js_scripts": context.get("extra_js_scripts", ""),
            "body_class": context.get("body_class", ""),
            "current_year": context.get("current_year", datetime.utcnow().year),
        }

        try:
            rendered = self._format_template(layout_template, layout_context)
        except KeyError as exc:
            return self._missing_placeholder_response(layout_name, exc)

        body = rendered.encode("utf-8")
        headers = {
            "Content-Type": "text/html; charset=utf-8",
            "Content-Length": str(len(body)),
            "Connection": "close",
        }
        return HTTPResponse(200, "OK", body, headers)

    def _load_template(self, template_name: str) -> str:
        path = os.path.join(self.template_root, template_name)
        if not os.path.exists(path):
            raise FileNotFoundError(template_name)
        with open(path, "r", encoding="utf-8") as file_handler:
            return file_handler.read()

    def _format_template(self, template: str, context: Dict[str, Any]) -> str:
        # 方案：不使用 template.format()，因为它会解析 CSS 中的 {}
        # 改为手动循环 replace，虽然效率低一点，但绝对安全，不会因为 CSS 报错
        
        result = template
        for key, value in context.items():
            # 构造占位符，例如 {page_title}
            placeholder = "{" + key + "}"
            
            # 如果值是 None，转为空字符串
            val_str = str(value) if value is not None else ""
            
            # 直接替换
            result = result.replace(placeholder, val_str)
            
        return result

    def _template_not_found_response(self, template_name: str) -> HTTPResponse:
        message = f"Template {template_name} not found".encode("utf-8")
        headers = {
            "Content-Type": "text/plain; charset=utf-8",
            "Content-Length": str(len(message)),
            "Connection": "close",
        }
        return HTTPResponse(500, "Internal Server Error", message, headers)

    def _missing_placeholder_response(self, template_name: str, exc: KeyError) -> HTTPResponse:
        missing = exc.args[0]
        message = f"模板 {template_name} 缺少占位符：{missing}".encode("utf-8")
        headers = {
            "Content-Type": "text/plain; charset=utf-8",
            "Content-Length": str(len(message)),
            "Connection": "close",
        }
        return HTTPResponse(500, "Internal Server Error", message, headers)


class _RichTextSanitizer(HTMLParser):
    VOID_TAGS = {"br", "img", "hr"}

    def __init__(self, allowed_tags: set, allowed_attrs: Dict[str, set], allowed_styles: set) -> None:
        super().__init__(convert_charrefs=True)
        self.allowed_tags = allowed_tags
        self.allowed_attrs = allowed_attrs
        self.allowed_styles = allowed_styles
        self.output: List[str] = []

    def handle_starttag(self, tag: str, attrs: List[tuple]) -> None:
        if tag not in self.allowed_tags:
            return
        attribute_text = self._sanitize_attributes(tag, attrs)
        self.output.append(f"<{tag}{attribute_text}>")

    def handle_startendtag(self, tag: str, attrs: List[tuple]) -> None:
        if tag not in self.allowed_tags:
            return
        attribute_text = self._sanitize_attributes(tag, attrs)
        self.output.append(f"<{tag}{attribute_text}>")

    def handle_endtag(self, tag: str) -> None:
        if tag not in self.allowed_tags:
            return
        if tag in self.VOID_TAGS:
            return
        self.output.append(f"</{tag}>")

    def handle_data(self, data: str) -> None:
        if not data:
            return
        self.output.append(html.escape(data))

    def handle_entityref(self, name: str) -> None:
        self.output.append(f"&{name};")

    def handle_charref(self, name: str) -> None:
        self.output.append(f"&#{name};")

    def handle_comment(self, data: str) -> None:
        return

    def get_html(self) -> str:
        return "".join(self.output)

    def _sanitize_attributes(self, tag: str, attrs: List[tuple]) -> str:
        allowed_for_tag = self.allowed_attrs.get(tag, set())
        allowed_global = self.allowed_attrs.get("*", set())
        allowed = allowed_for_tag.union(allowed_global)
        if not allowed:
            return ""
        sanitized: List[str] = []
        rel_present = False
        target_blank = False
        for name, value in attrs:
            if name not in allowed or value is None:
                continue
            if name == "class":
                sanitized_value = self._sanitize_classes(value)
                if not sanitized_value:
                    continue
            elif name == "style":
                sanitized_value = self._sanitize_style(value)
                if not sanitized_value:
                    continue
            elif name == "href":
                sanitized_value = self._sanitize_url(value)
                if not sanitized_value:
                    continue
            elif name == "src":
                sanitized_value = self._sanitize_src(value)
                if not sanitized_value:
                    continue
            elif name == "target":
                sanitized_value = value.strip().lower()
                if sanitized_value not in {"_blank", "_self", "_parent", "_top"}:
                    continue
                if sanitized_value == "_blank":
                    target_blank = True
            elif name == "rel":
                sanitized_value = self._sanitize_rel(value)
                if not sanitized_value:
                    continue
                rel_present = True
            else:
                sanitized_value = self._escape_attr(value)
            sanitized.append(f' {name}="{sanitized_value}"')
        if tag == "a" and target_blank and not rel_present:
            sanitized.append(' rel="noopener noreferrer"')
        return "".join(sanitized)

    def _sanitize_classes(self, value: str) -> str:
        tokens = value.split()
        valid_tokens: List[str] = []
        for token in tokens:
            if re.fullmatch(r"[A-Za-z0-9_-]+", token):
                valid_tokens.append(token)
        return " ".join(valid_tokens)

    def _sanitize_style(self, value: str) -> str:
        style_items = value.split(";")
        cleaned: List[str] = []
        for item in style_items:
            if ":" not in item:
                continue
            prop, raw_val = item.split(":", 1)
            prop_name = prop.strip().lower()
            if prop_name not in self.allowed_styles:
                continue
            sanitized_val = raw_val.strip()
            lowered = sanitized_val.lower()
            if "javascript:" in lowered or "expression" in lowered or "url(" in lowered:
                continue
            cleaned.append(f"{prop_name}: {sanitized_val}")
        return "; ".join(cleaned)

    def _sanitize_url(self, value: str) -> str:
        trimmed = value.strip()
        lowered = trimmed.lower()
        if lowered.startswith(("http://", "https://", "mailto:", "tel:", "/", "#")):
            return trimmed
        return ""

    def _sanitize_src(self, value: str) -> str:
        trimmed = value.strip()
        lowered = trimmed.lower()
        if lowered.startswith(("http://", "https://", "data:image/")):
            return trimmed
        return ""

    def _sanitize_rel(self, value: str) -> str:
        tokens = value.split()
        allowed_tokens = {"noopener", "noreferrer", "nofollow", "external"}
        result = [token for token in tokens if token in allowed_tokens]
        return " ".join(result)

    def _escape_attr(self, value: str) -> str:
        return html.escape(str(value), quote=True)


_ALLOWED_RICH_TEXT_TAGS = {
    "p",
    "br",
    "strong",
    "em",
    "u",
    "s",
    "blockquote",
    "code",
    "pre",
    "ul",
    "ol",
    "li",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "span",
    "a",
    "img",
    "table",
    "thead",
    "tbody",
    "tr",
    "th",
    "td",
    "hr",
    "figure",
    "figcaption",
    "sup",
    "sub",
    "div",
}

_ALLOWED_RICH_TEXT_ATTRS = {
    "*": {"class", "style"},
    "a": {"href", "target", "rel", "title"},
    "img": {"src", "alt", "title"},
    "table": {"class"},
    "thead": {"class"},
    "tbody": {"class"},
    "tr": {"class"},
    "th": {"colspan", "rowspan", "class", "style"},
    "td": {"colspan", "rowspan", "class", "style"},
    "code": {"class"},
    "pre": {"class"},
    "span": {"class", "style"},
    "div": {"class", "style"},
    "figure": {"class"},
    "figcaption": {"class", "style"},
}

_ALLOWED_RICH_TEXT_STYLES = {
    "color",
    "background-color",
    "font-size",
    "font-weight",
    "text-align",
    "text-decoration",
    "font-style",
    "font-family",
    "line-height",
    "letter-spacing",
    "margin",
    "margin-left",
    "margin-right",
    "margin-top",
    "margin-bottom",
}

_HTML_TAG_PATTERN = re.compile(r"<[^>]+>")
_WHITESPACE_PATTERN = re.compile(r"\s+")


class BaseHandler:
    NAV_ITEMS = [
        {"key": "home", "label": "首页", "href": "/", "icon": "fa-solid fa-house"},
        {"key": "profile", "label": "个人信息", "href": "/profile", "icon": "fa-regular fa-id-card"},
        {"key": "new_post", "label": "发布文章", "href": "/posts/new", "icon": "fa-solid fa-pen-nib"},
        {"key": "subscriptions", "label": "订阅管理", "href": "/subscriptions", "icon": "fa-solid fa-bell"},
        {"key": "messages", "label": "私信", "href": "/messages", "icon": "fa-regular fa-comments"},
    ]

    def __init__(self, renderer: TemplateRenderer, auth_service: AuthService) -> None:
        self.renderer = renderer
        self.auth_service = auth_service

    def get_current_user(self, request: HTTPRequest) -> Optional[Dict[str, Any]]:
        return self.auth_service.get_current_user(request)

    def _build_navbar_links(self, active_key: Optional[str]) -> str:
        items: List[str] = []
        for nav in self.NAV_ITEMS:
            classes = ["nav-link"]
            if active_key == nav["key"]:
                classes.append("nav-link-active")
            icon_html = f'<i class="{nav["icon"]} me-2"></i>'
            items.append(
                '<li class="nav-item">'
                f'<a class="{" ".join(classes)}" href="{nav["href"]}">'
                f'{icon_html}{html.escape(nav["label"])}'
                "</a>"
                "</li>"
            )
        return "".join(items)

    def _build_header_actions(self, user: Optional[Dict[str, Any]]) -> str:
        if user:
            display_name = html.escape(user.get("display_name") or user.get("username", "用户"))
            return (
                '<span class="navbar-text fw-semibold me-3">'
                f'<i class="fa-regular fa-circle-user me-2"></i>{display_name}'
                "</span>"
                '<a class="btn btn-outline-primary me-2" href="/posts/new">'
                '<i class="fa-solid fa-plus me-1"></i>创作'
                "</a>"
                '<a class="btn btn-primary" href="/logout">'
                '<i class="fa-solid fa-right-from-bracket me-1"></i>退出'
                "</a>"
            )
        return (
            '<a class="btn btn-outline-primary me-2" href="/login">'
            '<i class="fa-regular fa-user me-1"></i>登录'
            "</a>"
            '<a class="btn btn-primary" href="/register">'
            '<i class="fa-regular fa-pen-to-square me-1"></i>注册'
            "</a>"
        )

    def _layout_context(self, active_nav: Optional[str], user: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        return {
            "navbar_links": self._build_navbar_links(active_nav),
            "header_actions": self._build_header_actions(user),
            "current_year": datetime.utcnow().year,
            "body_class": "",
        }

    def _excerpt(self, content: str) -> str:
        if content is None:
            return ""
        plain = self._strip_html_tags(str(content))
        if not plain:
            return ""
        truncated = plain[:120]
        if len(plain) > 120:
            truncated += "..."
        return html.escape(truncated)

    def _strip_html_tags(self, value: str) -> str:
        if not value:
            return ""
        without_tags = _HTML_TAG_PATTERN.sub(" ", str(value))
        unescaped = html.unescape(without_tags)
        normalized = _WHITESPACE_PATTERN.sub(" ", unescaped)
        return normalized.strip()

    def _format_timestamp(self, raw_value: Optional[str]) -> str:
        if not raw_value:
            return ""
        normalized = str(raw_value).strip()
        if not normalized:
            return ""
        replacement = normalized.rstrip("Zz")
        # Preserve original separator if present, else fallback to space
        if "T" in replacement:
            candidate = replacement
        else:
            candidate = replacement.replace(" ", "T")
        try:
            parsed = datetime.fromisoformat(candidate)
        except ValueError:
            try:
                parsed = datetime.strptime(replacement, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                return replacement.replace("T", " ")
        return parsed.strftime("%Y-%m-%d %H:%M:%S")


class UserHandlers(BaseHandler):
    def __init__(self, renderer: TemplateRenderer, auth_service: AuthService) -> None:
        super().__init__(renderer, auth_service)

    def show_register(self, request: HTTPRequest) -> HTTPResponse:
        user = self.get_current_user(request)
        return self._render_register(user, "")

    def register(self, request: HTTPRequest) -> HTTPResponse:
        current_user = self.get_current_user(request)
        form = request.get_form_data()
        username = form.get("username", "").strip()
        password = form.get("password", "").strip()
        confirm_password = form.get("confirm_password", "").strip()
        display_name = form.get("display_name", "").strip() or None
        email = form.get("email", "").strip() or None
        if not username or not password:
            return self._render_register(current_user, "用户名和密码不能为空。")
        if len(username) < 3:
            return self._render_register(current_user, "用户名至少需要 3 个字符。")
        if password != confirm_password:
            return self._render_register(current_user, "两次输入的密码不一致。")
        result = self.auth_service.register(username, password, display_name, email)
        if not result.get("success"):
            return self._render_register(current_user, result.get("message", "注册失败。"))
        return create_redirect("/login")

    def show_login(self, request: HTTPRequest) -> HTTPResponse:
        user = self.get_current_user(request)
        return self._render_login(user, "")

    def login(self, request: HTTPRequest) -> HTTPResponse:
        current_user = self.get_current_user(request)
        form = request.get_form_data()
        username = form.get("username", "").strip()
        password = form.get("password", "").strip()
        if not username or not password:
            return self._render_login(current_user, "请输入用户名和密码。")
        result = self.auth_service.login(username, password)
        if not result.get("success"):
            return self._render_login(current_user, result.get("message", "登录失败，请重试。"))
        session_id = result.get("session_id", "")
        response = create_redirect("/")
        response.set_cookie("session_id", session_id, path="/")
        response.set_header("Content-Length", "0")
        response.body = b""
        return response

    def logout(self, request: HTTPRequest) -> HTTPResponse:
        cookies = request.get_cookies()
        session_id = cookies.get("session_id")
        if session_id:
            self.auth_service.logout(session_id)
        response = create_redirect("/")
        response.set_cookie("session_id", "", path="/", max_age=0)
        response.set_header("Content-Length", "0")
        response.body = b""
        return response

    def _render_register(self, user: Optional[Dict[str, Any]], message: str) -> HTTPResponse:
        alert_html = ""
        if message:
            alert_html = (
                '<div class="alert alert-warning" role="alert">'
                f"{html.escape(message)}"
                "</div>"
            )
        context = {
            "page_title": "用户注册",
            "page_description": "创建新账号，畅享订阅、创作与互动功能。",
            "message": message,
            "message_block": alert_html,
        }
        context.update(self._layout_context(None, user))
        return self.renderer.render("register.html", context)

    def _render_login(self, user: Optional[Dict[str, Any]], message: str) -> HTTPResponse:
        alert_html = ""
        if message:
            alert_html = (
                '<div class="alert alert-danger" role="alert">'
                f"{html.escape(message)}"
                "</div>"
            )
        context = {
            "page_title": "用户登录",
            "page_description": "输入账号与密码，继续你的创作与探索之旅。",
            "message": message,
            "message_block": alert_html,
        }
        context.update(self._layout_context(None, user))
        return self.renderer.render("login.html", context)


class BasicHandlers(BaseHandler):
    def __init__(
        self,
        renderer: TemplateRenderer,
        auth_service: AuthService,
        post_model: PostModel,
        interaction_model: InteractionModel,
        subscription_model: SubscriptionModel,
        user_model: UserModel,
        privacy_model: "PrivacyModel",
    ) -> None:
        super().__init__(renderer, auth_service)
        self.posts = post_model
        self.interactions = interaction_model
        self.subscriptions = subscription_model
        self.users = user_model
        self.privacy = privacy_model

    def homepage(self, request: HTTPRequest) -> HTTPResponse:
        user = self.get_current_user(request)
        if user:
            welcome_text = f"欢迎回来，{html.escape(user['display_name'])}！"
            auth_message = "探索个性化推送与订阅内容。"
            auth_action = (
                '<a class="btn btn-outline-primary" href="/profile">'
                '<i class="fa-regular fa-user me-1"></i>个人中心'
                "</a>"
                '<a class="btn btn-primary" href="/logout">'
                '<i class="fa-solid fa-right-from-bracket me-1"></i>退出登录'
                "</a>"
            )
        else:
            welcome_text = "欢迎体验 NeoBlog —— 现代化的博客空间。"
            auth_message = "当前为访客身份，请登录后获取更多功能。"
            auth_action = (
                '<a class="btn btn-outline-primary" href="/login">'
                '<i class="fa-regular fa-user me-1"></i>登录'
                "</a>"
                '<a class="btn btn-primary" href="/register">'
                '<i class="fa-regular fa-pen-to-square me-1"></i>立即加入'
                "</a>"
            )

        query_params = request.get_query_params()
        keyword = query_params.get("q", "").strip()
        category = query_params.get("category", "").strip()

        filters: Dict[str, Any] = {}
        if keyword:
            filters["keyword"] = keyword
        if category:
            filters["category"] = category

        posts = self.posts.list_posts(filters=filters)
        cookies = request.get_cookies()
        if user:
            posts = self._filter_accessible_posts(posts, user, cookies)
            subscription_posts = self._load_subscription_posts(user, cookies)
            subscription_html = self._build_post_cards(subscription_posts, compact=True, current_user=user)
        else:
            posts = [post for post in posts if self._is_public_post(post)]
            subscription_html = (
                '<div class="alert alert-info mb-0" role="alert">'
                '<i class="fa-regular fa-bell me-2"></i> 登录后即可接收专属订阅推送。'
                "</div>"
            )
        posts_html = self._build_post_cards(posts, current_user=user)

        categories = self.posts.list_categories()
        category_options_html = self._build_category_options(categories, category)

        context = {
            "page_title": "博客首页",
            "page_description": "现代化博客系统，探索精选内容、订阅喜爱作者并与好友互动。",
            "welcome_message": welcome_text,
            "auth_message": auth_message,
            "auth_action": auth_action,
            "posts_html": posts_html,
            "subscription_posts_html": subscription_html,
            "search_keyword": keyword,
            "search_category_options": category_options_html,
        }
        context.update(self._layout_context("home", user))
        return self.renderer.render("index.html", context)

    def profile(self, request: HTTPRequest) -> HTTPResponse:
        current_user = self.get_current_user(request)
        query_params = request.get_query_params()
        target_username = query_params.get("username") or query_params.get("user")

        target_user = None
        if target_username:
            target_user = self.users.get_user_by_username(target_username)
            if target_user is None:
                not_found_msg = (
                    '<div class="alert alert-warning" role="alert">'
                    f'未找到用户名为 {html.escape(target_username)} 的用户。'
                    "</div>"
                )
                context = {
                    "page_title": "个人信息",
                    "page_description": "该用户不存在或已被移除。",
                    "username": html.escape(target_username),
                    "email_display": "未知",
                    "bio_html": '<p class="text-muted mb-0">暂时无法显示该用户的详细信息。</p>',
                    "profile_feedback_html": "",
                    "profile_edit_section_html": "",
                    "edit_button_html": "",
                    "authored_posts_html": not_found_msg,
                    "favorite_posts_html": not_found_msg,
                    "subscriptions_html": not_found_msg,
                    "stats_html": "",
                    "profile_actions_html": (
                        '<a class="btn btn-outline-primary" href="/register">'
                        '<i class="fa-regular fa-pen-to-square me-1"></i>创建新账号</a>'
                    ),
                    "authored_heading": "作者文章",
                    "favorite_heading": "作者收藏",
                    "subscription_heading": "作者订阅",
                    "create_button_html": "",
                    "viewing_self": False,
                }
                context.update(self._layout_context("profile", current_user))
                return self.renderer.render("profile.html", context)
        if target_user is None:
            target_user = current_user

        if target_user is None:
            from http_types import create_redirect
            return create_redirect("/login")

        viewing_self = bool(current_user and current_user["id"] == target_user["id"])
        display_name = html.escape(target_user["display_name"])
        username_label = display_name
        if target_username and viewing_self is False:
            username_label = f"{display_name}（{html.escape(target_user['username'])}）"
        elif not target_username and not viewing_self:
            username_label = display_name

        privacy_settings = self.privacy.get_privacy_settings(target_user["id"])
        query_params = request.get_query_params()
        access_password = query_params.get("access_password", "").strip()
        has_access = True
        if not viewing_self:
            if privacy_settings["hide_posts"] or privacy_settings["hide_favorites"]:
                if privacy_settings["has_password"]:
                    if not access_password:
                        has_access = False
                    else:
                        has_access = self.privacy.verify_access_password(target_user["id"], access_password)
                else:
                    has_access = False

        authored_posts = []
        if has_access or viewing_self:
            authored_posts = self.posts.list_author_posts(target_user["id"])
        authored_html = self._build_post_cards(self._hydrate_posts(authored_posts), current_user=current_user) if authored_posts or not has_access else '<div class="alert alert-warning" role="alert">该用户已隐藏文章，需要访问密码才能查看。请通过URL参数?access_password=密码来访问。</div>'

        subscriber_count = self.subscriptions.get_subscriber_count(target_user["username"])
        subscription_count = self.subscriptions.get_subscription_count(target_user["id"], "author")
        is_subscribed = False
        if current_user and not viewing_self:
            is_subscribed = self.subscriptions.is_subscribed(current_user["id"], "author", target_user["username"])

        if viewing_self:
            favorite_ids = self.interactions.list_favorite_post_ids(target_user["id"])
            favorite_posts = self._hydrate_posts_by_ids(favorite_ids)
            favorites_html = self._build_post_cards(favorite_posts, current_user=current_user)
            privacy_settings_html = self._build_privacy_settings_section(target_user, privacy_settings)
            subs = self.subscriptions.list_subscriptions(target_user["id"])
            subscriptions_html = self._build_subscription_list(subs, self.users)
            profile_actions_html = "".join(
                [
                    '<a class="btn btn-outline-primary" href="/posts/new">'
                    '<i class="fa-solid fa-pen-nib me-1"></i>开始创作</a>',
                    '<a class="btn btn-outline-secondary" href="/subscriptions">'
                    '<i class="fa-solid fa-bell me-1"></i>管理订阅</a>',
                ]
            )
            create_button_html = '<a class="btn btn-sm btn-outline-primary" href="/posts/new">新建</a>'
            favorite_heading = "我的收藏"
            subscription_heading = "我的订阅"
        else:
            if has_access:
                favorite_ids = self.interactions.list_favorite_post_ids(target_user["id"])
                favorite_posts = self._hydrate_posts_by_ids(favorite_ids)
                favorites_html = self._build_post_cards(favorite_posts, current_user=current_user)
            else:
                favorites_html = (
                    '<div class="alert alert-warning" role="alert">'
                    "该用户已隐藏收藏，需要访问密码才能查看。"
                    "</div>"
                )
            privacy_settings_html = ""
            if privacy_settings.get("is_subscription_public", True):
                subs = self.subscriptions.list_subscriptions(target_user["id"])
                subscriptions_html = self._build_subscription_list(subs, self.users)
            else:
                subscriptions_html = (
                    '<div class="alert alert-light border-dashed text-muted" role="alert">'
                    "该用户选择隐藏订阅信息。"
                    "</div>"
                )
            actions = []
            if current_user:
                if is_subscribed:
                    actions.append(
                        '<form method="post" action="/subscriptions/cancel" class="d-inline">'
                        f'<input type="hidden" name="type" value="author">'
                        f'<input type="hidden" name="value" value="{html.escape(target_user["username"])}">'
                        f'<input type="hidden" name="next" value="/profile?username={html.escape(target_user["username"])}">'
                        '<button type="submit" class="btn btn-outline-warning">'
                        '<i class="fa-solid fa-bell-slash me-1"></i>取消订阅</button>'
                        '</form>'
                    )
                else:
                    actions.append(
                        '<form method="post" action="/subscriptions/author" class="d-inline">'
                        f'<input type="hidden" name="author" value="{html.escape(target_user["username"])}">'
                        f'<input type="hidden" name="next" value="/profile?username={html.escape(target_user["username"])}">'
                        '<button type="submit" class="btn btn-primary">'
                        '<i class="fa-solid fa-bell me-1"></i>订阅作者</button>'
                        '</form>'
                    )
                actions.append(
                    '<a class="btn btn-outline-primary" href="/messages?view=compose&receiver={username}">'.format(
                        username=html.escape(target_user["username"], quote=True)
                    )
                    + '<i class="fa-regular fa-comments me-1"></i>发送私信</a>'
                )
            else:
                actions.append(
                    '<a class="btn btn-outline-secondary" href="/login">'
                    '<i class="fa-regular fa-user me-1"></i>登录后查看更多</a>'
                )
            profile_actions_html = "".join(actions)
            create_button_html = ""
            favorite_heading = f"{display_name} 的收藏"
            subscription_heading = f"{display_name} 的订阅"
            edit_button_html = ""

        stored_bio = target_user.get("bio", "")
        sanitized_bio = self._sanitize_profile_bio(stored_bio)
        bio_display_html = self._render_profile_bio(sanitized_bio) or '<p class="text-muted mb-0">TA 还没有填写个人简介。</p>'
        email_value = target_user.get("email") or ""
        email_display = html.escape(email_value) if email_value else "未设置"
        feedback_html = ""
        if viewing_self:
            error_message = query_params.get("error", "").strip()
            if error_message:
                feedback_html = (
                    '<div class="alert alert-danger" role="alert">'
                    f"{html.escape(error_message)}"
                    "</div>"
                )
            elif query_params.get("updated") == "1":
                feedback_html = (
                    '<div class="alert alert-success d-flex align-items-center gap-2" role="alert">'
                    '<i class="fa-solid fa-circle-check"></i>'
                    "<span>个人信息已更新。</span>"
                    "</div>"
                )
        edit_section_html = ""
        edit_button_html = ""
        extra_js_scripts = ""
        if viewing_self:
            edit_section_html = self._build_profile_edit_section(target_user, sanitized_bio)
            edit_button_html = (
                '<button type="button" class="btn btn-outline-primary" id="profile-edit-toggle">'
                '<i class="fa-regular fa-pen-to-square me-1"></i>编辑</button>'
            )
            extra_js_scripts = '<script src="/static/js/profile_editor.js"></script>'
        stats_html = ""
        if viewing_self:
            stats_html = (
                f'<div><div class="text-muted small mb-1">粉丝数：</div><div class="fw-semibold">{subscriber_count}</div></div>'
                f'<div><div class="text-muted small mb-1">订阅数：</div><div class="fw-semibold">{subscription_count}</div></div>'
            )
        else:
            stats_html = f'<div><div class="text-muted small mb-1">粉丝数：</div><div class="fw-semibold">{subscriber_count}</div></div>'

        context = {
            "page_title": "个人信息",
            "page_description": "查看个人资料、管理收藏与订阅，回顾你的创作之旅。",
            "username": username_label,
            "email_display": email_display,
            "bio_html": bio_display_html,
            "stats_html": stats_html,
            "profile_feedback_html": feedback_html,
            "profile_edit_section_html": edit_section_html,
            "privacy_settings_html": privacy_settings_html if viewing_self else "",
            "edit_button_html": edit_button_html,
            "authored_posts_html": authored_html,
            "favorite_posts_html": favorites_html,
            "subscriptions_html": subscriptions_html,
            "profile_actions_html": profile_actions_html,
            "authored_heading": "我发布的文章" if viewing_self else f"{display_name} 的文章",
            "favorite_heading": favorite_heading,
            "subscription_heading": subscription_heading,
            "create_button_html": create_button_html,
            "viewing_self": viewing_self,
        }
        if extra_js_scripts:
            context["extra_js_scripts"] = extra_js_scripts
        context.update(self._layout_context("profile", current_user))
        return self.renderer.render("profile.html", context)

    def _build_privacy_settings_section(self, user: Dict[str, Any], privacy_settings: Dict[str, Any]) -> str:
        hide_posts_checked = "checked" if privacy_settings["hide_posts"] else ""
        hide_favorites_checked = "checked" if privacy_settings["hide_favorites"] else ""
        is_subscription_public_checked = "checked" if privacy_settings.get("is_subscription_public", True) else ""
        return (
            '<section class="post-card mt-3">'
            '<h3 class="h6 mb-3"><i class="fa-solid fa-lock me-2 text-warning"></i>隐私设置</h3>'
            '<form method="post" action="/profile/privacy" class="needs-validation" novalidate>'
            '<div class="mb-3">'
            '<div class="form-check form-switch">'
            f'<input class="form-check-input" type="checkbox" id="hide_posts" name="hide_posts" {hide_posts_checked}>'
            '<label class="form-check-label" for="hide_posts">隐藏我的文章</label>'
            '</div>'
            '</div>'
            '<div class="mb-3">'
            '<div class="form-check form-switch">'
            f'<input class="form-check-input" type="checkbox" id="hide_favorites" name="hide_favorites" {hide_favorites_checked}>'
            '<label class="form-check-label" for="hide_favorites">隐藏我的收藏</label>'
            '</div>'
            '</div>'
            '<div class="mb-3">'
            '<div class="form-check form-switch">'
            f'<input class="form-check-input" type="checkbox" id="is_subscription_public" name="is_subscription_public" {is_subscription_public_checked}>'
            '<label class="form-check-label" for="is_subscription_public">是否公开我的订阅列表</label>'
            '</div>'
            '</div>'
            '<div class="mb-3">'
            '<label for="access_password" class="form-label">访问密码（设置后，其他用户需要输入此密码才能查看隐藏内容）</label>'
            '<input type="password" class="form-control" id="access_password" name="access_password" placeholder="留空则不修改密码">'
            '</div>'
            '<button type="submit" class="btn btn-primary">保存隐私设置</button>'
            '</form>'
            '</section>'
        )

    def update_privacy_settings(self, request: HTTPRequest) -> HTTPResponse:
        user = self.get_current_user(request)
        if not user:
            return create_redirect("/login")
        form = request.get_form_data()
        hide_posts = form.get("hide_posts") == "on"
        hide_favorites = form.get("hide_favorites") == "on"
        is_subscription_public = form.get("is_subscription_public") == "on"
        access_password = form.get("access_password", "").strip()
        self.privacy.update_privacy_settings(
            user["id"],
            hide_posts,
            hide_favorites,
            is_subscription_public,
            access_password if access_password else None,
        )
        return create_redirect("/profile?updated=1")

    def update_profile(self, request: HTTPRequest) -> HTTPResponse:
        user = self.get_current_user(request)
        if not user:
            return create_redirect("/login")
        form = request.get_form_data()
        display_name = form.get("display_name", "").strip()
        if not display_name:
            display_name = user.get("username", "")
        if len(display_name) < 2 or len(display_name) > 50:
            message = "显示名称长度需在 2 到 50 个字符之间。"
            return create_redirect(f"/profile?error={quote_plus(message)}")
        email_value = form.get("email", "").strip()
        email_normalized: Optional[str]
        if email_value:
            if not re.fullmatch(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", email_value):
                message = "请输入有效的电子邮箱地址。"
                return create_redirect(f"/profile?error={quote_plus(message)}")
            email_normalized = email_value
        else:
            email_normalized = None
        bio_raw = form.get("bio_content", "")
        if len(bio_raw) > 8000:
            bio_raw = bio_raw[:8000]
        sanitized_bio = self._sanitize_profile_bio(bio_raw)
        self.users.update_profile(
            user_id=user["id"],
            display_name=display_name,
            bio=sanitized_bio,
            email=email_normalized,
            is_vip=user.get("is_vip", False),
        )
        return create_redirect("/profile?updated=1")

    def _sanitize_profile_bio(self, raw_bio: Optional[str]) -> str:
        if raw_bio is None:
            return ""
        normalized = raw_bio.replace("\r\n", "\n").replace("\r", "\n")
        if len(normalized) > 8000:
            normalized = normalized[:8000]
        cleaned = normalized.strip()
        return cleaned

    def _render_profile_bio(self, bio_text: str) -> str:
        if not bio_text:
            return ""
        escaped = html.escape(bio_text)
        return escaped.replace("\n", "<br>")

    def _build_profile_edit_section(self, user: Dict[str, Any], sanitized_bio: str) -> str:
        display_value = html.escape(user.get("display_name") or user.get("username") or "")
        email_value = html.escape(user.get("email") or "")
        bio_text_value = html.escape(sanitized_bio)
        bio_length = len(sanitized_bio)
        return (
            '<section class="post-card p-4">'
            '<div class="d-flex align-items-center justify-content-between mb-3">'
            '<h2 class="h5 mb-0"><i class="fa-regular fa-pen-to-square me-2 text-primary"></i>编辑个人信息</h2>'
            '<button type="button" class="btn btn-sm btn-outline-secondary" id="profile-edit-cancel">'
            '<i class="fa-solid fa-times me-1"></i>取消</button>'
            '</div>'
            '<form method="post" action="/profile" '
            'class="profile-edit-form d-flex flex-column gap-3" data-role="profile-form">'
            '<div>'
            '<label for="profile-display-name" class="form-label fw-semibold">显示名称：</label>'
            f'<input type="text" class="form-control" id="profile-display-name" name="display_name" '
            f'value="{display_value}" maxlength="50" required>'
            "</div>"
            '<div>'
            '<label for="profile-email" class="form-label fw-semibold">邮箱：</label>'
            f'<input type="email" class="form-control" id="profile-email" name="email" value="{email_value}" '
            'placeholder="选填，用于接收订阅通知">'
            "</div>"
            '<div>'
            '<div class="d-flex justify-content-between align-items-center mb-2">'
            '<label for="profile-bio" class="form-label fw-semibold mb-0">个性签名：</label>'
            f'<span class="text-muted small" data-role="bio-counter">{bio_length} / 8000</span>'
            '</div>'
            f'<textarea id="profile-bio" class="form-control profile-bio-input" name="bio_content" rows="6" maxlength="8000" placeholder="写点关于你的故事…" spellcheck="true">{bio_text_value}</textarea>'
            '<div class="form-text">支持纯文本与换行，最多 8000 字符。</div>'
            "</div>"
            '<div class="d-flex justify-content-end gap-2">'
            '<button type="button" class="btn btn-outline-secondary" id="profile-edit-cancel-form">取消</button>'
            '<button type="submit" class="btn btn-primary">'
            '<i class="fa-solid fa-floppy-disk me-1"></i>保存信息'
            '</button>'
            '</div>'
            '</form>'
            '</section>'
        )

    def not_implemented(self, request: HTTPRequest) -> HTTPResponse:
        body_text = "功能建设中"
        body = body_text.encode("utf-8")
        headers = {
            "Content-Type": "text/plain; charset=utf-8",
            "Content-Length": str(len(body)),
            "Connection": "close",
        }
        return HTTPResponse(200, "OK", body, headers)

    def _build_post_cards(
        self,
        posts: List[Dict[str, Any]],
        compact: bool = False,
        current_user: Optional[Dict[str, Any]] = None,
    ) -> str:
        if not posts:
            return '<div class="alert alert-light border-dashed text-muted" role="alert">暂无文章。</div>'
        cards: List[str] = []
        for post in posts:
            post_id = post.get("id", "")
            title = html.escape(post.get("title", "未命名文章"))
            summary_text = self._prepare_post_summary(post)
            summary = html.escape(summary_text)
            author_display = html.escape(post.get("author", {}).get("display_name", "未知作者"))
            author_username = html.escape(post.get("author", {}).get("username", ""))
            if author_username:
                author_html = (
                    f'<a class="text-decoration-none" href="/profile?username={author_username}">{author_display}</a>'
                )
            else:
                author_html = author_display
            category = html.escape(post.get("category", "未分类") or "未分类")
            created_at = html.escape(self._format_timestamp(post.get("created_at")))
            likes = self.interactions.count_likes(post_id)
            favorites = self.interactions.count_favorites(post_id)
            stats_html = (
                '<div class="d-flex align-items-center gap-3 text-muted">'
                f'<span><i class="fa-regular fa-thumbs-up me-1"></i>{likes}</span>'
                f'<span><i class="fa-regular fa-bookmark me-1"></i>{favorites}</span>'
                '</div>'
            )
            actions: List[str] = [
                (
                    f'<a class="btn btn-outline-primary btn-sm" href="/posts/{html.escape(post_id)}">'
                    '<i class="fa-regular fa-eye me-1"></i>阅读全文'
                    '</a>'
                )
            ]
            if current_user and self.posts.is_author(post, current_user):
                actions.append(
                    '<form method="post" action="/posts/{post_id}/delete" '
                    'onsubmit="return confirm(\'确认删除这篇文章吗？删除后无法恢复。\');">'.format(
                        post_id=html.escape(post_id)
                    )
                    + '<button type="submit" class="btn btn-outline-danger btn-sm">'
                    '<i class="fa-solid fa-trash-can me-1"></i>删除'
                    '</button>'
                    '</form>'
                )
            action_html = '<div class="d-flex flex-wrap gap-2">' + "".join(actions) + "</div>"
            heading = f'<h3 class="h5 mb-1"><a class="stretched-link" href="/posts/{html.escape(post_id)}">{title}</a></h3>'
            if compact:
                content_block = (
                    '<article class="post-card p-4">'
                    f'{heading}'
                    f'<p class="meta mb-2"><i class="fa-regular fa-user me-1"></i>{author_html} · '
                    f'<i class="fa-solid fa-tag me-1 ms-2"></i>{category}</p>'
                    f'{stats_html}'
                    '</article>'
                )
            else:
                content_block = (
                    '<article class="post-card position-relative overflow-hidden">'
                    '<div class="d-flex flex-column gap-3">'
                    f'{heading}'
                    f'<p class="meta mb-0"><i class="fa-regular fa-user me-1"></i>{author_html} · '
                    f'<i class="fa-solid fa-tag me-1 ms-2"></i>{category} · '
                    f'<i class="fa-regular fa-clock me-1 ms-2"></i>{created_at}</p>'
                    f'<p class="excerpt mb-0">{summary}</p>'
                    '<div class="d-flex flex-column flex-md-row align-items-md-center justify-content-between gap-3">'
                    f'{stats_html}'
                    f'{action_html}'
                    '</div>'
                    '</div>'
                    '</article>'
                )
            cards.append(content_block)
        return "".join(cards)

    def _prepare_post_summary(self, post: Dict[str, Any]) -> str:
        summary_source = post.get("summary", "")
        plain_text = self._strip_html_tags(summary_source)
        if not plain_text:
            plain_text = self._strip_html_tags(post.get("content", ""))
        if not plain_text:
            return "这篇文章还没有摘要。"
        if len(plain_text) > 160:
            return plain_text[:160].rstrip() + "..."
        return plain_text

    def _build_category_options(self, categories: List[str], selected: str) -> str:
        options = ['<option value="">全部分类</option>']
        for category in categories:
            escaped = html.escape(category)
            if category == selected:
                options.append(f'<option value="{escaped}" selected>{escaped}</option>')
            else:
                options.append(f'<option value="{escaped}">{escaped}</option>')
        return "".join(options)

    def _build_subscription_list(self, subscriptions: List[Dict[str, Any]], user_model: Optional["UserModel"] = None) -> str:
        if not subscriptions:
            return '<div class="alert alert-light border-dashed text-muted" role="alert">暂无订阅。</div>'
        items: List[str] = []
        for subscription in subscriptions:
            label = "分类" if subscription["type"] == "category" else "作者"
            sub_type = html.escape(subscription["type"])
            value_display = html.escape(subscription["value"])
            value_attr = html.escape(subscription["value"], quote=True)
            if subscription["type"] == "author" and user_model:
                author_user = user_model.get_user_by_username(subscription["value"])
                if author_user:
                    author_display = html.escape(author_user.get("display_name", value_display))
                    value_display = author_display
                    items.append(
                        '<div class="card mb-2 shadow-sm border-0 subscription-item-card">'
                        '<div class="card-body d-flex align-items-center justify-content-between py-2">'
                        f'<a href="/profile?username={value_attr}" class="text-decoration-none d-flex align-items-center gap-2">'
                        f'<i class="fa-solid fa-bell me-2 text-warning"></i><span>{label}：{value_display}</span>'
                        '</a>'
                        '</div>'
                        '</div>'
                    )
                    continue
            items.append(
                '<div class="card mb-2 shadow-sm border-0 subscription-item-card">'
                '<div class="card-body d-flex align-items-center justify-content-between py-2">'
                f'<span><i class="fa-solid fa-bell me-2 text-warning"></i>{label}：{value_display}</span>'
                '</div>'
                '</div>'
            )
        return '<div class="d-flex flex-column gap-2">' + "".join(items) + "</div>"

    def _hydrate_posts(self, summaries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        hydrated: List[Dict[str, Any]] = []
        for summary in summaries:
            post = self.posts.get_post_by_id(summary["id"])
            if post:
                hydrated.append(post)
        return hydrated

    def _hydrate_posts_by_ids(self, post_ids: List[str]) -> List[Dict[str, Any]]:
        posts: List[Dict[str, Any]] = []
        for post_id in post_ids:
            post = self.posts.get_post_by_id(post_id)
            if post:
                posts.append(post)
        return posts

    def _load_subscription_posts(self, user: Dict[str, Any], cookies: Dict[str, str]) -> List[Dict[str, Any]]:
        subscriptions = self.subscriptions.list_subscriptions(user["id"])
        collected: Dict[str, Dict[str, Any]] = {}
        for subscription in subscriptions:
            if subscription["type"] == "category":
                posts = self.posts.list_posts(filters={"category": subscription["value"]})
            else:
                posts = self.posts.list_posts(filters={"author": subscription["value"]})
            for post in posts:
                if self._post_accessible(post, user, cookies):
                    collected[post["id"]] = post
        return list(collected.values())

    def _filter_accessible_posts(self, posts: List[Dict[str, Any]], user: Dict[str, Any], cookies: Dict[str, str]) -> List[Dict[str, Any]]:
        accessible: List[Dict[str, Any]] = []
        for post in posts:
            if self._post_accessible(post, user, cookies):
                accessible.append(post)
        return accessible

    def _post_accessible(self, post: Dict[str, Any], user: Optional[Dict[str, Any]], cookies: Dict[str, str]) -> bool:
        security = post.get("security", {})
        permission_type = security.get("permission_type", "public")
        has_password_access = False
        if permission_type == "password":
            cookie_key = f"post_access_{post['id']}"
            has_password_access = cookies.get(cookie_key) == "granted"
        return self.posts.can_view_post(post, user, has_password_access)

    def _is_public_post(self, post: Dict[str, Any]) -> bool:
        security = post.get("security", {})
        return security.get("permission_type", "public") == "public"


class ArticleHandlers(BaseHandler):
    def __init__(
        self,
        renderer: TemplateRenderer,
        auth_service: AuthService,
        post_model: PostModel,
        comment_model: CommentModel,
        interaction_model: InteractionModel,
        subscription_model: SubscriptionModel,
    ) -> None:
        super().__init__(renderer, auth_service)
        self.posts = post_model
        self.comments = comment_model
        self.interactions = interaction_model
        self.subscriptions = subscription_model

    def show_create_post(self, request: HTTPRequest) -> HTTPResponse:
        user = self.get_current_user(request)
        if not user:
            return create_redirect("/login")
        categories = self.posts.list_categories()
        context = {
            "page_title": "发布文章",
            "page_description": "撰写你的灵感，支持多种权限与加密方式。",
            "title_value": "",
            "category_value": "",
            "content_value": "",
            "category_options": self._build_category_select_options(categories, ""),
            "message_block": "",
            "extra_css_links": (
                '<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/quill@1.3.7/dist/quill.snow.css">\n'
                '<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/codemirror.min.css">\n'
                '<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.css">'
            ),
            "extra_js_scripts": (
                '<script src="https://cdn.jsdelivr.net/npm/vue@3/dist/vue.global.prod.js"></script>\n'
                '<script src="https://cdn.jsdelivr.net/npm/quill@1.3.7/dist/quill.min.js"></script>\n'
                '<script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/codemirror.min.js"></script>\n'
                '<script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/mode/markdown/markdown.min.js"></script>\n'
                '<script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/mode/stex/stex.min.js"></script>\n'
                '<script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>\n'
                '<script src="https://cdn.jsdelivr.net/npm/dompurify@3.0.6/dist/purify.min.js"></script>\n'
                '<script src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.js"></script>\n'
                '<script src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/contrib/auto-render.min.js"></script>\n'
                '<script src="/static/js/rich_editor.js"></script>\n'
                '<script src="/static/js/contrast_editor.js"></script>'
            ),
        }
        context.update(self._permission_context("public", "", True, False))
        context.update(self._layout_context("new_post", user))
        return self.renderer.render("new_post.html", context)

    def create_post(self, request: HTTPRequest) -> HTTPResponse:
        user = self.get_current_user(request)
        if not user:
            return create_redirect("/login")
        form = request.get_form_data()
        title = form.get("title", "").strip()
        category = form.get("category", "").strip()
        if not category:
            category = form.get("category_custom", "").strip()
        content = form.get("content", "").strip()
        categories = self.posts.list_categories()
        permission_type = (form.get("permission_type") or "public").strip()
        password_hint = (form.get("password_hint") or "").strip()
        password_value = (form.get("access_password") or "").strip()
        allow_comments = form.get("allow_comments") == "on"
        is_encrypted = form.get("is_encrypted") == "on"
        if not title or not content:
            return self._render_new_post(user, "标题和内容不能为空。", title, category, content, categories, permission_type, password_hint, allow_comments, is_encrypted)
        if len(title) < 3:
            return self._render_new_post(user, "标题长度至少为 3 个字符。", title, category, content, categories, permission_type, password_hint, allow_comments, is_encrypted)
        valid_permissions = {"public", "vip", "password", "private"}
        if permission_type not in valid_permissions:
            return self._render_new_post(user, "请选择有效的访问权限。", title, category, content, categories, permission_type, password_hint, allow_comments, is_encrypted)
        if permission_type == "password" and not password_value:
            return self._render_new_post(user, "密码保护文章必须设置访问密码。", title, category, content, categories, permission_type, password_hint, allow_comments, is_encrypted)
        if permission_type != "password":
            password_hint = ""
            password_value = ""
        summary = content[:160] if len(content) > 160 else content
        post_id = self.posts.create_post(
            author_id=user["id"],
            title=title,
            content=content,
            summary=summary,
            category=category or "未分类",
            tags=None,
            cover_image=None,
            permission_type=permission_type,
            password_hint=password_hint or None,
            password=password_value or None,
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
        return create_redirect(f"/posts/{post_id}")

    def view_post(self, request: HTTPRequest, post_id: str) -> HTTPResponse:
        post = self.posts.get_post_by_id(post_id)
        if post is None:
            return self._build_not_found()

        user = self.get_current_user(request)
        
        # === [新增] 获取 Cookie 中的解锁状态 ===
        password_cookie_key = f"post_access_{post_id}"
        has_password_access = request.get_cookies().get(password_cookie_key) == "granted"
        
        query_params = request.get_query_params()
        error_message = query_params.get("error", "")

        # === [修改] 权限检查逻辑：区分“彻底无权”和“待解锁” ===
        can_view = self.posts.can_view_post(post, user, has_password_access)
        is_locked_content = False

        if not can_view:
            # 获取权限类型
            permission_type = post.get("security", {}).get("permission_type", "public")
            
            # 如果是密码保护类型，我们不直接拒绝，而是标记为“内容锁定”
            # 这样用户仍然可以访问页面，看到标题，但内容会变成输入框
            if permission_type == "password":
                is_locked_content = True
            else:
                # 其他情况（如 private, vip）仍然显示无权访问页面
                return self._render_permission_required(post, user, error_message)

        like_count = self.interactions.count_likes(post_id)
        favorite_count = self.interactions.count_favorites(post_id)
        
        delete_button_html = ""
        if user and self.posts.is_author(post, user):
            escaped_post_id = html.escape(post_id)
            delete_button_html = (
                '<form method="post" action="/posts/{post_id}/delete" class="d-inline" '
                'onsubmit="return confirm(\'确认删除这篇文章吗？删除后无法恢复。\');">'.format(post_id=escaped_post_id)
                + '<button type="submit" class="btn btn-outline-danger btn-sm">'
                '<i class="fa-solid fa-trash-can me-1"></i>删除'
                '</button>'
                '</form>'
            )

        if user:
            liked = post_id in self.interactions.list_like_post_ids(user["id"])
            favorited = post_id in self.interactions.list_favorite_post_ids(user["id"])
            like_label = "取消点赞" if liked else "点赞"
            favorite_label = "取消收藏" if favorited else "收藏"
            comment_form_html = self._build_comment_form(post_id)
        else:
            like_label = "点赞"
            favorite_label = "收藏"
            comment_form_html = (
                '<div class="alert alert-info" role="alert">'
                '请先 <a href="/login" class="alert-link">登录</a> 后发表评论。'
                "</div>"
            )

        comment_data = self.comments.list_nested_comments(post_id)
        comments_html = self._build_comment_list(comment_data)
        author_context = self._build_author_context(post, user)
        
        feedback_html = ""
        if query_params.get("subscribed") == "1":
            feedback_html = (
                '<div class="alert alert-success d-flex align-items-center gap-2" role="alert">'
                '<i class="fa-solid fa-circle-check"></i>'
                '<span>已订阅该作者，后续新文章将通过通知提醒你。</span>'
                "</div>"
            )

        # === [新增] 根据锁定状态生成内容 HTML ===
        if is_locked_content:
            # 渲染解锁表单
            post_content_html = f"""
            <div class="card border-warning mb-3" style="max-width: 30rem; margin: 2rem auto;">
                <div class="card-header bg-warning text-dark fw-bold">
                    <i class="fa-solid fa-lock me-2"></i>内容已加密
                </div>
                <div class="card-body text-center">
                    <p class="card-text">该文章受古老咒语保护，请输入密码解锁。</p>
                    <form class="post-unlock-form" data-post-id="{post['id']}">
                        <div class="input-group mb-3">
                            <input type="password" name="password" class="form-control" placeholder="请输入密码..." required>
                            <button class="btn btn-dark" type="submit">解封</button>
                        </div>
                        <div class="unlock-error text-danger small" style="display:none;"></div>
                    </form>
                </div>
            </div>
            """
        else:
            # 正常渲染内容
            post_content_html = self._format_content(post.get("content", ""), allow_html=True)

        context = {
            "page_title": post["title"],
            "page_description": self._excerpt(post.get("content", "")),
            "post_title": html.escape(post["title"]),
            "post_category": html.escape(post.get("category", "未分类") or "未分类"),
            "post_created_at": html.escape(self._format_timestamp(post.get("created_at"))),
            "post_content_html": post_content_html,  # 使用根据权限生成的 HTML
            "like_count": str(like_count),
            "favorite_count": str(favorite_count),
            "comment_list_html": comments_html,
            "comment_form_html": comment_form_html,
            "like_action_label": like_label,
            "favorite_action_label": favorite_label,
            "post_id": html.escape(post_id),
            "delete_button_html": delete_button_html,
            "post_feedback_html": feedback_html,
            "extra_js_scripts": (
                '<script src="https://cdn.jsdelivr.net/npm/html2canvas@1.4.1/dist/html2canvas.min.js"></script>\n'
                '<script src="https://cdn.jsdelivr.net/npm/jspdf@2.5.1/dist/jspdf.umd.min.js"></script>\n'
                '<script src="https://cdn.jsdelivr.net/npm/html-docx-js@0.3.1/dist/html-docx.js"></script>\n'
                '<script src="/static/js/post_download.js"></script>'
            ),
        }
        context.update(author_context)
        context.update(self._layout_context(None, user))
        return self.renderer.render("post.html", context)
    def add_comment(self, request: HTTPRequest, post_id: str) -> HTTPResponse:
        user = self.get_current_user(request)
        if not user:
            return create_redirect("/login")
        post = self.posts.get_post_by_id(post_id)
        if post is None:
            return self._build_not_found()
        form = request.get_form_data()
        content = form.get("content", "").strip()
        parent_id = form.get("parent_id") or None
        if not content:
            return create_redirect(f"/posts/{post_id}")
        emoji_value = form.get("emoji", "").strip()
        self.comments.add_comment(
            post_id=post_id,
            author_id=user["id"],
            content=content,
            parent_id=parent_id,
            emoji=emoji_value or None,
        )
        return create_redirect(f"/posts/{post_id}")

    def unlock_post(self, request: HTTPRequest, post_id: str) -> HTTPResponse:
        from urllib.parse import quote_plus
        form = request.get_form_data()
        password = form.get("password", "").strip()
        if not password:
            return create_redirect(f"/posts/{post_id}?error={quote_plus('密码不能为空')}")
        if not self.posts.verify_post_password(post_id, password):
            return create_redirect(f"/posts/{post_id}?error={quote_plus('密码错误，请重试')}")
        cookie_key = f"post_access_{post_id}"
        redirect_url = f"/posts/{post_id}"
        from http_types import HTTPResponse
        response = HTTPResponse(
            302,
            "Found",
            b"",
            {
                "Location": redirect_url,
                "Set-Cookie": f"{cookie_key}=granted; Path=/; Max-Age=86400",
            },
        )
        return response

    def handle_favorite(self, request: HTTPRequest, post_id: str) -> HTTPResponse:
        user = self.get_current_user(request)
        if not user:
            return create_redirect("/login")
        post = self.posts.get_post_by_id(post_id)
        if post is None:
            return self._build_not_found()
        self.interactions.toggle_favorite(user["id"], post_id)
        return create_redirect(f"/posts/{post_id}")

    def handle_like(self, request: HTTPRequest, post_id: str) -> HTTPResponse:
        user = self.get_current_user(request)
        if not user:
            return create_redirect("/login")
        post = self.posts.get_post_by_id(post_id)
        if post is None:
            return self._build_not_found()
        self.interactions.toggle_like(user["id"], post_id)
        return create_redirect(f"/posts/{post_id}")

    def delete_post(self, request: HTTPRequest, post_id: str) -> HTTPResponse:
        user = self.get_current_user(request)
        if not user:
            return create_redirect("/login")
        post = self.posts.get_post_by_id(post_id)
        if post is None:
            return self._build_not_found()
        if not self.posts.is_author(post, user):
            return self._build_forbidden_response("无权删除这篇文章。")
        self.comments.delete_comments_by_post(post_id)
        self.interactions.delete_post_records(post_id)
        self.posts.delete_post(post_id)
        return create_redirect("/profile")

    def _render_new_post(
        self,
        user: Optional[Dict[str, Any]],
        message: str,
        title: str,
        category: str,
        content: str,
        categories: List[str],
        permission_type: str = "public",
        password_hint: str = "",
        allow_comments: bool = True,
        is_encrypted: bool = False,
    ) -> HTTPResponse:
        alert_html = ""
        if message:
            alert_html = (
                '<div class="alert alert-warning" role="alert">'
                f"{html.escape(message)}"
                "</div>"
            )
        context = {
            "page_title": "发布文章",
            "page_description": "设置文章分类、权限与可见性，打造独特内容。",
            "title_value": html.escape(title),
            "category_value": html.escape(category),
            "content_value": html.escape(content),
            "category_options": self._build_category_select_options(categories, category),
            "message_block": alert_html,
            "extra_css_links": (
                '<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/quill@1.3.7/dist/quill.snow.css">\n'
                '<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/codemirror.min.css">\n'
                '<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.css">'
            ),
            "extra_js_scripts": (
                '<script src="https://cdn.jsdelivr.net/npm/vue@3/dist/vue.global.prod.js"></script>\n'
                '<script src="https://cdn.jsdelivr.net/npm/quill@1.3.7/dist/quill.min.js"></script>\n'
                '<script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/codemirror.min.js"></script>\n'
                '<script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/mode/markdown/markdown.min.js"></script>\n'
                '<script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/mode/stex/stex.min.js"></script>\n'
                '<script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>\n'
                '<script src="https://cdn.jsdelivr.net/npm/dompurify@3.0.6/dist/purify.min.js"></script>\n'
                '<script src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.js"></script>\n'
                '<script src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/contrib/auto-render.min.js"></script>\n'
                '<script src="/static/js/rich_editor.js"></script>\n'
                '<script src="/static/js/contrast_editor.js"></script>'
            ),
        }
        context.update(self._permission_context(permission_type, password_hint, allow_comments, is_encrypted))
        context.update(self._layout_context("new_post", user))
        return self.renderer.render("new_post.html", context)

    def _permission_context(
        self,
        permission_type: str,
        password_hint: str,
        allow_comments: bool,
        is_encrypted: bool,
    ) -> Dict[str, Any]:
        return {
            "permission_public_selected": "selected" if permission_type == "public" else "",
            "permission_vip_selected": "selected" if permission_type == "vip" else "",
            "permission_password_selected": "selected" if permission_type == "password" else "",
            "permission_private_selected": "selected" if permission_type == "private" else "",
            "password_hint_value": html.escape(password_hint),
            "allow_comments_checked": "checked" if allow_comments else "",
            "is_encrypted_checked": "checked" if is_encrypted else "",
            "password_field_class": "" if permission_type == "password" else "d-none",
        }

    def _build_category_select_options(self, categories: List[str], selected: str) -> str:
        options = ['<option value="">未分类</option>']
        for category in categories:
            escaped = html.escape(category)
            if category == selected:
                options.append(f'<option value="{escaped}" selected>{escaped}</option>')
            else:
                options.append(f'<option value="{escaped}">{escaped}</option>')
        return "".join(options)

    def _build_comment_list(self, comments: List[Dict[str, Any]]) -> str:
        if not comments:
            return "<p>暂无评论，快来抢沙发吧！</p>"
        items: List[str] = []
        for comment in comments:
            items.append(self._render_comment_node(comment, depth=0))
        return "".join(items)

    def _render_comment_node(self, comment: Dict[str, Any], depth: int) -> str:
        author = html.escape(comment["author"]["display_name"])
        created = html.escape(self._format_timestamp(comment.get("created_at")))
        content_html = self._format_content(comment.get("content", ""))
        emoji = comment.get("emoji")
        emoji_html = f'<span class="comment-emoji">{html.escape(emoji)}</span>' if emoji else ""
        indent_class = f" comment-depth-{depth}"
        children = comment.get("children", [])
        children_html = "".join(self._render_comment_node(child, depth + 1) for child in children)
        return (
            f'<div class="comment-item{indent_class}">'
            f'<p class="comment-meta">{author} 发表于 {created}</p>'
            f'<div class="comment-content">{emoji_html}{content_html}</div>'
            f'{children_html}'
            "</div>"
        )

    def _format_content(self, content: str, allow_html: bool = False) -> str:
        if not content:
            return ""
        if allow_html:
            return self._sanitize_rich_text(content)
        escaped = html.escape(content)
        return escaped.replace("\n", "<br>")

    def _sanitize_rich_text(self, content: str) -> str:
        sanitizer = _RichTextSanitizer(_ALLOWED_RICH_TEXT_TAGS, _ALLOWED_RICH_TEXT_ATTRS, _ALLOWED_RICH_TEXT_STYLES)
        sanitizer.feed(content)
        sanitizer.close()
        return sanitizer.get_html()

    def _build_author_context(self, post: Dict[str, Any], current_user: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        author = post.get("author", {})
        post_id = post.get("id", "")
        username = author.get("username") or ""
        display_name = author.get("display_name") or username or "未知作者"
        escaped_username = html.escape(username)
        username_label = f"@{escaped_username}" if username else ""

        action_items: List[str] = []
        if username:
            if current_user and current_user.get("username") != username:
                action_items.append(
                    '<li>'
                    f'<a class="dropdown-item d-flex align-items-center gap-2" href="/messages?view=compose&receiver={escaped_username}">'
                    '<i class="fa-regular fa-comments text-primary"></i>'
                    '<span>发送私信</span>'
                    '</a>'
                    '</li>'
                )
            elif not current_user:
                action_items.append(
                    '<li>'
                    '<a class="dropdown-item d-flex align-items-center gap-2" href="/login">'
                    '<i class="fa-regular fa-comments text-secondary"></i>'
                    '<span>登录后发送私信</span>'
                    '</a>'
                    '</li>'
                )
            else:
                action_items.append(
                    '<li>'
                    '<span class="dropdown-item-text text-muted d-flex align-items-center gap-2">'
                    '<i class="fa-regular fa-comments text-secondary"></i>'
                    '<span>无法给自己发送私信</span>'
                    '</span>'
                    '</li>'
                )

            profile_href = f"/profile?username={escaped_username}"
            action_items.append(
                '<li>'
                f'<a class="dropdown-item d-flex align-items-center gap-2" href="{profile_href}">'
                '<i class="fa-regular fa-id-card text-success"></i>'
                '<span>查看个人主页</span>'
                '</a>'
                '</li>'
            )

            if current_user and current_user.get("username") != username:
                redirect_back = f"/posts/{post_id}?subscribed=1" if post_id else "/subscriptions"
                if not redirect_back.startswith("/"):
                    redirect_back = "/subscriptions"
                escaped_redirect = html.escape(redirect_back)
                action_items.append(
                    '<li>'
                    '<form method="post" action="/subscriptions/author" class="dropdown-item p-0">'
                    f'<input type="hidden" name="author" value="{escaped_username}">'
                    f'<input type="hidden" name="next" value="{escaped_redirect}">'
                    '<button type="submit" class="dropdown-item-action d-flex align-items-center gap-2">'
                    '<i class="fa-solid fa-bell text-warning"></i>'
                    '<span>订阅作者</span>'
                    '</button>'
                    '</form>'
                    '</li>'
                )
            elif not current_user:
                action_items.append(
                    '<li>'
                    '<a class="dropdown-item d-flex align-items-center gap-2" href="/login">'
                    '<i class="fa-solid fa-bell text-secondary"></i>'
                    '<span>登录后订阅作者</span>'
                    '</a>'
                    '</li>'
                )
            else:
                action_items.append(
                    '<li>'
                    '<span class="dropdown-item-text text-muted d-flex align-items-center gap-2">'
                    '<i class="fa-solid fa-bell-slash text-secondary"></i>'
                    '<span>这是你的文章</span>'
                    '</span>'
                    '</li>'
                )
        else:
            action_items.extend(
                [
                    '<li><span class="dropdown-item-text text-muted d-flex align-items-center gap-2">'
                    '<i class="fa-regular fa-comments text-secondary"></i>'
                    '<span>作者信息暂不可用</span>'
                    '</span></li>',
                    '<li><span class="dropdown-item-text text-muted d-flex align-items-center gap-2">'
                    '<i class="fa-regular fa-id-card text-secondary"></i>'
                    '<span>无法查看主页</span>'
                    '</span></li>',
                    '<li><span class="dropdown-item-text text-muted d-flex align-items-center gap-2">'
                    '<i class="fa-solid fa-circle-info text-secondary"></i>'
                    '<span>暂无法订阅该作者</span>'
                    '</span></li>',
                ]
            )

        author_profile_link = f"/profile?username={escaped_username}" if username else "#"
        return {
            "post_author": html.escape(display_name),
            "author_username_label": username_label,
            "author_action_items_html": "".join(action_items),
            "author_profile_link": author_profile_link,
        }

    def _build_comment_form(self, post_id: str) -> str:
        escaped_post_id = html.escape(post_id)
        return (
            '<form method="post" action="/posts/' + escaped_post_id + '/comment" class="comment-form">'
            '<div class="mb-3">'
            '<label class="form-label fw-semibold" for="comment-content">评论内容</label>'
            '<textarea id="comment-content" class="form-control" name="content" rows="4" required placeholder="写下你的评论..."></textarea>'
            '</div>'
            '<div class="row g-3 align-items-center">'
            '<div class="col-sm-8">'
            '<input type="text" class="form-control" name="emoji" placeholder="输入表情（可选，比如 😊）">'
            '</div>'
            '<div class="col-sm-4 d-grid">'
            '<button type="submit" class="btn btn-primary">'
            '<i class="fa-regular fa-paper-plane me-1"></i>发表评论'
            '</button>'
            '</div>'
            '</div>'
            '</form>'
        )

    def _build_not_found(self) -> HTTPResponse:
        body_text = "未找到内容"
        body = body_text.encode("utf-8")
        headers = {
            "Content-Type": "text/plain; charset=utf-8",
            "Content-Length": str(len(body)),
            "Connection": "close",
        }
        return HTTPResponse(404, "Not Found", body, headers)

    def _render_permission_required(self, post: Dict[str, Any], user: Optional[Dict[str, Any]], error_message: str = "") -> HTTPResponse:
        permission = post.get("security", {}).get("permission_type", "public")
        if permission == "vip":
            message = "该文章仅对 VIP 用户开放。"
        elif permission == "password":
            message = "该文章已加密，请输入访问密码。"
        elif permission == "private":
            message = "该文章为私密内容，仅作者可见。"
        else:
            message = "您暂无权访问该内容。"
        if error_message:
            message = html.escape(error_message)
        author_context = self._build_author_context(post, user)
        context = {
            "page_title": post.get("title", "访问受限"),
            "page_description": "该内容暂不可见，请根据提示解锁访问权限。",
            "post_title": html.escape(post.get("title", "访问受限")),
            "permission_message": message,
            "post_category": html.escape(post.get("category", "未分类") or "未分类"),
            "post_created_at": html.escape(self._format_timestamp(post.get("created_at"))),
            "post_content_html": f'<p class="permission-message mb-0">{html.escape(message)}</p>',
            "like_count": "0",
            "favorite_count": "0",
            "comment_list_html": f'<p class="permission-warning mb-0">{html.escape(message)}</p>',
            "comment_form_html": self._build_unlock_form(post["id"], permission, post.get("security", {}).get("is_encrypted", False)) if (permission == "password" or post.get("security", {}).get("is_encrypted", False)) else "",
            "like_action_label": "点赞",
            "favorite_action_label": "收藏",
            "post_id": html.escape(post["id"]),
            "post_feedback_html": "",
        }
        context.update(author_context)
        context.update(self._layout_context(None, user))
        return self.renderer.render("post.html", context)

    def _build_unlock_form(self, post_id: str, permission: str, is_encrypted: bool = False) -> str:
        if permission != "password" and not is_encrypted:
            return ""
        escaped_post_id = html.escape(post_id)
        modal_id = f"unlockModal_{escaped_post_id[:8]}"
        return (
            '<div class="mb-3">'
            '<button type="button" class="btn btn-primary" data-bs-toggle="modal" data-bs-target="#' + modal_id + '">'
            '<i class="fa-solid fa-lock me-1"></i>输入密码解锁'
            '</button>'
            '</div>'
            '<div class="modal fade" id="' + modal_id + '" tabindex="-1" aria-labelledby="' + modal_id + 'Label" aria-hidden="true">'
            '<div class="modal-dialog">'
            '<div class="modal-content">'
            '<div class="modal-header">'
            '<h5 class="modal-title" id="' + modal_id + 'Label">输入访问密码</h5>'
            '<button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>'
            '</div>'
            '<form method="post" action="/posts/' + escaped_post_id + '/unlock" id="unlockForm_' + escaped_post_id[:8] + '">'
            '<div class="modal-body">'
            '<div class="mb-3">'
            '<label for="password_' + escaped_post_id[:8] + '" class="form-label">访问密码</label>'
            '<input type="password" class="form-control" id="password_' + escaped_post_id[:8] + '" name="password" placeholder="请输入访问密码" required>'
            '<div class="invalid-feedback" id="password-feedback_' + escaped_post_id[:8] + '"></div>'
            '</div>'
            '</div>'
            '<div class="modal-footer">'
            '<button type="button" class="btn btn-secondary" data-bs-dismiss="modal">取消</button>'
            '<button type="submit" class="btn btn-primary">'
            '<i class="fa-solid fa-lock-open me-1"></i>解锁'
            '</button>'
            '</div>'
            '</form>'
            '</div>'
            '</div>'
            '</div>'
        )

    def _build_forbidden_response(self, message: str) -> HTTPResponse:
        body = message.encode("utf-8")
        headers = {
            "Content-Type": "text/plain; charset=utf-8",
            "Content-Length": str(len(body)),
            "Connection": "close",
        }
        return HTTPResponse(403, "Forbidden", body, headers)


class SubscriptionHandlers(BaseHandler):
    def __init__(
        self,
        renderer: TemplateRenderer,
        auth_service: AuthService,
        subscription_model: SubscriptionModel,
        post_model: PostModel,
        user_model: "UserModel",
    ) -> None:
        super().__init__(renderer, auth_service)
        self.subscriptions = subscription_model
        self.posts = post_model
        self.users = user_model

    def show_subscriptions(self, request: HTTPRequest) -> HTTPResponse:
        user = self.get_current_user(request)
        if not user:
            return create_redirect("/login")
        return self._render_page(request, user, "")

    def subscribe_category(self, request: HTTPRequest) -> HTTPResponse:
        user = self.get_current_user(request)
        if not user:
            return create_redirect("/login")
        form = request.get_form_data()
        category = form.get("category", "").strip()
        if not category:
            category = form.get("category_custom", "").strip()
        if not category:
            return self._render_page(request, user, "请选择或输入要订阅的分类。")
        existing_categories = self.posts.list_categories()
        if category not in existing_categories:
            return self._render_page(request, user, f"分类 {html.escape(category)} 不存在，请先选择已有分类或确保该分类下有文章。")
        self.subscriptions.add_subscription(user["id"], "category", category)
        return self._render_page(request, user, f"已订阅分类：{html.escape(category)}。")

    def subscribe_author(self, request: HTTPRequest) -> HTTPResponse:
        user = self.get_current_user(request)
        if not user:
            return create_redirect("/login")
        form = request.get_form_data()
        author = form.get("author", "").strip()
        next_url = form.get("next", "").strip()
        redirect_target = ""
        if next_url.startswith("/"):
            redirect_target = next_url
        if not author:
            return self._render_page(request, user, "请输入要订阅的作者用户名。")
        author_user = self.users.get_user_by_username(author)
        if not author_user:
            return self._render_page(request, user, f"用户 {html.escape(author)} 不存在，无法订阅。")
        if author_user["id"] == user["id"]:
            return self._render_page(request, user, "不能订阅自己。")
        self.subscriptions.add_subscription(user["id"], "author", author)
        if redirect_target:
            return create_redirect(redirect_target)
        return self._render_page(request, user, f"已订阅作者：{html.escape(author)}。")

    def cancel_subscription(self, request: HTTPRequest) -> HTTPResponse:
        user = self.get_current_user(request)
        if not user:
            return create_redirect("/login")
        form = request.get_form_data()
        sub_type = form.get("type", "").strip()
        value = form.get("value", "").strip()
        if not sub_type or not value:
            return self._render_page(request, user, "订阅信息不完整，无法取消。")
        self.subscriptions.remove_subscription_by_value(user["id"], sub_type, value)
        return self._render_page(request, user, "订阅已取消。")

    def _render_page(self, request: HTTPRequest, user: Dict[str, Any], message: str) -> HTTPResponse:
        categories = self.posts.list_categories()
        subscriptions = self.subscriptions.list_subscriptions(user["id"])
        category_options = self._build_category_options(categories)
        subscription_list_html = self._build_subscription_list(subscriptions)
        posts = self._collect_subscription_posts(subscriptions, user, request.get_cookies())
        posts_html = self._build_post_cards(posts)
        alert_html = ""
        if message:
            alert_html = (
                '<div class="alert alert-info" role="alert">'
                f"{html.escape(message)}"
                "</div>"
            )
        context = {
            "page_title": "订阅管理",
            "page_description": "统一管理关注的分类与作者，查看最新推送并维护订阅。",
            "message": message,
            "category_options": category_options,
            "subscription_list_html": subscription_list_html,
            "subscription_posts_html": posts_html,
            "message_block": alert_html,
        }
        context.update(self._layout_context("subscriptions", user))
        return self.renderer.render("subscriptions.html", context)

    def _build_category_options(self, categories: List[str]) -> str:
        options = ['<option value="">请选择分类</option>']
        for category in categories:
            escaped = html.escape(category)
            options.append(f'<option value="{escaped}">{escaped}</option>')
        return "".join(options)

    def _build_subscription_list(self, subscriptions: List[Dict[str, Any]]) -> str:
        if not subscriptions:
            return '<div class="alert alert-light border-dashed text-muted" role="alert">暂无订阅。</div>'
        items: List[str] = []
        for subscription in subscriptions:
            label = "分类" if subscription["type"] == "category" else "作者"
            sub_type = html.escape(subscription["type"])
            value_display = html.escape(subscription["value"])
            value_attr = html.escape(subscription["value"], quote=True)
            action_buttons = []
            if subscription["type"] == "author":
                author_user = self.users.get_user_by_username(subscription["value"])
                display_name = author_user.get("display_name", value_display) if author_user else value_display
                value_display = html.escape(display_name)
                action_buttons.append(
                    f'<a class="btn btn-sm btn-outline-primary" href="/messages?view=compose&receiver={value_attr}">'
                    '<i class="fa-regular fa-comments me-1"></i>私信</a>'
                )
            action_buttons.append(
                '<form method="post" action="/subscriptions/cancel" class="d-inline">'
                f'<input type="hidden" name="type" value="{sub_type}">'
                f'<input type="hidden" name="value" value="{value_attr}">'
                '<button type="submit" class="btn btn-sm btn-outline-danger">'
                '<i class="fa-regular fa-circle-xmark me-1"></i>取消'
                '</button>'
                '</form>'
            )
            items.append(
                '<div class="card mb-2 shadow-sm border-0 subscription-item-card">'
                '<div class="card-body d-flex align-items-center justify-content-between py-2">'
                f'<span><i class="fa-solid fa-bell me-2 text-warning"></i>{label}：{value_display}</span>'
                '<div class="d-flex gap-2">' + "".join(action_buttons) + '</div>'
                '</div>'
                '</div>'
            )
        return '<div class="d-flex flex-column gap-2">' + "".join(items) + "</div>"

    def _collect_subscription_posts(self, subscriptions: List[Dict[str, Any]], user: Dict[str, Any], cookies: Dict[str, str]) -> List[Dict[str, Any]]:
        collected: Dict[str, Dict[str, Any]] = {}
        for subscription in subscriptions:
            if subscription["type"] == "category":
                posts = self.posts.list_posts(filters={"category": subscription["value"]})
            else:
                posts = self.posts.list_posts(filters={"author": subscription["value"]})
            for post in posts:
                if self._post_accessible(post, user, cookies):
                    collected[post["id"]] = post
        return list(collected.values())

    def _post_accessible(self, post: Dict[str, Any], user: Optional[Dict[str, Any]], cookies: Dict[str, str]) -> bool:
        security = post.get("security", {})
        permission_type = security.get("permission_type", "public")
        has_password_access = False
        if permission_type == "password":
            cookie_key = f"post_access_{post['id']}"
            has_password_access = cookies.get(cookie_key) == "granted"
        return self.posts.can_view_post(post, user, has_password_access)

    def _build_post_cards(self, posts: List[Dict[str, Any]]) -> str:
        if not posts:
            return '<div class="alert alert-light border-dashed text-muted" role="alert">当前订阅暂无推送。</div>'
        cards: List[str] = []
        for post in posts:
            post_id = html.escape(post["id"])
            title = html.escape(post["title"])
            author = html.escape(post["author"]["display_name"])
            category = html.escape(post.get("category", "未分类") or "未分类")
            created_at = html.escape(self._format_timestamp(post.get("created_at")))
            cards.append(
                '<article class="post-card position-relative">'
                f'<h3 class="h6 mb-2"><a class="stretched-link" href="/posts/{post_id}">{title}</a></h3>'
                f'<p class="meta mb-0"><i class="fa-regular fa-user me-1"></i>{author} · '
                f'<i class="fa-solid fa-tag me-1 ms-2"></i>{category} · '
                f'<i class="fa-regular fa-clock me-1 ms-2"></i>{created_at}</p>'
                "</article>"
            )
        return "".join(cards)


class MessageHandlers(BaseHandler):
    def __init__(
        self,
        renderer: TemplateRenderer,
        auth_service: AuthService,
        message_model: MessageModel,
        user_model: UserModel,
    ) -> None:
        super().__init__(renderer, auth_service)
        self.messages = message_model
        self.users = user_model

    def mailbox(self, request: HTTPRequest) -> HTTPResponse:
        user = self.get_current_user(request)
        if not user:
            return create_redirect("/login")
        query_params = request.get_query_params()
        view = query_params.get("view", "inbox")
        receiver = query_params.get("receiver", "").strip()
        context = {
            "page_title": "私信",
            "page_description": "邮箱式私信系统，管理您的所有消息。",
            "current_view": view,
            "receiver_username": receiver or "",
            "current_user_id": user["id"],
            "extra_js_scripts": '<script src="/static/js/mailbox.js"></script>',
        }
        context.update(self._layout_context("messages", user))
        return self.renderer.render("mailbox.html", context)

    def view_conversation(self, request: HTTPRequest, target_username: str) -> HTTPResponse:
        user = self.get_current_user(request)
        if not user:
            return create_redirect("/login")
        target = self.users.get_user_by_username(target_username)
        if target is None:
            return create_redirect("/messages")
        conversation = self.messages.list_messages_between(user["id"], target["id"])
        conversation_html = self._build_conversation(conversation, user["id"])
        context = {
            "page_title": f"与 {html.escape(target['display_name'])} 的对话",
            "page_description": f"与 {html.escape(target['display_name'])} 的最新对话记录与消息状态。",
            "target_username": html.escape(target_username),
            "conversation_html": conversation_html,
            "message": "",
        }
        context.update(self._layout_context("messages", user))
        return self.renderer.render("conversation.html", context)

    def send_message(self, request: HTTPRequest) -> HTTPResponse:
        user = self.get_current_user(request)
        if not user:
            return create_redirect("/login")
        form = request.get_form_data()
        target_username = form.get("target", "").strip()
        content = form.get("content", "").strip()
        if not target_username or not content:
            return create_redirect("/messages")
        target = self.users.get_user_by_username(target_username)
        if target is None:
            return create_redirect("/messages")
        self.messages.send_message(user["id"], target["id"], content)
        return create_redirect(f"/messages/{target_username}")

    def _collect_contacts(self, user_id: int, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        contacts: Dict[int, Dict[str, Any]] = {}
        for message in messages:
            if message.get("sender_id") == user_id:
                other_id = message.get("receiver_id")
                receiver = message.get("receiver", {})
                other_username = receiver.get("username") if isinstance(receiver, dict) else ""
                other_display = receiver.get("display_name") if isinstance(receiver, dict) else ""
            else:
                other_id = message.get("sender_id")
                sender = message.get("sender", {})
                other_username = sender.get("username") if isinstance(sender, dict) else ""
                other_display = sender.get("display_name") if isinstance(sender, dict) else ""
            if not other_username or not other_id:
                continue
            if not other_display:
                other_display = other_username
            if other_id not in contacts:
                contacts[other_id] = {
                    "username": other_username,
                    "display_name": other_display,
                }
        return list(contacts.values())

    def _build_contact_list(self, contacts: List[Dict[str, Any]], active_username: Optional[str] = None) -> str:
        if not contacts:
            return '<div class="alert alert-light border-dashed text-muted" role="alert">暂无私信联系人，点击"新建私信"开始对话。</div>'
        items: List[str] = []
        for contact in contacts:
            username = html.escape(contact["username"])
            raw_display = contact["display_name"] or contact["username"]
            display_name = html.escape(raw_display)
            is_active = active_username == contact["username"]
            classes = "list-group-item list-group-item-action d-flex align-items-center justify-content-between conversation-item"
            if is_active:
                classes += " active"
            items.append(
                f'<a class="{classes}" href="#" data-username="{username}" data-display-name="{display_name}" data-role="open-conversation">'
                f'<div class="d-flex align-items-center gap-2">'
                f'<i class="fa-regular fa-user-circle text-primary"></i>'
                f'<span>{display_name}</span>'
                f'</div>'
                '</a>'
            )
        return '<div class="list-group list-group-flush">' + "".join(items) + "</div>"

    def _build_conversation(self, conversation: List[Dict[str, Any]], current_user_id: int) -> str:
        if not conversation:
            return '<div class="message-thread"><div class="alert alert-light border-dashed text-muted mb-0" role="alert">暂未开始对话，发送第一条私信吧！</div></div>'
        bubbles: List[str] = []
        for message in conversation:
            is_self = message["sender_id"] == current_user_id
            role_class = "message-bubble--self" if is_self else "message-bubble--other"
            sender_label = "我" if is_self else html.escape(message["sender"]["display_name"] or message["sender"]["username"])
            created_at = html.escape(self._format_timestamp(message.get("created_at")))
            content_html = html.escape(message.get("content", "")).replace("\n", "<br>")
            bubbles.append(
                '<div class="message-bubble {role}">'.format(role=role_class)
                + f'<div class="message-body"><span class="message-sender">{sender_label}</span>'
                + f'<div class="message-text">{content_html}</div>'
                + f'<span class="message-time">{created_at}</span></div>'
                + "</div>"
            )
        return '<div class="message-thread">' + "".join(bubbles) + "</div>"

