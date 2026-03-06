from __future__ import annotations

import asyncio
import json
import os
import re as _re
import shutil
import tarfile
import tempfile
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from jinja2 import Environment, FileSystemLoader, select_autoescape
from simple_logger.logger import get_logger
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse, RedirectResponse, Response

from docsfy.ai_client import check_ai_cli_available
from docsfy.config import get_settings
from docsfy.generator import generate_all_pages, run_incremental_planner, run_planner
from docsfy.models import GenerateRequest
from docsfy.repository import clone_repo, get_changed_files, get_local_repo_info
from docsfy.renderer import render_site
from docsfy.storage import (
    SESSION_TTL_SECONDS,
    cleanup_expired_sessions,
    create_session,
    create_user,
    delete_project,
    delete_session,
    delete_user,
    get_known_models,
    get_latest_variant,
    get_project,
    get_project_access,
    get_project_cache_dir,
    get_project_dir,
    get_project_site_dir,
    get_session,
    get_user_accessible_projects,
    get_user_by_key,
    get_user_by_username,
    grant_project_access,
    init_db,
    list_projects,
    list_users,
    list_variants,
    revoke_project_access,
    rotate_user_key,
    save_project,
    update_project_status,
)

logger = get_logger(name=__name__)

_generating: dict[str, asyncio.Task[None]] = {}
# Fix 6: asyncio.Lock to prevent race between checking and adding to _generating
_gen_lock = asyncio.Lock()

# Fix 10: Singleton Jinja2 environment to avoid repeated FileSystemLoader creation
_jinja_env = Environment(
    loader=FileSystemLoader(str(Path(__file__).parent / "templates")),
    autoescape=select_autoescape(["html"]),
)


def _validate_project_name(name: str) -> str:
    """Validate project name to prevent path traversal."""
    if not _re.match(r"^[a-zA-Z0-9][a-zA-Z0-9._-]*$", name):
        raise HTTPException(status_code=400, detail=f"Invalid project name: '{name}'")
    return name


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
)


class AuthMiddleware(BaseHTTPMiddleware):
    """Authenticate every request via Bearer token or session cookie."""

    # Paths that do not require authentication
    _PUBLIC_PATHS = frozenset({"/login", "/login/", "/health"})

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        if request.url.path in self._PUBLIC_PATHS:
            return await call_next(request)

        settings = get_settings()
        user = None
        is_admin = False
        username = ""

        # 1. Check Authorization header (API clients)
        auth_header = request.headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
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
                session = await get_session(session_token)
                if session:
                    is_admin = bool(session["is_admin"])
                    username = str(session["username"])
                    # Fix 8: For DB users (not ADMIN_KEY admin), verify user still exists
                    if username != "admin":
                        user = await get_user_by_username(username)
                        if not user:
                            # User was deleted since session was created
                            if request.url.path.startswith("/api/"):
                                return JSONResponse(
                                    status_code=401, content={"detail": "Unauthorized"}
                                )
                            return RedirectResponse(url="/login", status_code=302)

        if not user and not is_admin:
            # Not authenticated
            if request.url.path.startswith("/api/"):
                return JSONResponse(status_code=401, content={"detail": "Unauthorized"})
            return RedirectResponse(url="/login", status_code=302)

        # Determine the role
        if is_admin:
            role = "admin"
            if not username:
                username = "admin"
        else:
            assert user is not None  # guaranteed by the guard above
            role = str(user.get("role", "user"))
            username = str(user["username"])
            # Fix 6: DB user with admin role gets admin privileges
            if role == "admin":
                is_admin = True

        # Store user info in request state
        request.state.user = user
        request.state.is_admin = is_admin
        request.state.role = role
        request.state.username = username

        return await call_next(request)


# TODO: Add rate limiting for login attempts.  Rate limiting is typically
# done at the reverse proxy level (nginx, Caddy, etc.) but an in-app
# fallback (e.g. slowapi) could be added for defense-in-depth.
app.add_middleware(AuthMiddleware)


def _require_write_access(request: Request) -> None:
    """Raise 403 if user is a viewer (read-only)."""
    if request.state.role not in ("admin", "user"):
        raise HTTPException(
            status_code=403,
            detail="Write access required.",
        )


async def _check_ownership(
    request: Request, project_name: str, project: dict[str, Any]
) -> None:
    """Raise 404 if the requesting user does not own the project (unless admin)."""
    if request.state.is_admin:
        return
    project_owner = str(project.get("owner", ""))
    if project_owner == request.state.username:
        return
    # Check if user has been granted access (scoped by project_owner)
    access = await get_project_access(project_name, project_owner=project_owner)
    if request.state.username in access:
        return
    raise HTTPException(status_code=404, detail="Not found")


