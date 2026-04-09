"""Performance middleware for the NodeLens API."""

import zlib


class ETagMiddleware:
    """Pure ASGI ETag / conditional-GET middleware.

    The frontend polls every 10 s.  For endpoints whose data hasn't
    changed (device list, dashboard config, plugin list, …) this avoids
    re-transferring the full body — the client gets a 304 Not Modified.

    Uses raw ASGI instead of BaseHTTPMiddleware to avoid per-request
    task overhead and streaming issues.  CRC32 replaces MD5 — faster
    for the small JSON payloads typical of this API.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope.get("method", "") not in ("GET", "HEAD"):
            await self.app(scope, receive, send)
            return

        status_code = 200
        response_headers: list[tuple[bytes, bytes]] = []
        body_parts: list[bytes] = []

        async def capture_send(message):
            nonlocal status_code, response_headers
            if message["type"] == "http.response.start":
                status_code = message["status"]
                response_headers = list(message.get("headers", []))
            elif message["type"] == "http.response.body":
                body_parts.append(message.get("body", b""))

        await self.app(scope, receive, capture_send)

        if status_code != 200:
            await send({"type": "http.response.start", "status": status_code, "headers": response_headers})
            await send({"type": "http.response.body", "body": b"".join(body_parts)})
            return

        body = b"".join(body_parts)
        etag = f'"{zlib.crc32(body):08x}"'

        # Check If-None-Match
        if_none_match = ""
        for name, value in scope.get("headers", []):
            if name == b"if-none-match":
                if_none_match = value.decode()
                break

        if if_none_match == etag:
            await send({
                "type": "http.response.start",
                "status": 304,
                "headers": [(b"etag", etag.encode())],
            })
            await send({"type": "http.response.body", "body": b""})
            return

        response_headers.append((b"etag", etag.encode()))
        header_names = {h[0].lower() for h in response_headers}
        if b"cache-control" not in header_names:
            response_headers.append((b"cache-control", b"private, max-age=0, must-revalidate"))

        await send({"type": "http.response.start", "status": status_code, "headers": response_headers})
        await send({"type": "http.response.body", "body": body})
