from __future__ import annotations

import asyncio
import ipaddress
import json
import shutil
import socket
import tarfile
import tempfile
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from simple_logger.logger import get_logger

from docsfy.ai_client import check_ai_cli_available
from docsfy.config import get_settings
from docsfy.generator import (
    generate_all_pages,
    is_unsafe_slug,
    run_incremental_planner,
    run_planner,
)
from docsfy.models import (
    DEFAULT_BRANCH,
    VALID_PROVIDERS,
    GenerateRequest,
)
from docsfy.postprocess import (
    add_cross_links,
    detect_version,
    fix_broken_internal_links,
    linkify_plain_references,
    validate_pages,
)
from docsfy.renderer import render_site
from docsfy.repository import (
    clone_repo,
    deepen_clone_for_diff,
    get_diff,
    get_local_repo_info,
)
from docsfy.storage import (
    _validate_name,
    delete_project,
    get_known_branches,
    get_known_models,
    get_latest_variant,
    get_project,
    get_project_access,
    get_project_cache_dir,
    get_project_dir,
    get_project_site_dir,
    get_user_accessible_projects,
    list_projects,
    list_variants,
    save_project,
    update_project_status,
)
from docsfy.api.websocket import (
    notify_progress,
    notify_status_change,
    notify_sync,
)

logger = get_logger(name=__name__)

_ABORT_TIMEOUT = 5.0


def _redact_url(url: str | None) -> str:
    """Strip credentials from a URL for safe logging."""
    if not url:
        return "<none>"
    try:
        from urllib.parse import urlparse, urlunparse

        parsed = urlparse(url)
        if parsed.username or parsed.password:
            redacted = parsed._replace(
                netloc=f"***@{parsed.hostname}"
                + (f":{parsed.port}" if parsed.port else "")
            )
            return urlunparse(redacted)
    except Exception:
        pass
    return url


_STREAM_CHUNK_SIZE = 8192


_generating: dict[str, asyncio.Task[None]] = {}
# Fix 6: asyncio.Lock to prevent race between checking and adding to _generating
_gen_lock = asyncio.Lock()

_TERMINAL_STATUSES = frozenset({"ready", "error", "aborted"})


async def update_and_notify(
    gen_key: str,
    project_name: str,
    ai_provider: str,
    ai_model: str,
    status: str,
    branch: str = DEFAULT_BRANCH,
    owner: str | None = None,
    last_commit_sha: str | None = None,
    page_count: int | None = None,
    error_message: str | None = None,
    plan_json: str | None = None,
    current_stage: str | None | object = None,
) -> None:
    """Update project status in DB and send WebSocket notification."""
    ups_kwargs: dict[str, Any] = {
        "status": status,
        "branch": branch,
    }
    if owner is not None:
        ups_kwargs["owner"] = owner
    if last_commit_sha is not None:
        ups_kwargs["last_commit_sha"] = last_commit_sha
    if page_count is not None:
        ups_kwargs["page_count"] = page_count
    if error_message is not None:
        ups_kwargs["error_message"] = error_message
    if plan_json is not None:
        ups_kwargs["plan_json"] = plan_json

    # Always pass current_stage through so that None clears the stage in the DB.
    ups_kwargs["current_stage"] = current_stage

    await update_project_status(project_name, ai_provider, ai_model, **ups_kwargs)

    if status in _TERMINAL_STATUSES:
        await notify_status_change(
            gen_key=gen_key,
            status=status,
            page_count=page_count,
            last_generated=(
                datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")
                if status == "ready"
                else None
            ),
            last_commit_sha=last_commit_sha,
            error_message=error_message,
        )
        await notify_sync()
    else:
        await notify_progress(
            gen_key=gen_key,
            status=status,
            current_stage=current_stage if isinstance(current_stage, str) else None,
            page_count=page_count,
            plan_json=plan_json,
            error_message=error_message,
        )


router = APIRouter(prefix="/api", tags=["projects"])