@app.get("/login", response_class=HTMLResponse)
async def login_page() -> HTMLResponse:
    """Render the login page."""
    template = _jinja_env.get_template("login.html")
    html = template.render(error=None)
    return HTMLResponse(content=html)


@app.post("/login", response_model=None)
async def login(request: Request) -> RedirectResponse | HTMLResponse:
    """Authenticate with username + API key and set a session cookie."""
    form = await request.form()
    username = str(form.get("username", ""))
    api_key = str(form.get("api_key", ""))
    settings = get_settings()

    is_admin = False
    authenticated = False

    # Check admin -- username must be "admin" and key must match
    if username == "admin" and api_key == settings.admin_key:
        is_admin = True
        authenticated = True
    else:
        # Check user key -- verify username matches the key's owner
        user = await get_user_by_key(api_key)
        if user and user["username"] == username:
            authenticated = True
            is_admin = user.get("role") == "admin"

    if authenticated:
        session_token = await create_session(username, is_admin=is_admin)
        response = RedirectResponse(url="/", status_code=302)
        response.set_cookie(
            "docsfy_session",
            session_token,
            httponly=True,
            samesite="strict",
            secure=settings.secure_cookies,
            max_age=SESSION_TTL_SECONDS,
        )
        return response

    # Fix 13: Sanitize username in audit log to prevent log injection
    safe_username = username.replace("\n", "").replace("\r", "")[:100]
    logger.info(f"[AUDIT] Failed login attempt for username '{safe_username}'")

    # Invalid credentials -- show login page with error
    template = _jinja_env.get_template("login.html")
    html = template.render(error="Invalid username or password")
    return HTMLResponse(content=html, status_code=401)


@app.get("/logout")
async def logout(request: Request) -> RedirectResponse:
    """Clear the session cookie, delete session from DB, and redirect to login."""
    session_token = request.cookies.get("docsfy_session")
    if session_token:
        await delete_session(session_token)
    settings = get_settings()
    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie(
        "docsfy_session",
        httponly=True,
        samesite="strict",
        secure=settings.secure_cookies,
    )
    return response


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request) -> HTMLResponse:
    settings = get_settings()
    username = request.state.username
    is_admin = request.state.is_admin

    if is_admin:
        projects = await list_projects()  # admin sees all
    else:
        accessible = await get_user_accessible_projects(username)
        projects = await list_projects(owner=username, accessible=accessible)

    known_models = await get_known_models()

    # Group by repo name
    grouped: dict[str, list[dict[str, Any]]] = {}
    for p in projects:
        name = str(p["name"])
        if name not in grouped:
            grouped[name] = []
        grouped[name].append(p)

    template = _jinja_env.get_template("dashboard.html")
    html = template.render(
        grouped_projects=grouped,
        projects=projects,  # keep for backward compat
        default_provider=settings.ai_provider,
        default_model=settings.ai_model,
        known_models=known_models,
        role=request.state.role,
        username=request.state.username,
    )
    return HTMLResponse(content=html)


@app.get("/status/{name}/{provider}/{model}", response_class=HTMLResponse)
async def project_status_page(
    request: Request, name: str, provider: str, model: str
) -> HTMLResponse:
    name = _validate_project_name(name)
    project = await get_project(name, ai_provider=provider, ai_model=model)
    if not project:
        raise HTTPException(status_code=404, detail="Variant not found")
    await _check_ownership(request, name, project)

    # Parse plan_json string into a dict for template consumption
    plan_json = None
    total_pages = 0
    if project.get("plan_json"):
        try:
            plan_json = json.loads(str(project["plan_json"]))
            for group in plan_json.get("navigation", []):
                total_pages += len(group.get("pages", []))
        except (json.JSONDecodeError, TypeError):
            plan_json = None

    settings = get_settings()
    known_models = await get_known_models()

    template = _jinja_env.get_template("status.html")
    html = template.render(
        project=project,
        plan_json=plan_json,
        total_pages=total_pages,
        known_models=known_models,
        default_provider=settings.ai_provider,
        default_model=settings.ai_model,
    )
    return HTMLResponse(content=html)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/status")
async def status(request: Request) -> dict[str, Any]:
    if request.state.is_admin:
        projects = await list_projects()
    else:
        accessible = await get_user_accessible_projects(request.state.username)
        projects = await list_projects(
            owner=request.state.username, accessible=accessible
        )
    known_models = await get_known_models()
    return {"projects": projects, "known_models": known_models}


