"""Local-only guard shared by every web app here (main app and labeler).

A web page you visit must not spend your API key or rewrite your labels. The Host header must be a
local name (blocks DNS rebinding), and a state-changing request that carries an Origin must come from
this same address (blocks cross-site posts). To serve a real hostname, set BLINDSPOT_ALLOWED_HOSTS
to a comma-separated list. A public server must stay in mock mode (see cli serve).
"""
from __future__ import annotations

import os
from urllib.parse import urlsplit

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

LOOPBACK = {"127.0.0.1", "localhost", "::1"}


def allowed_hosts() -> set[str]:
    extra = {h.strip().lower() for h in os.environ.get("BLINDSPOT_ALLOWED_HOSTS", "").split(",") if h.strip()}
    return LOOPBACK | extra


def install_local_guard(app: FastAPI) -> None:
    @app.middleware("http")
    async def local_requests_only(request: Request, call_next):
        host = request.headers.get("host", "")
        try:
            parsed = urlsplit("//" + host)
            valid_host = (bool(host) and not any(ch.isspace() for ch in host)
                          and parsed.netloc == host and not parsed.username and not parsed.password
                          and not parsed.path and not parsed.query and not parsed.fragment
                          and (parsed.port is None or 0 < parsed.port <= 65535)
                          and (parsed.hostname or "").lower() in allowed_hosts())
        except ValueError:
            valid_host = False
        if not valid_host:
            return JSONResponse({"detail": "this server does not answer that host name"}, status_code=403)
        origin = request.headers.get("origin")
        if request.method not in {"GET", "HEAD", "OPTIONS"} and origin:
            try:
                parsed_origin = urlsplit(origin)
                same_origin = (parsed_origin.scheme == request.url.scheme
                               and parsed_origin.netloc.lower() == host.lower()
                               and not parsed_origin.path and not parsed_origin.query
                               and not parsed_origin.fragment)
            except ValueError:
                same_origin = False
            if not same_origin:
                return JSONResponse({"detail": "cross-site request refused"}, status_code=403)
        return await call_next(request)