def _validate_project_name(name: str) -> str:
    """Validate project name to prevent path traversal."""
    try:
        return _validate_name(name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


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


async def _resolve_project(
    request: Request,
    name: str,
    ai_provider: str,
    ai_model: str,
    branch: str = DEFAULT_BRANCH,
) -> dict[str, Any]:
    """Find a project variant, preferring the requesting user's owned copy.

    Raises 404 if not found or not accessible.
    """
    logger.debug(
        f"Resolving project: name='{name}', provider='{ai_provider}', model='{ai_model}', branch='{branch}'"
    )
    # 0. If ?owner= is provided, use that owner for the initial lookup
    requested_owner = request.query_params.get("owner")
    if requested_owner is not None and not request.state.is_admin:
        requested_owner = None  # Non-admins cannot specify owner
    lookup_owner = (
        requested_owner if requested_owner is not None else request.state.username
    )

    # 1. Try owned by requesting/specified user (including admin)
    proj = await get_project(
        name,
        ai_provider=ai_provider,
        ai_model=ai_model,
        owner=lookup_owner,
        branch=branch,
    )
    if proj:
        return proj

    # 2. For admin, disambiguate by owner (fallback when admin doesn't own it)
    if request.state.is_admin:
        all_variants = await list_variants(name)
        matching = [
            v
            for v in all_variants
            if str(v.get("ai_provider", "")) == ai_provider
            and str(v.get("ai_model", "")) == ai_model
            and str(v.get("branch", DEFAULT_BRANCH)) == branch
        ]
        if not matching:
            raise HTTPException(status_code=404, detail="Not found")
        # If admin and multiple owners, check ?owner= query param
        if requested_owner is not None:
            matching = [
                v for v in matching if str(v.get("owner", "")) == requested_owner
            ]
            if not matching:
                raise HTTPException(status_code=404, detail="Not found")
        distinct_owners = {str(v.get("owner", "")) for v in matching}
        if len(distinct_owners) > 1:
            raise HTTPException(
                status_code=409,
                detail="Multiple owners found for this variant, please specify owner",
            )
        return matching[0]

    # 3. For non-admin, check granted access — find which owner granted access
    accessible = await get_user_accessible_projects(request.state.username)
    matched_projects: list[dict[str, Any]] = []
    for proj_name, proj_owner in accessible:
        if proj_name == name and proj_owner:
            # Found a grant — look up this specific owner's variant
            proj = await get_project(
                name,
                ai_provider=ai_provider,
                ai_model=ai_model,
                owner=proj_owner,
                branch=branch,
            )
            if proj:
                matched_projects.append(proj)

    if matched_projects:
        distinct_owners = {str(p.get("owner", "")) for p in matched_projects}
        if len(distinct_owners) > 1:
            owners_str = ", ".join(sorted(distinct_owners))
            raise HTTPException(
                status_code=409,
                detail=f"Multiple owners found for this variant ({owners_str}). "
                f"Contact an admin to resolve the ambiguity.",
            )
        return matched_projects[0]

    # 4. Not found
    raise HTTPException(status_code=404, detail="Not found")


async def _reject_private_url(url: str) -> None:
    """Reject URLs targeting private/internal IP ranges (SSRF mitigation).

    This provides basic protection against SSRF. More comprehensive protection
    (DNS rebinding, etc.) should be handled at the network/firewall level.
    """
    from urllib.parse import urlparse

    try:
        parsed = urlparse(url)

        # Reject non-HTTP(S) schemes (e.g. file://, ftp://) unless SSH format
        if not url.startswith("git@"):
            if parsed.scheme and parsed.scheme.lower() not in (
                "http",
                "https",
                "git",
                "ssh",
            ):
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported URL scheme: '{parsed.scheme}'. Only http, https, git, and ssh are allowed",
                )
            # Reject hostless URLs like file:///etc/passwd or //localhost/
            if parsed.scheme and not parsed.hostname:
                raise HTTPException(
                    status_code=400,
                    detail="Repository URL must include a hostname",
                )

        hostname = parsed.hostname
        # Handle SSH format: git@hostname:org/repo.git
        if not hostname and url.startswith("git@"):
            try:
                hostname = url.split("@")[1].split(":")[0]
            except (IndexError, ValueError):
                raise HTTPException(
                    status_code=400,
                    detail="Could not parse hostname from SSH URL",
                )
        if not hostname:
            # Reject bare paths like /srv/repo.git or ../repo that have
            # no scheme and no hostname -- they are local filesystem refs.
            raise HTTPException(
                status_code=400,
                detail="Repository URL must include a hostname. Bare local paths are not allowed.",
            )
        # Check for localhost
        if hostname in ("localhost", "127.0.0.1", "::1", "0.0.0.0"):
            raise HTTPException(
                status_code=400,
                detail="Repository URL must not target localhost or private networks",
            )
        # Check if hostname is an IP address in private range
        try:
            addr = ipaddress.ip_address(hostname)
            if not addr.is_global:
                raise HTTPException(
                    status_code=400,
                    detail="Repository URL must not target localhost or private networks",
                )
        except ValueError:
            # hostname is a DNS name - resolve and check
            try:
                loop = asyncio.get_event_loop()
                resolved = await loop.run_in_executor(
                    None,
                    socket.getaddrinfo,
                    hostname,
                    None,
                    socket.AF_UNSPEC,
                    socket.SOCK_STREAM,
                )
                for _family, _socktype, _proto, _canonname, sockaddr in resolved:
                    ip_str = sockaddr[0]
                    addr = ipaddress.ip_address(ip_str)
                    if not addr.is_global:
                        raise HTTPException(
                            status_code=400,
                            detail="Repository URL resolves to a private network address",
                        )
            except socket.gaierror:
                pass  # DNS resolution failed - let git clone handle the error
    except HTTPException:
        raise
    except (ValueError, OSError, socket.gaierror) as exc:
        logger.debug(f"URL validation skipped for '{url}': {exc}")


async def _stream_tarball(site_dir: Path, archive_name: str) -> StreamingResponse:
    """Create a tar.gz archive and stream it as a response."""
    tmp = tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False)
    tar_path = Path(tmp.name)
    tmp.close()

    def _create_archive() -> None:
        with tarfile.open(tar_path, mode="w:gz") as tar:
            tar.add(str(site_dir), arcname=archive_name)

    try:
        await asyncio.to_thread(_create_archive)
    except Exception:
        tar_path.unlink(missing_ok=True)
        raise

    async def _stream_and_cleanup() -> AsyncIterator[bytes]:
        try:
            f = await asyncio.to_thread(open, tar_path, "rb")
            try:
                while True:
                    chunk = await asyncio.to_thread(f.read, _STREAM_CHUNK_SIZE)
                    if not chunk:
                        break
                    yield chunk
            finally:
                await asyncio.to_thread(f.close)
        finally:
            tar_path.unlink(missing_ok=True)

    return StreamingResponse(
        _stream_and_cleanup(),
        media_type="application/gzip",
        headers={
            "Content-Disposition": f'attachment; filename="{archive_name}-docs.tar.gz"'
        },
    )


async def _copy_variant_artifacts(
    project_name: str,
    source_provider: str,
    source_model: str,
    target_provider: str,
    target_model: str,
    owner: str,
    include_site: bool = False,
    branch: str = DEFAULT_BRANCH,
) -> bool:
    """Copy an existing variant directory into a new provider/model variant."""
    source_dir = get_project_dir(
        project_name, source_provider, source_model, owner, branch=branch
    )
    target_dir = get_project_dir(
        project_name, target_provider, target_model, owner, branch=branch
    )

    if not source_dir.exists():
        logger.warning(
            f"[{project_name}] Source artifacts missing for {source_provider}/{source_model}; "
            f"cannot prefill {target_provider}/{target_model}"
        )
        return False

    if target_dir.exists():
        await asyncio.to_thread(shutil.rmtree, target_dir)

    target_dir.parent.mkdir(parents=True, exist_ok=True)
    if include_site:
        await asyncio.to_thread(
            shutil.copytree,
            source_dir,
            target_dir,
            dirs_exist_ok=True,
        )
    else:
        await asyncio.to_thread(
            shutil.copytree,
            source_dir,
            target_dir,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns("site"),
        )
    return True