@app.post("/api/generate", status_code=202)
async def generate(request: Request, gen_request: GenerateRequest) -> dict[str, str]:
    _require_write_access(request)
    # Fix 9: Local repo path access requires admin privileges
    if gen_request.repo_path and not request.state.is_admin:
        raise HTTPException(
            status_code=403,
            detail="Local repo path access requires admin privileges",
        )

    # Validate repo_path existence after admin check to avoid leaking filesystem info
    if gen_request.repo_path:
        repo_p = Path(gen_request.repo_path)
        if not repo_p.exists():
            raise HTTPException(
                status_code=400,
                detail=f"Repository path does not exist: '{gen_request.repo_path}'",
            )
        if not (repo_p / ".git").exists():
            raise HTTPException(
                status_code=400,
                detail=f"Not a git repository (no .git directory): '{gen_request.repo_path}'",
            )

    # Fix 10 (SSRF): Reject internal/private network URLs.
    # This is an admin-provisioned service so the risk is low, but we add
    # basic validation to prevent accidental SSRF against internal hosts.
    # Advanced SSRF protection (DNS rebinding, etc.) should be handled at
    # the network/firewall level.
    if gen_request.repo_url:
        _reject_private_url(gen_request.repo_url)

    settings = get_settings()
    ai_provider = gen_request.ai_provider or settings.ai_provider
    ai_model = gen_request.ai_model or settings.ai_model
    project_name = gen_request.project_name
    owner = request.state.username

    if ai_provider not in ("claude", "gemini", "cursor"):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid AI provider: '{ai_provider}'. Must be claude, gemini, or cursor.",
        )
    if not ai_model:
        raise HTTPException(status_code=400, detail="AI model must be specified.")

    # Fix 6: Use lock to prevent race condition between check and add
    gen_key = f"{owner}/{project_name}/{ai_provider}/{ai_model}"
    async with _gen_lock:
        if gen_key in _generating:
            raise HTTPException(
                status_code=409,
                detail=f"Variant '{project_name}/{ai_provider}/{ai_model}' is already being generated",
            )

        await save_project(
            name=project_name,
            repo_url=gen_request.repo_url or gen_request.repo_path or "",
            status="generating",
            ai_provider=ai_provider,
            ai_model=ai_model,
            owner=owner,
        )

        try:
            task = asyncio.create_task(
                _run_generation(
                    repo_url=gen_request.repo_url,
                    repo_path=gen_request.repo_path,
                    project_name=project_name,
                    ai_provider=ai_provider,
                    ai_model=ai_model,
                    ai_cli_timeout=gen_request.ai_cli_timeout
                    or settings.ai_cli_timeout,
                    force=gen_request.force,
                    owner=owner,
                )
            )
            _generating[gen_key] = task
        except Exception:
            _generating.pop(gen_key, None)
            raise

    return {"project": project_name, "status": "generating"}


def _reject_private_url(url: str) -> None:
    """Reject URLs targeting private/internal IP ranges (SSRF mitigation).

    This provides basic protection against SSRF. More comprehensive protection
    (DNS rebinding, etc.) should be handled at the network/firewall level.
    """
    import ipaddress
    from urllib.parse import urlparse

    try:
        parsed = urlparse(url)
        hostname = parsed.hostname
        # Handle SSH format: git@hostname:org/repo.git
        if not hostname and url.startswith("git@"):
            try:
                hostname = url.split("@")[1].split(":")[0]
            except (IndexError, ValueError):
                pass
        if not hostname:
            return
        # Check for localhost
        if hostname in ("localhost", "127.0.0.1", "::1", "0.0.0.0"):
            raise HTTPException(
                status_code=400,
                detail="Repository URL must not target localhost or private networks",
            )
        # Check if hostname is an IP address in private range
        try:
            addr = ipaddress.ip_address(hostname)
            if addr.is_private or addr.is_loopback or addr.is_link_local:
                raise HTTPException(
                    status_code=400,
                    detail="Repository URL must not target localhost or private networks",
                )
        except ValueError:
            pass  # hostname is a DNS name, not an IP - allowed
    except HTTPException:
        raise
    except Exception:
        pass  # URL parsing errors are handled by Pydantic validation


@app.post("/api/projects/{name}/abort")
async def abort_generation(request: Request, name: str) -> dict[str, str]:
    """Abort generation for any variant of the given project name.

    Kept for backward compatibility. Finds the first active generation
    matching the project name.
    """
    _require_write_access(request)
    name = _validate_project_name(name)
    # Find any active generation key that starts with this project name
    matching_key = None
    for key in _generating:
        # gen_key format: "owner/name/provider/model"
        parts = key.split("/", 3)
        if len(parts) == 4 and parts[1] == name:
            matching_key = key
            break
    task = _generating.get(matching_key) if matching_key else None
    if not task or not matching_key:
        raise HTTPException(
            status_code=404, detail=f"No active generation for '{name}'"
        )

    # Extract owner/provider/model from the key (format: "owner/name/provider/model")
    parts = matching_key.split("/", 3)
    if len(parts) != 4:
        raise HTTPException(status_code=500, detail="Invalid generation key format")
    key_owner, _, ai_provider, ai_model = parts

    # Check ownership before allowing abort
    project = await get_project(
        name, ai_provider=ai_provider, ai_model=ai_model, owner=key_owner
    )
    if project:
        await _check_ownership(request, name, project)

    task.cancel()
    try:
        await asyncio.wait_for(task, timeout=5.0)
    except asyncio.CancelledError:
        pass  # expected cancellation acknowledgment
    except asyncio.TimeoutError as exc:
        logger.warning(f"[{name}] Abort requested but cancellation still in progress")
        raise HTTPException(
            status_code=409,
            detail=f"Abort still in progress for '{name}'. Please retry shortly.",
        ) from exc
    except Exception as exc:
        logger.exception(f"[{name}] Abort failed")
        raise HTTPException(
            status_code=500, detail=f"Failed to abort '{name}'"
        ) from exc

    await update_project_status(
        name,
        ai_provider,
        ai_model,
        status="aborted",
        owner=key_owner,
        error_message="Generation aborted by user",
        current_stage=None,
    )
    _generating.pop(matching_key, None)

    return {"aborted": name}


