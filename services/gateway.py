"""Authenticated dispatcher to independent organization databases and app state."""

import hashlib
import os
import time
from collections import defaultdict, deque
from contextlib import AsyncExitStack, asynccontextmanager

from fastapi import FastAPI
from starlette.concurrency import run_in_threadpool
from starlette.responses import JSONResponse

from services.api.main import create_app
from services.identity import IdentityVerifier
from services.organizations import load_registry


class Dispatcher:
    def __init__(self, registry, applications):
        self.registry = registry
        self.applications = applications
        self.credentials = {
            hashlib.sha256(c.token.encode()).digest(): {
                "subject": c.subject,
                "organization": c.organization,
                "roles": c.roles,
            }
            for c in registry.credentials
        }
        self.requests = defaultdict(deque)
        self.identity = IdentityVerifier(registry) if registry.identity_provider else None

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return
        headers = scope.get("headers", [])
        auth = [value for key, value in headers if key.lower() == b"authorization"]
        principal = None
        if len(auth) == 1 and len(auth[0]) <= 8199 and auth[0].startswith(b"Bearer "):
            principal = self.credentials.get(hashlib.sha256(auth[0][7:]).digest())
            if principal is None and self.identity:
                principal = await run_in_threadpool(self.identity.verify, auth[0][7:])
        if principal is None:
            await JSONResponse({"detail": "Valid organization credentials required"}, 401)(
                scope, receive, send
            )
            return
        key = (principal["organization"], principal["subject"])
        now = time.monotonic()
        window = self.requests[key]
        while window and window[0] <= now - 60:
            window.popleft()
        if len(window) >= self.registry.request_limit:
            await JSONResponse(
                {"detail": "Request limit exceeded"}, 429, headers={"Retry-After": "60"}
            )(scope, receive, send)
            return
        window.append(now)
        path = scope["path"]
        mutating = scope["method"] not in ("GET", "HEAD", "OPTIONS") or path.endswith("/export")
        if mutating and not set(principal["roles"]).intersection({"analyst", "admin"}):
            await JSONResponse({"detail": "Analyst role required"}, 403)(scope, receive, send)
            return
        if path == "/v1/session":
            organization = next(
                o for o in self.registry.organizations if o.id == principal["organization"]
            )
            await JSONResponse({**principal, "organization_name": organization.name})(
                scope, receive, send
            )
            return
        length = next((v for k, v in headers if k.lower() == b"content-length"), b"0")
        try:
            if int(length) < 0:
                raise ValueError()
            oversized = int(length) > self.registry.body_limit
        except ValueError:
            await JSONResponse({"detail": "Invalid content length"}, 400)(scope, receive, send)
            return
        if oversized:
            await JSONResponse({"detail": "Request body too large"}, 413)(scope, receive, send)
            return
        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            body.extend(message.get("body", b""))
            if len(body) > self.registry.body_limit:
                await JSONResponse({"detail": "Request body too large"}, 413)(scope, receive, send)
                return
            if not message.get("more_body", False):
                break
        delivered = False

        async def replay():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()

        async def safe_send(message):
            if message["type"] == "http.response.start":
                message["headers"] = [
                    *message.get("headers", []),
                    (b"x-content-type-options", b"nosniff"),
                    (b"x-frame-options", b"DENY"),
                ]
            await send(message)

        scope = {**scope, "state": {**scope.get("state", {}), "principal": principal}}
        await self.applications[principal["organization"]](scope, replay, safe_send)


def create_gateway(registry):
    applications = {o.id: create_app(registry.settings_for(o)) for o in registry.organizations}

    @asynccontextmanager
    async def lifespan(app):
        async with AsyncExitStack() as stack:
            for child in applications.values():
                await stack.enter_async_context(child.router.lifespan_context(child))
            yield

    gateway = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    gateway.state.organizations = applications

    @gateway.get("/health")
    def health():
        return {"status": "alive"}

    @gateway.get("/ready")
    def ready():
        from sqlalchemy import text

        try:
            for child in applications.values():
                if child.state.manifest is None:
                    return JSONResponse({"status": "not ready"}, 503)
                with child.state.sessions() as session:
                    session.execute(text("SELECT 1"))
        except Exception:
            return JSONResponse({"status": "not ready"}, 503)
        return {"status": "ready"}

    gateway.mount("/", Dispatcher(registry, applications))
    return gateway


def factory():
    path = os.environ.get("FRAUDGRAPH_ORGANIZATIONS_FILE")
    if not path:
        raise ValueError("FRAUDGRAPH_ORGANIZATIONS_FILE is required")
    return create_gateway(load_registry(path))