async def _replace_variant(
    project_name: str,
    source_provider: str,
    source_model: str,
    target_provider: str,
    target_model: str,
    owner: str,
    branch: str = DEFAULT_BRANCH,
) -> None:
    """Delete the old variant after its replacement is ready."""
    if source_provider == target_provider and source_model == target_model:
        return

    async with _gen_lock:
        # Check if source variant is actively generating
        gen_key_prefix = (
            f"{owner}/{project_name}/{branch}/{source_provider}/{source_model}"
        )
        for key in _generating:
            if key == gen_key_prefix:
                logger.warning(
                    f"[{project_name}] Source variant {source_provider}/{source_model} "
                    f"is actively generating, skipping replacement"
                )
                return

        try:
            await delete_project(
                project_name,
                ai_provider=source_provider,
                ai_model=source_model,
                owner=owner,
                branch=branch,
            )
        except Exception as exc:
            logger.warning(
                f"[{project_name}] Failed to delete old variant DB row: {exc}"
            )
            return

    # Filesystem cleanup outside lock (best-effort)
    try:
        old_dir = get_project_dir(
            project_name, source_provider, source_model, owner, branch=branch
        )
        if old_dir.exists():
            await asyncio.to_thread(shutil.rmtree, old_dir)
    except Exception as exc:
        logger.warning(
            f"[{project_name}] Failed to clean up old variant directory: {exc}"
        )

    logger.info(
        f"[{project_name}] Replaced {source_provider}/{source_model} variant with "
        f"{target_provider}/{target_model}"
    )

    # Notify connected clients so the deleted variant disappears from the UI
    await notify_sync(owner)


