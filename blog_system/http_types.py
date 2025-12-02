import json
from typing import Dict, Optional, Any


class HTTPRequest:
    def __init__(self, raw_data: bytes) -> None:
        self.raw_data = raw_data
        self.method = ""
        self.path = ""
        self.query = ""
        self.http_version = "HTTP/1.1"
        self.headers: Dict[str, str] = {}
        self.body = b""
        self._query_params_cache: Optional[Dict[str, str]] = None
        self._form_params_cache: Optional[Dict[str, str]] = None
        self._cookies_cache: Optional[Dict[str, str]] = None
        self._files_cache: Optional[Dict[str, Dict[str, Any]]] = None
        self._json_cache: Optional[Any] = None
        self._parse()

    def _parse(self) -> None:
        header_bytes, separator, body_bytes = self.raw_data.partition(b"\r\n\r\n")
        header_text = header_bytes.decode("utf-8", errors="replace")
        header_lines = header_text.split("\r\n")
        if header_lines:
            request_line = header_lines[0]
            parts = request_line.split()
            if len(parts) >= 3:
                self.method, full_path, self.http_version = parts[0], parts[1], parts[2]
            elif len(parts) == 2:
                self.method, full_path = parts[0], parts[1]
            elif len(parts) == 1:
                self.method = parts[0]
                full_path = "/"
            else:
                full_path = "/"
        else:
            full_path = "/"
        if "?" in full_path:
            path_part, query_part = full_path.split("?", 1)
            self.path = path_part or "/"
            self.query = query_part
        else:
            self.path = full_path or "/"
            self.query = ""

        for line in header_lines[1:]:
            if not line or ":" not in line:
                continue
            name, value = line.split(":", 1)
            self.headers[name.strip().lower()] = value.strip()
        if separator:
            self.body = body_bytes
        else:
            self.body = b""

    def get_header(self, name: str, default: Optional[str] = None) -> Optional[str]:
        return self.headers.get(name.lower(), default)

    def get_query_params(self) -> Dict[str, str]:
        if self._query_params_cache is None:
            from urllib.parse import parse_qs

            parsed = parse_qs(self.query, keep_blank_values=True)
            simplified: Dict[str, str] = {}
            for key, values in parsed.items():
                if values:
                    simplified[key] = values[0]
                else:
                    simplified[key] = ""
            self._query_params_cache = simplified
        return self._query_params_cache

    def get_form_data(self) -> Dict[str, str]:
        if self._form_params_cache is None:
            content_type = self.get_header("content-type", "")
            if content_type is None:
                content_type = ""
            if "application/x-www-form-urlencoded" in content_type:
                from urllib.parse import parse_qs

                charset = "utf-8"
                if "charset=" in content_type:
                    charset = content_type.split("charset=", 1)[1]
                decoded = self.body.decode(charset, errors="replace")
                parsed = parse_qs(decoded, keep_blank_values=True)
                simplified: Dict[str, str] = {}
                for key, values in parsed.items():
                    if values:
                        simplified[key] = values[0]
                    else:
                        simplified[key] = ""
                self._form_params_cache = simplified
                self._files_cache = {}
            elif "multipart/form-data" in content_type:
                self._parse_multipart_form(content_type)
            else:
                self._form_params_cache = {}
                self._files_cache = {}
        return self._form_params_cache

    def get_files(self) -> Dict[str, Dict[str, Any]]:
        if self._files_cache is None:
            # Ensure form data parsing populates files cache if needed
            self.get_form_data()
        if self._files_cache is None:
            self._files_cache = {}
        return self._files_cache

    def get_json(self) -> Optional[Any]:
        if self._json_cache is not None:
            return self._json_cache
        content_type = self.get_header("content-type", "")
        if not content_type or "application/json" not in content_type.lower():
            return None
        try:
            decoded = self.body.decode("utf-8")
            self._json_cache = json.loads(decoded) if decoded else {}
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._json_cache = None
        return self._json_cache

    def get_cookies(self) -> Dict[str, str]:
        if self._cookies_cache is None:
            cookie_header = self.get_header("cookie", "")
            cookies: Dict[str, str] = {}
            if cookie_header:
                parts = cookie_header.split(";")
                for part in parts:
                    if "=" in part:
                        name, value = part.split("=", 1)
                        cookies[name.strip()] = value.strip()
            self._cookies_cache = cookies
        return self._cookies_cache

    def _parse_multipart_form(self, content_type: str) -> None:
        boundary_token = ""
        parameters = content_type.split(";")
        for parameter in parameters:
            parameter = parameter.strip()
            if parameter.startswith("boundary="):
                boundary_token = parameter.split("=", 1)[1].strip()
                if boundary_token.startswith('"') and boundary_token.endswith('"'):
                    boundary_token = boundary_token[1:-1]
                break
        if not boundary_token:
            self._form_params_cache = {}
            self._files_cache = {}
            return
        boundary_bytes = ("--" + boundary_token).encode("utf-8")
        segments = self.body.split(boundary_bytes)
        form_values: Dict[str, str] = {}
        file_values: Dict[str, Dict[str, Any]] = {}
        for segment in segments:
            if not segment:
                continue
            if segment == b"--\r\n" or segment == b"--" or segment == b"\r\n--" or segment == b"--\r\n--":
                continue
            if segment.startswith(b"\r\n"):
                segment = segment[2:]
            if segment.endswith(b"\r\n"):
                segment = segment[:-2]
            header_bytes, separator, content_bytes = segment.partition(b"\r\n\r\n")
            if not separator:
                continue
            header_text = header_bytes.decode("utf-8", errors="replace")
            headers = header_text.split("\r\n")
            disposition_header = ""
            content_type_header = ""
            for header_line in headers:
                lower_line = header_line.lower()
                if lower_line.startswith("content-disposition"):
                    disposition_header = header_line
                elif lower_line.startswith("content-type"):
                    content_type_header = header_line
            if not disposition_header:
                continue
            name = ""
            filename: Optional[str] = None
            parts = disposition_header.split(";")
            for part in parts:
                part = part.strip()
                if part.startswith("name="):
                    name = part.split("=", 1)[1].strip('"')
                elif part.startswith("filename="):
                    filename = part.split("=", 1)[1].strip('"')
            if not name:
                continue
            if filename is not None and filename != "":
                content_type_value = "application/octet-stream"
                if content_type_header:
                    _, _, ctype_value = content_type_header.partition(":")
                    content_type_value = ctype_value.strip() or content_type_value
                file_values[name] = {
                    "filename": filename,
                    "content_type": content_type_value,
                    "content": content_bytes,
                }
            else:
                form_values[name] = content_bytes.decode("utf-8", errors="replace")
        self._form_params_cache = form_values
        self._files_cache = file_values


class HTTPResponse:
    def __init__(self, status_code: int, reason: str, body: bytes, headers: Optional[Dict[str, str]] = None) -> None:
        self.status_code = status_code
        self.reason = reason
        self.body = body
        self.headers = headers or {}

    def to_bytes(self) -> bytes:
        response_line = f"HTTP/1.1 {self.status_code} {self.reason}\r\n"
        header_lines = ""
        for name, value in self.headers.items():
            header_lines += f"{name}: {value}\r\n"
        return (response_line + header_lines + "\r\n").encode("utf-8") + self.body

    def set_header(self, name: str, value: str) -> None:
        self.headers[name] = value

    def set_cookie(self, name: str, value: str, path: str = "/", max_age: Optional[int] = None) -> None:
        cookie_value = f"{name}={value}; Path={path}; HttpOnly"
        if max_age is not None:
            cookie_value += f"; Max-Age={max_age}"
        existing = self.headers.get("Set-Cookie")
        if existing:
            cookie_value = f"{existing}\r\nSet-Cookie: {cookie_value}"
            self.headers["Set-Cookie"] = cookie_value
        else:
            self.headers["Set-Cookie"] = cookie_value

