"""Performance middleware for the NodeLens API."""

import hashlib

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class ETagMiddleware(BaseHTTPMiddleware):
    """ETag / conditional-GET support for polling efficiency.

    The frontend polls every 10 s.  For endpoints whose data hasn't
    changed (device list, dashboard config, plugin list, …) this avoids
    re-serialising and re-transferring the full body — the client gets a
    304 Not Modified instead.
    """

    async def dispatch(self, request: Request, call_next):
        if request.method not in ("GET", "HEAD"):
            return await call_next(request)

        response: Response = await call_next(request)

        if response.status_code != 200:
            return response

        body = b""
        async for chunk in response.body_iterator:  # type: ignore[union-attr]
            body += chunk if isinstance(chunk, bytes) else chunk.encode()

        etag = '"' + hashlib.md5(body).hexdigest() + '"'
        response.headers["ETag"] = etag
        response.headers.setdefault(
            "Cache-Control", "private, max-age=0, must-revalidate"
        )

        if_none_match = request.headers.get("if-none-match")
        if if_none_match and if_none_match == etag:
            return Response(status_code=304, headers={"ETag": etag})

        return Response(
            content=body,
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type=response.media_type,
        )