async def _run_generation(
    repo_url: str | None,
    repo_path: str | None,
    project_name: str,
    ai_provider: str,
    ai_model: str,
    ai_cli_timeout: int,
    force: bool = False,
    owner: str = "",
    branch: str = DEFAULT_BRANCH,
) -> None:
    gen_key = f"{owner}/{project_name}/{branch}/{ai_provider}/{ai_model}"
    try:
        cli_flags = ["--trust"] if ai_provider == "cursor" else None
        available, msg = await check_ai_cli_available(
            ai_provider, ai_model, cli_flags=cli_flags
        )
        if not available:
            await update_and_notify(
                gen_key,
                project_name,
                ai_provider,
                ai_model,
                status="error",
                owner=owner,
                branch=branch,
                error_message=msg,
            )
            return

        await update_and_notify(
            gen_key,
            project_name,
            ai_provider,
            ai_model,
            status="generating",
            owner=owner,
            branch=branch,
            current_stage="cloning",
        )

        if repo_path:
            # Local repository - use directly, no cloning needed
            local_path, commit_sha, _ = get_local_repo_info(
                Path(repo_path), expected_branch=branch
            )
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
                branch=branch,
            )
        else:
            # Remote repository - clone to temp dir
            if repo_url is None:
                msg = "repo_url must be provided for remote repositories"
                raise ValueError(msg)
            with tempfile.TemporaryDirectory() as tmp_dir:
                repo_dir, commit_sha, _ = await asyncio.to_thread(
                    clone_repo, repo_url, Path(tmp_dir), branch=branch
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
                    branch=branch,
                )

    except asyncio.CancelledError:
        logger.warning(f"[{project_name}] Generation cancelled")
        await update_and_notify(
            gen_key,
            project_name,
            ai_provider,
            ai_model,
            status="aborted",
            owner=owner,
            branch=branch,
            error_message="Generation was cancelled",
            current_stage=None,
        )
        raise
    except Exception as exc:
        logger.error(f"Generation failed for {project_name}: {exc}")
        await update_and_notify(
            gen_key,
            project_name,
            ai_provider,
            ai_model,
            status="error",
            owner=owner,
            branch=branch,
            error_message=str(exc),
        )
    finally:
        async with _gen_lock:
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
    branch: str = DEFAULT_BRANCH,
) -> None:
    cache_dir = get_project_cache_dir(
        project_name, ai_provider, ai_model, owner, branch=branch
    )
    use_cache = False
    old_sha: str | None = None
    base_variant: dict[str, Any] | None = None
    plan: dict[str, Any] | None = None
    changed_files: list[str] | None = None
    diff_content: str | None = None
    existing_pages: dict[str, str] = {}
    base_provider = ai_provider
    base_model = ai_model
    copied_base_artifacts = False
    replaces_base_variant = False

    gen_key = f"{owner}/{project_name}/{branch}/{ai_provider}/{ai_model}"

    async def _mark_up_to_date(base_project: dict[str, Any] | None = None) -> None:
        page_count = (
            int(base_project["page_count"])
            if base_project and base_project.get("page_count") is not None
            else None
        )
        plan_json = (
            str(base_project["plan_json"])
            if base_project and base_project.get("plan_json") is not None
            else None
        )
        await update_and_notify(
            gen_key,
            project_name,
            ai_provider,
            ai_model,
            status="ready",
            owner=owner,
            branch=branch,
            current_stage="up_to_date",
            last_commit_sha=commit_sha,
            page_count=page_count,
            plan_json=plan_json,
        )

    async def _replace_base_variant() -> None:
        if not replaces_base_variant:
            return

        await _replace_variant(
            project_name=project_name,
            source_provider=base_provider,
            source_model=base_model,
            target_provider=ai_provider,
            target_model=ai_model,
            owner=owner,
            branch=branch,
        )

    if force:
        if cache_dir.exists():
            await asyncio.to_thread(shutil.rmtree, cache_dir)
            logger.info(f"[{project_name}] Cleared cache (force=True)")
        # Reset page count so API shows 0 during regeneration
        await update_and_notify(
            gen_key,
            project_name,
            ai_provider,
            ai_model,
            status="generating",
            owner=owner,
            branch=branch,
            page_count=0,
        )
    else:
        current_variant = await get_project(
            project_name,
            ai_provider=ai_provider,
            ai_model=ai_model,
            owner=owner,
            branch=branch,
        )
        ready_current_variant = (
            current_variant
            if current_variant and current_variant.get("last_generated")
            else None
        )

        # Check if a cross-provider variant is newer
        latest_any = await get_latest_variant(project_name, owner=owner, branch=branch)
        if ready_current_variant and latest_any:
            current_gen = str(ready_current_variant.get("last_generated") or "")
            latest_gen = str(latest_any.get("last_generated") or "")
            if latest_gen > current_gen and (
                latest_any.get("ai_provider") != ai_provider
                or latest_any.get("ai_model") != ai_model
            ):
                base_variant = latest_any
            else:
                base_variant = ready_current_variant
        elif ready_current_variant:
            base_variant = ready_current_variant
        elif latest_any:
            base_variant = latest_any
        else:
            base_variant = None

        if base_variant:
            base_provider = str(base_variant.get("ai_provider", ""))
            base_model = str(base_variant.get("ai_model", ""))
            replaces_base_variant = (
                base_provider != ai_provider or base_model != ai_model
            )
            if replaces_base_variant:
                logger.info(
                    f"[{project_name}] Cross-provider update: reusing {base_provider}/{base_model} "
                    f"content for {ai_provider}/{ai_model} generation"
                )
                same_commit = base_variant.get("last_commit_sha") == commit_sha
                copied_base_artifacts = await _copy_variant_artifacts(
                    project_name=project_name,
                    source_provider=base_provider,
                    source_model=base_model,
                    target_provider=ai_provider,
                    target_model=ai_model,
                    owner=owner,
                    include_site=same_commit,
                    branch=branch,
                )
        elif current_variant:
            base_variant = current_variant

        if base_variant and base_variant.get("last_generated"):
            old_sha = (
                str(base_variant["last_commit_sha"])
                if base_variant.get("last_commit_sha")
                else None
            )
            if old_sha == commit_sha and (
                not replaces_base_variant or copied_base_artifacts
            ):
                logger.info(
                    f"[{project_name}] Project is up to date at {commit_sha[:8]}"
                )
                await _mark_up_to_date(base_variant)
                await _replace_base_variant()
                return

    # Check if we can do incremental update BEFORE planning to avoid
    # paying the full planning cost for up-to-date or metadata-only commits
    can_run_incremental_update = bool(
        old_sha
        and old_sha != commit_sha
        and not force
        and base_variant
        and (not replaces_base_variant or copied_base_artifacts)
    )
    if replaces_base_variant and not copied_base_artifacts and not force:
        logger.warning(
            f"[{project_name}] Base artifacts copy failed, falling back to full regeneration"
        )
    if can_run_incremental_update:
        # Shallow clones (--depth 1) only contain the latest commit.
        # Fetch the old commit so that git-diff can compare the two.
        if old_sha is not None and not deepen_clone_for_diff(repo_dir, old_sha):
            logger.warning(
                f"[{project_name}] Could not fetch old commit {old_sha}, "
                "falling back to full regeneration"
            )
            old_sha = None  # skip the diff branch entirely
            can_run_incremental_update = False

    if can_run_incremental_update:
        if old_sha is not None:
            diff_result = get_diff(repo_dir, old_sha, commit_sha)
        else:
            diff_result = None
        if diff_result is None:
            logger.warning(
                f"[{project_name}] Failed to get diff, falling back to full regeneration"
            )
        else:
            changed_files, diff_content = diff_result
            if not changed_files:
                # Commits differ but tree is identical — nothing to regenerate
                await _mark_up_to_date(base_variant)
                await _replace_base_variant()
                return
            if base_variant is not None:
                existing_plan_json = base_variant.get("plan_json")
            else:
                existing_plan_json = None
            if existing_plan_json:
                try:
                    existing_plan = json.loads(str(existing_plan_json))
                    await update_and_notify(
                        gen_key,
                        project_name,
                        ai_provider,
                        ai_model,
                        status="generating",
                        owner=owner,
                        branch=branch,
                        current_stage="incremental_planning",
                        page_count=0,
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
                    if pages_to_regen == ["all"]:
                        # All pages need regeneration but keep the existing plan
                        # Delete all cached pages so they get regenerated
                        if cache_dir.exists():
                            for cache_file in cache_dir.glob("*.md"):
                                existing_pages[cache_file.stem] = cache_file.read_text(
                                    encoding="utf-8"
                                )
                                cache_file.unlink()
                        plan = existing_plan
                        use_cache = False
                        logger.info(
                            f"[{project_name}] Full incremental update: "
                            f"all pages to regenerate, reusing existing plan"
                        )
                    else:
                        valid_pages_to_regen: list[str] = []
                        # Read existing content before deleting cached pages
                        for slug in pages_to_regen:
                            # Validate slug to prevent path traversal
                            if is_unsafe_slug(slug):
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
                            valid_pages_to_regen.append(slug)
                            if cache_file.exists():
                                existing_pages[slug] = cache_file.read_text(
                                    encoding="utf-8"
                                )
                                cache_file.unlink()
                        plan = existing_plan
                        use_cache = True
                        logger.info(
                            f"[{project_name}] Incremental update: {len(changed_files)} files changed, "
                            f"{len(valid_pages_to_regen)} pages to regenerate"
                        )
                except (json.JSONDecodeError, TypeError):
                    logger.warning(
                        f"[{project_name}] Failed to parse existing plan, doing full regeneration"
                    )

    if plan is None:
        await update_and_notify(
            gen_key,
            project_name,
            ai_provider,
            ai_model,
            status="generating",
            owner=owner,
            branch=branch,
            current_stage="planning",
            page_count=0,
        )

        plan = await run_planner(
            repo_path=repo_dir,
            project_name=project_name,
            ai_provider=ai_provider,
            ai_model=ai_model,
            ai_cli_timeout=ai_cli_timeout,
        )

    if plan is None:
        raise RuntimeError("Plan was not generated")
    plan["repo_url"] = source_url

    if not use_cache and cache_dir.exists():
        # A full regeneration should start from a clean cache so progress reflects
        # pages generated in this run and removed pages do not linger on disk.
        for cache_file in cache_dir.glob("*.md"):
            cache_file.unlink()

    current_page_count = (
        len(list(cache_dir.glob("*.md"))) if use_cache and cache_dir.exists() else 0
    )

    # Store plan so API consumers can see doc structure while pages generate
    await update_and_notify(
        gen_key,
        project_name,
        ai_provider,
        ai_model,
        status="generating",
        owner=owner,
        branch=branch,
        current_stage="generating_pages",
        plan_json=json.dumps(plan),
        page_count=current_page_count,
    )

    async def _on_page_generated(page_count: int) -> None:
        await notify_progress(
            gen_key=gen_key,
            status="generating",
            current_stage="generating_pages",
            page_count=page_count,
        )

    pages = await generate_all_pages(
        repo_path=repo_dir,
        plan=plan,
        cache_dir=cache_dir,
        ai_provider=ai_provider,
        ai_model=ai_model,
        ai_cli_timeout=ai_cli_timeout,
        use_cache=use_cache,
        project_name=project_name,
        owner=owner,
        changed_files=changed_files,
        existing_pages=existing_pages if existing_pages else None,
        diff_content=diff_content,
        branch=branch,
        on_page_generated=_on_page_generated,
    )

    # --- Post-generation pipeline ---
    try:
        await update_and_notify(
            gen_key,
            project_name,
            ai_provider,
            ai_model,
            status="generating",
            owner=owner,
            branch=branch,
            current_stage="validating",
            page_count=len(pages),
        )
        pages = await validate_pages(
            pages=pages,
            repo_path=repo_dir,
            ai_provider=ai_provider,
            ai_model=ai_model,
            cache_dir=cache_dir,
            project_name=project_name,
            plan=plan,
            ai_cli_timeout=ai_cli_timeout,
        )
    except Exception as exc:
        logger.warning(f"[{project_name}] Validation stage failed: {exc}")

    try:
        await update_and_notify(
            gen_key,
            project_name,
            ai_provider,
            ai_model,
            status="generating",
            owner=owner,
            branch=branch,
            current_stage="cross_linking",
            page_count=len(pages),
        )
        pages = fix_broken_internal_links(pages, plan, project_name=project_name)
        try:
            pages = linkify_plain_references(pages, plan, project_name=project_name)
        except Exception as exc:
            logger.warning(f"[{project_name}] linkify_plain_references failed: {exc}")
        pages = await add_cross_links(
            pages=pages,
            plan=plan,
            ai_provider=ai_provider,
            ai_model=ai_model,
            repo_path=repo_dir,
            project_name=project_name,
            ai_cli_timeout=ai_cli_timeout,
        )
    except Exception as exc:
        logger.warning(f"[{project_name}] Cross-linking stage failed: {exc}")

    version = detect_version(repo_dir)
    if version:
        plan["version"] = version
        logger.info(f"[{project_name}] Detected project version: {version}")
    # --- End post-generation pipeline ---

    await update_and_notify(
        gen_key,
        project_name,
        ai_provider,
        ai_model,
        status="generating",
        owner=owner,
        branch=branch,
        current_stage="rendering",
        page_count=len(pages),
    )

    site_dir = get_project_site_dir(
        project_name, ai_provider, ai_model, owner, branch=branch
    )
    render_site(plan=plan, pages=pages, output_dir=site_dir)

    project_dir = get_project_dir(
        project_name, ai_provider, ai_model, owner, branch=branch
    )
    (project_dir / "plan.json").write_text(json.dumps(plan, indent=2), encoding="utf-8")

    page_count = len(pages)
    await update_and_notify(
        gen_key,
        project_name,
        ai_provider,
        ai_model,
        status="ready",
        owner=owner,
        branch=branch,
        current_stage=None,
        last_commit_sha=commit_sha,
        page_count=page_count,
        plan_json=json.dumps(plan),
    )
    logger.info(f"[{project_name}] Documentation ready ({page_count} pages)")

    await _replace_base_variant()


async def _resolve_latest_accessible_variant(
    username: str, name: str
) -> dict[str, Any] | None:
    """Find the newest variant across owned and shared projects.

    Collects the caller's own latest variant **and** all shared variants
    from owners that have granted access to *username*, then returns the
    one with the newest ``last_generated`` timestamp.  If multiple
    variants tie on the newest timestamp (ambiguous), raises HTTP 409.

    Returns ``None`` when no variants are found at all.
    """
    candidates: list[dict[str, Any]] = []

    # 1. Caller's owned variant
    owned = await get_latest_variant(name, owner=username)
    if owned:
        candidates.append(owned)

    # 2. Shared variants from other owners
    accessible = await get_user_accessible_projects(username)
    for proj_name, proj_owner in accessible:
        if proj_name == name and proj_owner:
            variant = await get_latest_variant(name, owner=proj_owner)
            if variant:
                candidates.append(variant)

    if not candidates:
        return None

    if len(candidates) == 1:
        return candidates[0]

    # Pick the variant with the newest last_generated timestamp
    def _sort_key(v: dict[str, Any]) -> str:
        return str(v.get("last_generated") or "")

    candidates.sort(key=_sort_key, reverse=True)
    newest = _sort_key(candidates[0])
    tied = [c for c in candidates if _sort_key(c) == newest]
    if len(tied) > 1:
        raise HTTPException(
            status_code=409,
            detail="Multiple owners have variants with the same timestamp, please specify owner",
        )
    return candidates[0]


# ---------------------------------------------------------------------------
# Route handlers
# ---------------------------------------------------------------------------


async def build_projects_payload(username: str, is_admin: bool) -> dict[str, Any]:
    """Build the projects sync payload for the given user.

    Shared by the REST status/projects endpoints and the WebSocket sync logic.
    """
    if is_admin:
        projects = await list_projects()
        known_branches = await get_known_branches()
    else:
        accessible = await get_user_accessible_projects(username)
        projects = await list_projects(owner=username, accessible=accessible)
        known_branches = await get_known_branches(owner=username)

    known_models = await get_known_models()
    return {
        "projects": projects,
        "known_models": known_models,
        "known_branches": known_branches,
    }


@router.get("/models")
async def get_models_endpoint() -> dict[str, Any]:
    """Return available AI providers, server defaults, and known models.

    No authentication required -- this is a discovery endpoint.
    """
    settings = get_settings()
    try:
        known_models = await get_known_models()
    except Exception as exc:
        logger.warning(f"/api/models: failed to load known_models: {exc}")
        known_models = {}
    return {
        "providers": list(VALID_PROVIDERS),
        "default_provider": settings.ai_provider,
        "default_model": settings.ai_model,
        "known_models": known_models,
    }


@router.get("/status")
@router.get("/projects")
async def status(request: Request) -> dict[str, Any]:
    return await build_projects_payload(request.state.username, request.state.is_admin)


@router.get("/projects/{name}")
async def get_project_details(request: Request, name: str) -> dict[str, Any]:
    name = _validate_project_name(name)
    if request.state.is_admin:
        variants = await list_variants(name)
    else:
        variants = await list_variants(name, owner=request.state.username)
        # Always merge shared variants so they appear alongside owned ones
        seen: set[tuple[str, str, str, str]] = {
            (
                str(v.get("owner", "")),
                str(v.get("branch", DEFAULT_BRANCH)),
                str(v.get("ai_provider", "")),
                str(v.get("ai_model", "")),
            )
            for v in variants
        }
        accessible = await get_user_accessible_projects(request.state.username)
        for proj_name, proj_owner in accessible:
            if proj_name == name and proj_owner:
                shared_variants = await list_variants(name, owner=proj_owner)
                for sv in shared_variants:
                    key = (
                        str(sv.get("owner", "")),
                        str(sv.get("branch", DEFAULT_BRANCH)),
                        str(sv.get("ai_provider", "")),
                        str(sv.get("ai_model", "")),
                    )
                    if key not in seen:
                        seen.add(key)
                        variants.append(sv)
    if not variants:
        raise HTTPException(status_code=404, detail=f"Project '{name}' not found")
    return {"name": name, "variants": variants}


@router.post("/generate", status_code=202)
async def generate(
    request: Request, gen_request: GenerateRequest
) -> dict[str, str | None]:
    _require_write_access(request)
    logger.debug(
        f"Generate request: repo_url='{_redact_url(gen_request.repo_url)}', provider='{gen_request.ai_provider}', "
        f"model='{gen_request.ai_model}', branch='{gen_request.branch}', force={gen_request.force}"
    )
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
        await _reject_private_url(gen_request.repo_url)

    settings = get_settings()
    ai_provider = gen_request.ai_provider or settings.ai_provider
    ai_model = gen_request.ai_model or settings.ai_model
    project_name = gen_request.project_name
    owner = request.state.username

    if ai_provider not in VALID_PROVIDERS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid AI provider: '{ai_provider}'. Must be one of {', '.join(VALID_PROVIDERS)}.",
        )
    if not ai_model:
        raise HTTPException(status_code=400, detail="AI model must be specified.")

    # Fix 6: Use lock to prevent race condition between check and add
    branch = gen_request.branch
    gen_key = f"{owner}/{project_name}/{branch}/{ai_provider}/{ai_model}"
    async with _gen_lock:
        if gen_key in _generating:
            raise HTTPException(
                status_code=409,
                detail=f"Variant '{project_name}/{branch}/{ai_provider}/{ai_model}' is already being generated",
            )

        await save_project(
            name=project_name,
            repo_url=gen_request.repo_url or gen_request.repo_path or "",
            status="generating",
            ai_provider=ai_provider,
            ai_model=ai_model,
            owner=owner,
            branch=branch,
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
                    branch=branch,
                )
            )
            _generating[gen_key] = task
        except Exception:
            _generating.pop(gen_key, None)
            raise

    return {"project": project_name, "status": "generating", "branch": branch}