@app.post("/api/projects/{name}/{provider}/{model}/abort")
async def abort_variant(
    request: Request, name: str, provider: str, model: str
) -> dict[str, str]:
    _require_write_access(request)
    name = _validate_project_name(name)
    owner = request.state.username
    gen_key = f"{owner}/{name}/{provider}/{model}"
    task = _generating.get(gen_key)
    if not task:
        # Also check if an admin is aborting someone else's generation
        if request.state.is_admin:
            for key in _generating:
                parts = key.split("/", 3)
                if (
                    len(parts) == 4
                    and parts[1] == name
                    and parts[2] == provider
                    and parts[3] == model
                ):
                    gen_key = key
                    task = _generating[key]
                    break
        if not task:
            raise HTTPException(
                status_code=404,
                detail="No active generation for this variant",
            )

    # Check ownership before allowing abort
    key_parts = gen_key.split("/", 3)
    key_owner = key_parts[0] if len(key_parts) == 4 else owner
    project = await get_project(
        name, ai_provider=provider, ai_model=model, owner=key_owner
    )
    if project:
        await _check_ownership(request, name, project)

    task.cancel()
    try:
        await asyncio.wait_for(task, timeout=5.0)
    except asyncio.CancelledError:
        pass
    except asyncio.TimeoutError as exc:
        logger.warning(
            f"[{gen_key}] Abort requested but cancellation still in progress"
        )
        raise HTTPException(
            status_code=409,
            detail=f"Abort still in progress for '{gen_key}'. Please retry shortly.",
        ) from exc
    except Exception as exc:
        logger.exception(f"[{gen_key}] Abort failed")
        raise HTTPException(
            status_code=500, detail=f"Failed to abort '{gen_key}'"
        ) from exc

    await update_project_status(
        name,
        provider,
        model,
        status="aborted",
        owner=key_owner,
        error_message="Generation aborted by user",
        current_stage=None,
    )
    _generating.pop(gen_key, None)

    return {"aborted": f"{name}/{provider}/{model}"}


async def _run_generation(
    repo_url: str | None,
    repo_path: str | None,
    project_name: str,
    ai_provider: str,
    ai_model: str,
    ai_cli_timeout: int,
    force: bool = False,
    owner: str = "",
) -> None:
    gen_key = f"{owner}/{project_name}/{ai_provider}/{ai_model}"
    try:
        cli_flags = ["--trust"] if ai_provider == "cursor" else None
        available, msg = await check_ai_cli_available(
            ai_provider, ai_model, cli_flags=cli_flags
        )
        if not available:
            await update_project_status(
                project_name,
                ai_provider,
                ai_model,
                status="error",
                owner=owner,
                error_message=msg,
            )
            return

        await update_project_status(
            project_name,
            ai_provider,
            ai_model,
            status="generating",
            owner=owner,
            current_stage="cloning",
        )

        if repo_path:
            # Local repository - use directly, no cloning needed
            local_path, commit_sha = get_local_repo_info(Path(repo_path))
            await _generate_from_path(
                local_path,
                commit_sha,
                repo_url or repo_path,
                project_name,
                ai_provider,
                ai_model,
                ai_cli_timeout,
                force,
                owner,
            )
        else:
            # Remote repository - clone to temp dir
            if repo_url is None:
                msg = "repo_url must be provided for remote repositories"
                raise ValueError(msg)
            with tempfile.TemporaryDirectory() as tmp_dir:
                repo_dir, commit_sha = await asyncio.to_thread(
                    clone_repo, repo_url, Path(tmp_dir)
                )
                await _generate_from_path(
                    repo_dir,
                    commit_sha,
                    repo_url or "",
                    project_name,
                    ai_provider,
                    ai_model,
                    ai_cli_timeout,
                    force,
                    owner,
                )

    except asyncio.CancelledError:
        logger.warning(f"[{project_name}] Generation cancelled")
        await update_project_status(
            project_name,
            ai_provider,
            ai_model,
            status="aborted",
            owner=owner,
            error_message="Generation was cancelled",
            current_stage=None,
        )
        raise
    except Exception as exc:
        logger.error(f"Generation failed for {project_name}: {exc}")
        await update_project_status(
            project_name,
            ai_provider,
            ai_model,
            status="error",
            owner=owner,
            error_message=str(exc),
        )
    finally:
        _generating.pop(gen_key, None)


