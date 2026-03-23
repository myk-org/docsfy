from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from simple_logger.logger import get_logger
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse, RedirectResponse, Response

from docsfy.api.admin import router as admin_router
from docsfy.api.auth import router as auth_router
from docsfy.api.websocket import router as ws_router
from docsfy.api.projects import (
    _check_ownership,
    _generating,
    _resolve_latest_accessible_variant,
    _resolve_project,
    _validate_project_name,
    router as projects_router,
)
from docsfy.config import get_settings
from docsfy.models import DEFAULT_BRANCH
from docsfy.storage import (
    cleanup_expired_sessions,
    get_latest_variant,
    get_project_site_dir,
    get_session,
    get_user_by_key,
    get_user_by_username,
    init_db,
)

logger = get_logger(name=__name__)

# Re-export so existing tests can do ``from docsfy.main import _generating``
__all__ = ["app", "_generating"]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    if not settings.admin_key:
        logger.error("ADMIN_KEY environment variable is required")
        raise SystemExit(1)

    if len(settings.admin_key) < 16:
        logger.error("ADMIN_KEY must be at least 16 characters long")
        raise SystemExit(1)

    _generating.clear()
    await init_db(data_dir=settings.data_dir)
    await cleanup_expired_sessions()
    yield


app = FastAPI(
    title="docsfy",
    description="AI-powered documentation generator",
    version="0.1.0",
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)
app.include_router(admin_router)
app.include_router(auth_router)
app.include_router(projects_router)
app.include_router(ws_router)


class AuthMiddleware(BaseHTTPMiddleware):
    """Authenticate every request via Bearer token or session cookie."""

    # Paths that do not require authentication
    _PUBLIC_PATHS = frozenset(
        {
            "/api/auth/login",
            "/api/auth/login/",
            "/api/auth/logout",
            "/api/auth/logout/",
            "/api/ws",
            "/health",
            "/login",
            "/login/",
        }
    )

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        path = request.url.path

        # Public paths -- no auth required
        if path in self._PUBLIC_PATHS:
            logger.debug(f"Auth middleware: public path '{path}', skipping auth")
            return await call_next(request)

        # API and docs paths require authentication
        requires_auth = path.startswith(("/api/", "/docs/"))

        if not requires_auth:
            # SPA routes (/, /admin, /status/*, /assets/*, etc.) -- pass through
            # without auth check; the SPA catch-all serves index.html and React
            # handles auth routing client-side.
            logger.debug(f"Auth middleware: SPA route '{path}', skipping auth")
            return await call_next(request)

        settings = get_settings()
        user = None
        is_admin = False
        username = ""

        # 1. Check Authorization header (API clients)
        auth_header = request.headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            logger.debug(f"Auth middleware: Bearer token auth for '{path}'")
            token = auth_header[7:]
            if token == settings.admin_key:
                is_admin = True
                username = "admin"
            else:
                user = await get_user_by_key(token)

        # 2. Check session cookie (browser) -- opaque session token
        if not user and not is_admin:
            session_token = request.cookies.get("docsfy_session")
            if session_token:
                logger.debug(f"Auth middleware: session cookie auth for '{path}'")
                session = await get_session(session_token)
                if session:
                    is_admin = bool(session["is_admin"])
                    username = str(session["username"])
                    # For DB users (not ADMIN_KEY admin), verify user still exists
                    if username != "admin":
                        user = await get_user_by_username(username)
                        if not user:
                            # User was deleted since session was created
                            if path.startswith("/docs/"):
                                accept = request.headers.get("accept", "")
                                if "text/html" in accept:
                                    return RedirectResponse(
                                        url="/login", status_code=302
                                    )
                            return JSONResponse(
                                status_code=401, content={"detail": "Unauthorized"}
                            )

        if not user and not is_admin:
            # Not authenticated -- redirect browsers viewing /docs/* to login
            if path.startswith("/docs/"):
                accept = request.headers.get("accept", "")
                if "text/html" in accept:
                    return RedirectResponse(url="/login", status_code=302)
            return JSONResponse(status_code=401, content={"detail": "Unauthorized"})

        # Determine the role
        if is_admin:
            role = "admin"
            if not username:
                username = "admin"
        else:
            if user is None:
                return JSONResponse(status_code=401, content={"detail": "Unauthorized"})
            role = str(user.get("role", "user"))
            username = str(user["username"])
            # DB user with admin role gets admin privileges
            if role == "admin":
                is_admin = True

        # Store user info in request state
        request.state.user = user
        request.state.is_admin = is_admin
        request.state.role = role
        request.state.username = username
        logger.debug(
            f"Auth middleware: authenticated '{username}' role='{role}' for '{path}'"
        )

        return await call_next(request)