@router.get("/projects/{name}/{branch}/{provider}/{model}")
async def get_variant_details(
    request: Request,
    name: str,
    branch: str,
    provider: str,
    model: str,
) -> dict[str, str | int | None]:
    name = _validate_project_name(name)
    project = await _resolve_project(
        request,
        name,
        ai_provider=provider,
        ai_model=model,
        branch=branch,
    )

    return project


@router.delete("/projects/{name}/{branch}/{provider}/{model}")
async def delete_variant(
    request: Request,
    name: str,
    branch: str,
    provider: str,
    model: str,
) -> dict[str, str]:
    _require_write_access(request)
    logger.debug(
        f"Delete variant: name='{name}', branch='{branch}', provider='{provider}', model='{model}'"
    )
    name = _validate_project_name(name)

    if request.state.is_admin:
        project_owner = request.query_params.get("owner")
        if project_owner is None:
            raise HTTPException(
                status_code=400,
                detail="Project owner is required for admin deletion. Use ?owner=username (or ?owner= for legacy projects)",
            )
    else:
        project_owner = request.state.username

    project = await get_project(
        name,
        ai_provider=provider,
        ai_model=model,
        owner=project_owner,
        branch=branch,
    )
    if not project:
        raise HTTPException(status_code=404, detail="Variant not found")

    # Non-admins can only delete variants they own
    if (
        not request.state.is_admin
        and str(project.get("owner", "")) != request.state.username
    ):
        raise HTTPException(status_code=404, detail="Variant not found")

    # Hold _gen_lock for the entire check+delete to prevent TOCTOU race
    dir_to_delete: Path | None = None
    async with _gen_lock:
        # Check for active generation scoped to the target owner
        # Key format: "owner/name/branch/provider/model"
        for key in _generating:
            parts = key.split("/", 4)
            if (
                len(parts) == 5
                and parts[0] == project_owner
                and parts[1] == name
                and parts[2] == branch
                and parts[3] == provider
                and parts[4] == model
            ):
                raise HTTPException(
                    status_code=409,
                    detail=f"Cannot delete '{name}/{provider}/{model}' while generation is in progress. Abort first.",
                )

        deleted = await delete_project(
            name,
            ai_provider=provider,
            ai_model=model,
            owner=project_owner,
            branch=branch,
        )
        if not deleted:
            raise HTTPException(status_code=404, detail="Variant not found")

        # Rename to tombstone while still holding the lock so a new
        # generation cannot recreate the directory before we delete it.
        project_dir = get_project_dir(
            name, provider, model, project_owner, branch=branch
        )
        if project_dir.exists():
            tombstone = project_dir.with_name(
                f"{project_dir.name}.deleting-{uuid4().hex}"
            )
            project_dir.replace(tombstone)
            dir_to_delete = tombstone

    # Filesystem cleanup outside lock to reduce contention
    if dir_to_delete is not None:
        await asyncio.to_thread(shutil.rmtree, dir_to_delete)
    await notify_sync()
    return {"deleted": f"{name}/{branch}/{provider}/{model}"}