async def _generate_from_path(
    repo_dir: Path,
    commit_sha: str,
    source_url: str,
    project_name: str,
    ai_provider: str,
    ai_model: str,
    ai_cli_timeout: int,
    force: bool,
    owner: str = "",
) -> None:
    use_cache = False
    old_sha: str | None = None
    existing: dict[str, Any] | None = None

    if force:
        cache_dir = get_project_cache_dir(project_name, ai_provider, ai_model, owner)
        if cache_dir.exists():
            shutil.rmtree(cache_dir)
            logger.info(f"[{project_name}] Cleared cache (force=True)")
        # Reset page count so API shows 0 during regeneration
        await update_project_status(
            project_name,
            ai_provider,
            ai_model,
            status="generating",
            owner=owner,
            page_count=0,
        )
    else:
        existing = await get_project(
            project_name, ai_provider=ai_provider, ai_model=ai_model, owner=owner
        )
        if existing and existing.get("last_generated"):
            old_sha = (
                str(existing["last_commit_sha"])
                if existing.get("last_commit_sha")
                else None
            )
            if old_sha == commit_sha:
                logger.info(
                    f"[{project_name}] Project is up to date at {commit_sha[:8]}"
                )
                await update_project_status(
                    project_name,
                    ai_provider,
                    ai_model,
                    status="ready",
                    owner=owner,
                    current_stage="up_to_date",
                )
                return

    await update_project_status(
        project_name,
        ai_provider,
        ai_model,
        status="generating",
        owner=owner,
        current_stage="planning",
    )

    plan = await run_planner(
        repo_path=repo_dir,
        project_name=project_name,
        ai_provider=ai_provider,
        ai_model=ai_model,
        ai_cli_timeout=ai_cli_timeout,
    )

    plan["repo_url"] = source_url

    # Check if we can do incremental update
    cache_dir = get_project_cache_dir(project_name, ai_provider, ai_model, owner)
    if old_sha and old_sha != commit_sha and not force and existing:
        changed_files = get_changed_files(repo_dir, old_sha, commit_sha)
        if changed_files:
            existing_plan_json = existing.get("plan_json")
            if existing_plan_json:
                try:
                    existing_plan = json.loads(str(existing_plan_json))
                    await update_project_status(
                        project_name,
                        ai_provider,
                        ai_model,
                        status="generating",
                        owner=owner,
                        current_stage="incremental_planning",
                    )
                    pages_to_regen = await run_incremental_planner(
                        repo_dir,
                        project_name,
                        ai_provider,
                        ai_model,
                        changed_files,
                        existing_plan,
                        ai_cli_timeout,
                    )
                    if pages_to_regen != ["all"]:
                        # Delete only the cached pages that need regeneration
                        for slug in pages_to_regen:
                            # Validate slug to prevent path traversal
                            if (
                                "/" in slug
                                or "\\" in slug
                                or ".." in slug
                                or slug.startswith(".")
                            ):
                                logger.warning(
                                    f"[{project_name}] Skipping invalid slug from incremental planner: {slug}"
                                )
                                continue
                            cache_file = cache_dir / f"{slug}.md"
                            # Extra safety: ensure the resolved path is inside cache_dir
                            try:
                                cache_file.resolve().relative_to(cache_dir.resolve())
                            except ValueError:
                                logger.warning(
                                    f"[{project_name}] Path traversal attempt in slug: {slug}"
                                )
                                continue
                            if cache_file.exists():
                                cache_file.unlink()
                        use_cache = True
                        logger.info(
                            f"[{project_name}] Incremental update: {len(changed_files)} files changed, "
                            f"{len(pages_to_regen)} pages to regenerate"
                        )
                except (json.JSONDecodeError, TypeError):
                    logger.warning(
                        f"[{project_name}] Failed to parse existing plan, doing full regeneration"
                    )

    # Store plan so API consumers can see doc structure while pages generate
    await update_project_status(
        project_name,
        ai_provider,
        ai_model,
        status="generating",
        owner=owner,
        current_stage="generating_pages",
        plan_json=json.dumps(plan),
    )

    pages = await generate_all_pages(
        repo_path=repo_dir,
        plan=plan,
        cache_dir=cache_dir,
        ai_provider=ai_provider,
        ai_model=ai_model,
        ai_cli_timeout=ai_cli_timeout,
        use_cache=use_cache if use_cache else not force,
        project_name=project_name,
        owner=owner,
    )

    await update_project_status(
        project_name,
        ai_provider,
        ai_model,
        status="generating",
        owner=owner,
        current_stage="rendering",
        page_count=len(pages),
    )

    site_dir = get_project_site_dir(project_name, ai_provider, ai_model, owner)
    render_site(plan=plan, pages=pages, output_dir=site_dir)

    project_dir = get_project_dir(project_name, ai_provider, ai_model, owner)
    (project_dir / "plan.json").write_text(json.dumps(plan, indent=2), encoding="utf-8")

    page_count = len(pages)
    await update_project_status(
        project_name,
        ai_provider,
        ai_model,
        status="ready",
        owner=owner,
        current_stage=None,
        last_commit_sha=commit_sha,
        page_count=page_count,
        plan_json=json.dumps(plan),
    )
    logger.info(f"[{project_name}] Documentation ready ({page_count} pages)")


