from typing import Callable, Dict, Any, Optional, List


class RouteMatch:
    def __init__(self, handler: Callable[..., "HTTPResponse"], params: Dict[str, Any]) -> None:
        self.handler = handler
        self.params = params


class Router:
    def __init__(self) -> None:
        self.routes: List[Dict[str, Any]] = []

    def add_route(self, path: str, method: str, handler: Callable[..., "HTTPResponse"]) -> None:
        entry = {
            "path": path,
            "method": method.upper(),
            "handler": handler,
            "segments": self._split_path(path),
        }
        self.routes.append(entry)

    def resolve(self, path: str, method: str) -> Optional[RouteMatch]:
        request_segments = self._split_path(path)
        for route in self.routes:
            if route["method"] != method.upper():
                continue
            params: Dict[str, Any] = {}
            if self._match_segments(route["segments"], request_segments, params):
                return RouteMatch(route["handler"], params)
        return None

    def _split_path(self, path: str) -> List[str]:
        if path == "/":
            return []
        return [segment for segment in path.strip("/").split("/") if segment]

    def _match_segments(self, route_segments: List[str], request_segments: List[str], params: Dict[str, Any]) -> bool:
        if len(route_segments) != len(request_segments):
            return False
        for route_segment, request_segment in zip(route_segments, request_segments):
            if route_segment.startswith("<") and route_segment.endswith(">"):
                key = route_segment[1:-1]
                params[key] = request_segment
            elif route_segment == request_segment:
                continue
            else:
                return False
        return True