@router.post("/projects/{name}/abort")
async def abort_generation(request: Request, name: str) -> dict[str, str]:
    """Abort generation for any variant of the given project name.

    Convenience API for clients/CLI. Finds the first active generation
    matching the project name.
    """
    _require_write_access(request)
    name = _validate_project_name(name)
    # Find active generation keys matching this project name
    # Key format: "owner/name/branch/provider/model"
    async with _gen_lock:
        matching_keys = [
            key
            for key in _generating
            if len(key.split("/", 4)) == 5 and key.split("/", 4)[1] == name
        ]

        if not request.state.is_admin:
            # Non-admin users can only abort their own generation tasks
            matching_keys = [
                key
                for key in matching_keys
                if key.split("/", 4)[0] == request.state.username
            ]
            if not matching_keys:
                raise HTTPException(
                    status_code=404, detail=f"No active generation for '{name}'"
                )

        if len(matching_keys) > 1:
            raise HTTPException(
                status_code=409,
                detail="Multiple active variants found; use the branch-specific abort endpoint.",
            )

        matching_key = matching_keys[0] if matching_keys else None
        task = _generating.get(matching_key) if matching_key else None
    if not task or not matching_key:
        raise HTTPException(
            status_code=404, detail=f"No active generation for '{name}'"
        )

    # Extract owner/name/branch/provider/model from the key
    parts = matching_key.split("/", 4)
    if len(parts) != 5:
        raise HTTPException(status_code=500, detail="Invalid generation key format")
    key_owner, _, key_branch, ai_provider, ai_model = parts
    resolved_branch = key_branch

    # Check ownership before allowing abort
    project = await get_project(
        name,
        ai_provider=ai_provider,
        ai_model=ai_model,
        owner=key_owner,
        branch=resolved_branch,
    )
    if project:
        await _check_ownership(request, name, project)

    if not task.cancel():
        raise HTTPException(
            status_code=409,
            detail=f"Generation for '{name}' already finished. Refresh status and retry only if needed.",
        )
    try:
        await asyncio.wait_for(task, timeout=_ABORT_TIMEOUT)
    except asyncio.CancelledError:
        pass  # expected cancellation acknowledgment
    except TimeoutError as exc:
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

    abort_gen_key = f"{key_owner}/{name}/{resolved_branch}/{ai_provider}/{ai_model}"
    await update_and_notify(
        abort_gen_key,
        name,
        ai_provider,
        ai_model,
        status="aborted",
        owner=key_owner,
        branch=resolved_branch,
        error_message="Generation aborted by user",
        current_stage=None,
    )
    # Note: _generating cleanup is handled by _run_generation's finally block.
    # An extra pop() here could race with a new generation that reuses the key.

    return {"aborted": name}