@app.get("/api/projects/{name}/{provider}/{model}")
async def get_variant_details(
    request: Request,
    name: str,
    provider: str,
    model: str,
) -> dict[str, str | int | None]:
    name = _validate_project_name(name)
    project = await get_project(name, ai_provider=provider, ai_model=model)
    if not project:
        raise HTTPException(status_code=404, detail="Variant not found")
    await _check_ownership(request, name, project)
    return project


@app.delete("/api/projects/{name}/{provider}/{model}")
async def delete_variant(
    request: Request,
    name: str,
    provider: str,
    model: str,
) -> dict[str, str]:
    _require_write_access(request)
    name = _validate_project_name(name)

    # Check for active generation (scan all keys)
    for key in _generating:
        parts = key.split("/", 3)
        if (
            len(parts) == 4
            and parts[1] == name
            and parts[2] == provider
            and parts[3] == model
        ):
            raise HTTPException(
                status_code=409,
                detail=f"Cannot delete '{name}/{provider}/{model}' while generation is in progress. Abort first.",
            )

    project = await get_project(name, ai_provider=provider, ai_model=model)
    if not project:
        raise HTTPException(status_code=404, detail="Variant not found")
    await _check_ownership(request, name, project)
    project_owner = str(project.get("owner", ""))
    deleted = await delete_project(
        name, ai_provider=provider, ai_model=model, owner=project_owner
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="Variant not found")
    project_dir = get_project_dir(name, provider, model, project_owner)
    if project_dir.exists():
        shutil.rmtree(project_dir)
    return {"deleted": f"{name}/{provider}/{model}"}


@app.get("/api/projects/{name}/{provider}/{model}/download")
async def download_variant(
    request: Request,
    name: str,
    provider: str,
    model: str,
) -> StreamingResponse:
    name = _validate_project_name(name)
    project = await get_project(name, ai_provider=provider, ai_model=model)
    if not project:
        raise HTTPException(status_code=404, detail="Variant not found")
    await _check_ownership(request, name, project)
    if project["status"] != "ready":
        raise HTTPException(status_code=400, detail="Variant not ready")
    project_owner = str(project.get("owner", ""))
    site_dir = get_project_site_dir(name, provider, model, project_owner)
    if not site_dir.exists():
        raise HTTPException(status_code=404, detail="Site not found")
    tmp = tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False)
    tar_path = Path(tmp.name)
    tmp.close()
    with tarfile.open(tar_path, mode="w:gz") as tar:
        tar.add(str(site_dir), arcname=f"{name}-{provider}-{model}")

    async def _stream_and_cleanup() -> AsyncIterator[bytes]:
        try:
            with open(tar_path, "rb") as f:
                while chunk := f.read(8192):
                    yield chunk
        finally:
            tar_path.unlink(missing_ok=True)

    return StreamingResponse(
        _stream_and_cleanup(),
        media_type="application/gzip",
        headers={
            "Content-Disposition": f'attachment; filename="{name}-{provider}-{model}-docs.tar.gz"'
        },
    )


@app.get("/api/projects/{name}")
async def get_project_details(request: Request, name: str) -> dict[str, Any]:
    name = _validate_project_name(name)
    if request.state.is_admin:
        variants = await list_variants(name)
    else:
        variants = await list_variants(name, owner=request.state.username)
    if not variants:
        raise HTTPException(status_code=404, detail=f"Project '{name}' not found")
    return {"name": name, "variants": variants}