# TODO: Add rate limiting for login attempts.  Rate limiting is typically
# done at the reverse proxy level (nginx, Caddy, etc.) but an in-app
# fallback (e.g. slowapi) could be added for defense-in-depth.
app.add_middleware(AuthMiddleware)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


# IMPORTANT: variant-specific route MUST be defined BEFORE the generic route
# so FastAPI matches it first.
@app.get("/docs/{project}/{branch}/{provider}/{model}/{path:path}")
async def serve_variant_docs(
    request: Request,
    project: str,
    branch: str,
    provider: str,
    model: str,
    path: str = "index.html",
) -> FileResponse:
    if not path or path == "/":
        path = "index.html"
    logger.debug(
        f"Serving variant doc: project='{project}', branch='{branch}', provider='{provider}', model='{model}', path='{path}'"
    )
    project = _validate_project_name(project)
    proj = await _resolve_project(
        request,
        project,
        ai_provider=provider,
        ai_model=model,
        branch=branch,
    )

    proj_owner = str(proj.get("owner", ""))
    site_dir = get_project_site_dir(project, provider, model, proj_owner, branch=branch)
    file_path = site_dir / path
    try:
        file_path.resolve().relative_to(site_dir.resolve())
    except ValueError as exc:
        raise HTTPException(status_code=403, detail="Access denied") from exc
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path)


@app.get("/docs/{project}/{path:path}")
async def serve_docs(
    request: Request, project: str, path: str = "index.html"
) -> FileResponse:
    """Serve the most recently generated variant."""
    if not path or path == "/":
        path = "index.html"
    project = _validate_project_name(project)
    if request.state.is_admin:
        latest = await get_latest_variant(project)
    else:
        latest = await _resolve_latest_accessible_variant(
            request.state.username, project
        )
    if not latest:
        raise HTTPException(status_code=404, detail="No docs available")
    await _check_ownership(request, project, latest)
    latest_owner = str(latest.get("owner", ""))
    latest_branch = str(latest.get("branch", DEFAULT_BRANCH))
    site_dir = get_project_site_dir(
        project,
        str(latest["ai_provider"]),
        str(latest["ai_model"]),
        latest_owner,
        branch=latest_branch,
    )
    file_path = site_dir / path
    try:
        file_path.resolve().relative_to(site_dir.resolve())
    except ValueError as exc:
        raise HTTPException(status_code=403, detail="Access denied") from exc
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path)


# ---------------------------------------------------------------------------
# Frontend SPA serving
# ---------------------------------------------------------------------------
# Serve pre-built frontend static assets and a catch-all for client-side
# routing.  The assets mount and catch-all MUST come after all API routers
# and /docs/* routes so they never shadow backend endpoints.
# ---------------------------------------------------------------------------
_frontend_dist = Path(__file__).parent.parent.parent / "frontend" / "dist"

# Mount static assets if they exist (production build)
_assets_dir = _frontend_dist / "assets"
if _assets_dir.exists():
    app.mount(
        "/assets", StaticFiles(directory=str(_assets_dir)), name="frontend-assets"
    )


@app.get("/{path:path}")
async def spa_catch_all(path: str) -> FileResponse:
    """Serve the SPA index.html for all non-API, non-docs routes."""
    if path.startswith(("api/", "docs/")) or path in ("api", "docs"):
        raise HTTPException(status_code=404, detail="Not found")
    logger.debug(f"SPA catch-all serving index.html for path='{path}'")
    index = _frontend_dist / "index.html"
    if index.exists():
        return FileResponse(str(index))
    raise HTTPException(
        status_code=404,
        detail="Frontend not built. Run: cd frontend && npm run build",
    )


def run() -> None:
    import uvicorn

    reload = os.getenv("DEBUG", "").lower() == "true"
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("docsfy.main:app", host=host, port=port, reload=reload)