@router.post("/projects/{name}/{branch}/{provider}/{model}/abort")
async def abort_variant(
    request: Request, name: str, branch: str, provider: str, model: str
) -> dict[str, str]:
    _require_write_access(request)
    logger.debug(
        f"Abort variant: name='{name}', branch='{branch}', provider='{provider}', model='{model}'"
    )
    name = _validate_project_name(name)
    owner = request.state.username
    gen_key = f"{owner}/{name}/{branch}/{provider}/{model}"
    task = _generating.get(gen_key)
    if not task:
        # Also check if an admin is aborting someone else's generation
        if request.state.is_admin:
            admin_matches = [
                key
                for key in _generating
                if len(key.split("/", 4)) == 5
                and key.split("/", 4)[1] == name
                and key.split("/", 4)[2] == branch
                and key.split("/", 4)[3] == provider
                and key.split("/", 4)[4] == model
            ]
            requested_owner = request.query_params.get("owner")
            if requested_owner is not None:
                admin_matches = [
                    k for k in admin_matches if k.split("/", 4)[0] == requested_owner
                ]
            if len(admin_matches) > 1:
                distinct_owners = {k.split("/", 4)[0] for k in admin_matches}
                if len(distinct_owners) > 1:
                    raise HTTPException(
                        status_code=409,
                        detail="Multiple owners found for this variant, please specify owner",
                    )
            if admin_matches:
                gen_key = admin_matches[0]
                task = _generating[gen_key]
        if not task:
            raise HTTPException(
                status_code=404,
                detail="No active generation for this variant",
            )

    # Check ownership before allowing abort
    key_parts = gen_key.split("/", 4)
    key_owner = key_parts[0] if len(key_parts) == 5 else owner
    project = await get_project(
        name,
        ai_provider=provider,
        ai_model=model,
        owner=key_owner,
        branch=branch,
    )
    if project:
        await _check_ownership(request, name, project)

    if not task.cancel():
        raise HTTPException(
            status_code=409,
            detail=f"Generation for '{gen_key}' already finished. Refresh status and retry only if needed.",
        )
    try:
        await asyncio.wait_for(task, timeout=_ABORT_TIMEOUT)
    except asyncio.CancelledError:
        pass
    except TimeoutError as exc:
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

    await update_and_notify(
        gen_key,
        name,
        provider,
        model,
        status="aborted",
        owner=key_owner,
        branch=branch,
        error_message="Generation aborted by user",
        current_stage=None,
    )
    # Note: _generating cleanup is handled by _run_generation's finally block.
    # An extra pop() here could race with a new generation that reuses the key.

    return {"aborted": f"{name}/{branch}/{provider}/{model}"}