@app.delete("/api/projects/{name}")
async def delete_project_endpoint(request: Request, name: str) -> dict[str, str]:
    _require_write_access(request)
    name = _validate_project_name(name)
    # Check if any variant is generating
    for gen_key in _generating:
        parts = gen_key.split("/", 3)
        if len(parts) == 4 and parts[1] == name:
            raise HTTPException(
                status_code=409,
                detail=f"Cannot delete '{name}' while generation is in progress. Abort running variants first.",
            )
    if request.state.is_admin:
        variants = await list_variants(name)
    else:
        variants = await list_variants(name, owner=request.state.username)
    if not variants:
        raise HTTPException(status_code=404, detail=f"Project '{name}' not found")
    for v in variants:
        v_provider = str(v.get("ai_provider", ""))
        v_model = str(v.get("ai_model", ""))
        v_owner = str(v.get("owner", ""))
        await delete_project(
            name, ai_provider=v_provider, ai_model=v_model, owner=v_owner
        )
        project_dir = get_project_dir(name, v_provider, v_model, v_owner)
        if project_dir.exists():
            shutil.rmtree(project_dir)
    return {"deleted": name}


@app.get("/api/projects/{name}/download")
async def download_project(request: Request, name: str) -> StreamingResponse:
    name = _validate_project_name(name)
    if request.state.is_admin:
        latest = await get_latest_variant(name)
    else:
        latest = await get_latest_variant(name, owner=request.state.username)
    if not latest:
        raise HTTPException(status_code=404, detail=f"No ready variant for '{name}'")
    await _check_ownership(request, name, latest)
    provider = str(latest.get("ai_provider", ""))
    model = str(latest.get("ai_model", ""))
    latest_owner = str(latest.get("owner", ""))
    site_dir = get_project_site_dir(name, provider, model, latest_owner)
    if not site_dir.exists():
        raise HTTPException(
            status_code=404, detail=f"Site directory not found for '{name}'"
        )
    tmp = tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False)
    tar_path = Path(tmp.name)
    tmp.close()
    with tarfile.open(tar_path, mode="w:gz") as tar:
        tar.add(str(site_dir), arcname=name)

    async def _stream_and_cleanup() -> AsyncIterator[bytes]:
        try:
            with open(tar_path, "rb") as f:
                while chunk := f.read(8192):
                    yield chunk
        finally:
            tar_path.unlink(missing_ok=True)

    return StreamingResponse(
        _stream_and_cleanup(),
        media_type="application/gzip",
        headers={"Content-Disposition": f'attachment; filename="{name}-docs.tar.gz"'},
    )


# ---------------------------------------------------------------------------
# Admin endpoints -- MUST be defined BEFORE /docs/{project}/{path:path}
# catch-all to avoid FastAPI matching project="admin".
# ---------------------------------------------------------------------------


def _require_admin(request: Request) -> None:
    """Raise 403 if the user is not an admin."""
    if not request.state.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")


@app.get("/admin", response_class=HTMLResponse)
async def admin_panel(request: Request) -> HTMLResponse:
    """Render the admin panel with user management."""
    _require_admin(request)
    users = await list_users()
    template = _jinja_env.get_template("admin.html")
    html = template.render(users=users, username=request.state.username)
    return HTMLResponse(content=html)


@app.post("/api/admin/users")
async def create_user_endpoint(request: Request) -> JSONResponse:
    """Create a new user and return the generated API key."""
    _require_admin(request)
    body = await request.json()
    username = body.get("username", "")
    role = body.get("role", "user")
    if not username:
        raise HTTPException(status_code=400, detail="Username is required")
    try:
        username, raw_key = await create_user(username, role)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    logger.info(
        f"[AUDIT] User '{request.state.username}' created user '{username}' with role '{role}'"
    )
    return JSONResponse(
        content={"username": username, "api_key": raw_key, "role": role},
        headers={"Cache-Control": "no-store"},
    )


@app.delete("/api/admin/users/{username}")
async def delete_user_endpoint(request: Request, username: str) -> dict[str, str]:
    """Delete a user by username."""
    _require_admin(request)
    # Fix 13: Prevent admin self-delete
    if username == request.state.username:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")
    deleted = await delete_user(username)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"User '{username}' not found")
    # Fix 18: Audit logging
    logger.info(f"[AUDIT] User '{request.state.username}' deleted user '{username}'")
    return {"deleted": username}


@app.get("/api/admin/users")
async def list_users_endpoint(
    request: Request,
) -> dict[str, list[dict[str, str | int | None]]]:
    """List all users."""
    _require_admin(request)
    users = await list_users()
    return {"users": users}