@router.get("/projects/{name}/{branch}/{provider}/{model}/download")
async def download_variant(
    request: Request,
    name: str,
    branch: str,
    provider: str,
    model: str,
) -> StreamingResponse:
    logger.debug(
        f"Download variant: name='{name}', branch='{branch}', provider='{provider}', model='{model}'"
    )
    name = _validate_project_name(name)
    project = await _resolve_project(
        request,
        name,
        ai_provider=provider,
        ai_model=model,
        branch=branch,
    )

    if project["status"] != "ready":
        raise HTTPException(status_code=400, detail="Variant not ready")
    project_owner = str(project.get("owner", ""))
    site_dir = get_project_site_dir(name, provider, model, project_owner, branch=branch)
    if not site_dir.exists():
        raise HTTPException(status_code=404, detail="Site not found")
    return await _stream_tarball(site_dir, f"{name}-{branch}-{provider}-{model}")


@router.delete("/projects/{name}")
async def delete_project_endpoint(request: Request, name: str) -> dict[str, str]:
    _require_write_access(request)
    logger.debug(f"Delete all variants: name='{name}'")
    name = _validate_project_name(name)
    if request.state.is_admin:
        owner = request.query_params.get("owner")
        if owner is None:
            raise HTTPException(
                status_code=400,
                detail="Project owner is required for admin deletion. Use ?owner=username (or ?owner= for legacy projects)",
            )
    else:
        owner = request.state.username
    variants = await list_variants(name, owner=owner)
    if not variants:
        raise HTTPException(status_code=404, detail=f"Project '{name}' not found")

    # Hold _gen_lock for the entire check+delete to prevent TOCTOU race
    dirs_to_delete: list[Path] = []
    async with _gen_lock:
        # Check if any variant owned by the target owner(s) is generating
        target_owners = {str(v.get("owner", "")) for v in variants}
        for gen_key in _generating:
            parts = gen_key.split("/", 4)
            if len(parts) == 5 and parts[0] in target_owners and parts[1] == name:
                raise HTTPException(
                    status_code=409,
                    detail=f"Cannot delete '{name}' while generation is in progress. Abort running variants first.",
                )
        for v in variants:
            v_provider = str(v.get("ai_provider", ""))
            v_model = str(v.get("ai_model", ""))
            v_owner = str(v.get("owner", ""))
            v_branch = str(v.get("branch", DEFAULT_BRANCH))
            await delete_project(
                name,
                ai_provider=v_provider,
                ai_model=v_model,
                owner=v_owner,
                branch=v_branch,
            )
            # Rename to tombstone while still holding the lock so a new
            # generation cannot recreate the directory before we delete it.
            project_dir = get_project_dir(
                name, v_provider, v_model, v_owner, branch=v_branch
            )
            if project_dir.exists():
                tombstone = project_dir.with_name(
                    f"{project_dir.name}.deleting-{uuid4().hex}"
                )
                project_dir.replace(tombstone)
                dirs_to_delete.append(tombstone)

    # Filesystem cleanup outside lock to reduce contention
    for d in dirs_to_delete:
        await asyncio.to_thread(shutil.rmtree, d)
    await notify_sync()
    return {"deleted": name}


@router.get("/projects/{name}/download")
async def download_project(request: Request, name: str) -> StreamingResponse:
    name = _validate_project_name(name)
    if request.state.is_admin:
        latest = await get_latest_variant(name)
    else:
        latest = await _resolve_latest_accessible_variant(request.state.username, name)
    if not latest:
        raise HTTPException(status_code=404, detail=f"No ready variant for '{name}'")
    await _check_ownership(request, name, latest)
    provider = str(latest.get("ai_provider", ""))
    model = str(latest.get("ai_model", ""))
    latest_owner = str(latest.get("owner", ""))
    latest_branch = str(latest.get("branch", DEFAULT_BRANCH))
    site_dir = get_project_site_dir(
        name, provider, model, latest_owner, branch=latest_branch
    )
    if not site_dir.exists():
        raise HTTPException(
            status_code=404, detail=f"Site directory not found for '{name}'"
        )
    return await _stream_tarball(site_dir, name)