@app.post("/api/admin/projects/{name}/access")
async def grant_access(request: Request, name: str) -> dict[str, str]:
    _require_admin(request)
    body = await request.json()
    username = body.get("username", "")
    project_owner = body.get("owner", "")
    if not username:
        raise HTTPException(status_code=400, detail="Username is required")
    if not project_owner:
        raise HTTPException(status_code=400, detail="Project owner is required")
    # Validate user exists
    user = await get_user_by_username(username)
    if not user:
        raise HTTPException(status_code=404, detail=f"User '{username}' not found")
    # Validate project exists for the specified owner
    variants = await list_variants(name, owner=project_owner)
    if not variants:
        raise HTTPException(
            status_code=404,
            detail=f"Project '{name}' not found for owner '{project_owner}'",
        )
    await grant_project_access(name, username, project_owner=project_owner)
    logger.info(
        f"[AUDIT] Admin '{request.state.username}' granted '{username}' access to '{name}' (owner: '{project_owner}')"
    )
    return {"granted": name, "username": username, "owner": project_owner}


@app.delete("/api/admin/projects/{name}/access/{username}")
async def revoke_access(request: Request, name: str, username: str) -> dict[str, str]:
    _require_admin(request)
    project_owner = request.query_params.get("owner", "")
    await revoke_project_access(name, username, project_owner=project_owner)
    logger.info(
        f"[AUDIT] Admin '{request.state.username}' revoked '{username}' access to '{name}' (owner: '{project_owner}')"
    )
    return {"revoked": name, "username": username}


@app.get("/api/admin/projects/{name}/access")
async def list_access(request: Request, name: str) -> dict[str, Any]:
    _require_admin(request)
    project_owner = request.query_params.get("owner", "")
    users = await get_project_access(name, project_owner=project_owner)
    return {"project": name, "owner": project_owner, "users": users}


# ---------------------------------------------------------------------------
# Key rotation endpoints
# ---------------------------------------------------------------------------


@app.post("/api/me/rotate-key")
async def rotate_own_key(request: Request) -> JSONResponse:
    """User rotates their own API key."""
    # Don't call _require_write_access -- viewers should be able to change their password
    if request.state.is_admin and not request.state.user:
        raise HTTPException(
            status_code=400,
            detail="ADMIN_KEY users cannot rotate keys. Change the ADMIN_KEY env var instead.",
        )

    body = await request.json()
    custom_key = body.get("new_key")  # Optional -- if provided, use it

    username = request.state.username
    try:
        new_key = await rotate_user_key(username, custom_key=custom_key)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    logger.info(f"[AUDIT] User '{username}' rotated their own API key")
    # Clear current session -- user must re-login with new key
    session_token = request.cookies.get("docsfy_session")
    if session_token:
        await delete_session(session_token)
    settings = get_settings()
    response = JSONResponse(
        content={"username": username, "new_api_key": new_key},
        headers={"Cache-Control": "no-store"},
    )
    response.delete_cookie(
        "docsfy_session",
        httponly=True,
        samesite="strict",
        secure=settings.secure_cookies,
    )
    return response


@app.post("/api/admin/users/{username}/rotate-key")
async def admin_rotate_key(request: Request, username: str) -> JSONResponse:
    """Admin rotates a user's API key."""
    _require_admin(request)
    body = await request.json()
    custom_key = body.get("new_key")
    try:
        new_key = await rotate_user_key(username, custom_key=custom_key)
    except ValueError as exc:
        detail = str(exc)
        status = 404 if "not found" in detail else 400
        raise HTTPException(status_code=status, detail=detail) from exc
    logger.info(
        f"[AUDIT] Admin '{request.state.username}' rotated API key for user '{username}'"
    )
    return JSONResponse(
        content={"username": username, "new_api_key": new_key},
        headers={"Cache-Control": "no-store"},
    )


# IMPORTANT: variant-specific route MUST be defined BEFORE the generic route
# so FastAPI matches it first.
@app.get("/docs/{project}/{provider}/{model}/{path:path}")
async def serve_variant_docs(
    request: Request,
    project: str,
    provider: str,
    model: str,
    path: str = "index.html",
) -> FileResponse:
    if not path or path == "/":
        path = "index.html"
    project = _validate_project_name(project)
    proj = await get_project(project, ai_provider=provider, ai_model=model)
    if not proj:
        raise HTTPException(status_code=404, detail="Not found")
    await _check_ownership(request, project, proj)
    proj_owner = str(proj.get("owner", ""))
    site_dir = get_project_site_dir(project, provider, model, proj_owner)
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
        latest = await get_latest_variant(project, owner=request.state.username)
    if not latest:
        raise HTTPException(status_code=404, detail="No docs available")
    await _check_ownership(request, project, latest)
    latest_owner = str(latest.get("owner", ""))
    site_dir = get_project_site_dir(
        project,
        str(latest["ai_provider"]),
        str(latest["ai_model"]),
        latest_owner,
    )
    file_path = site_dir / path
    try:
        file_path.resolve().relative_to(site_dir.resolve())
    except ValueError as exc:
        raise HTTPException(status_code=403, detail="Access denied") from exc
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path)


def run() -> None:
    import uvicorn

    reload = os.getenv("DEBUG", "").lower() == "true"
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("docsfy.main:app", host=host, port=port, reload=reload)
