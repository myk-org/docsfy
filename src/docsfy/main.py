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

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from jinja2 import Environment, FileSystemLoader, select_autoescape
from simple_logger.logger import get_logger

from docsfy.ai_client import check_ai_cli_available
from docsfy.config import get_settings
from docsfy.generator import generate_all_pages, run_planner
from docsfy.models import GenerateRequest
from docsfy.repository import clone_repo, get_local_repo_info
from docsfy.renderer import render_site
from docsfy.storage import (
    delete_project,
    get_known_models,
    get_latest_variant,
    get_project,
    get_project_cache_dir,
    get_project_dir,
    get_project_site_dir,
    init_db,
    list_projects,
    list_variants,
    save_project,
    update_project_status,
)

logger = get_logger(name=__name__)

_generating: dict[str, asyncio.Task[None]] = {}


def _validate_project_name(name: str) -> str:
    """Validate project name to prevent path traversal."""
    if not _re.match(r"^[a-zA-Z0-9][a-zA-Z0-9._-]*$", name):
        raise HTTPException(status_code=400, detail=f"Invalid project name: '{name}'")
    return name


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    _generating.clear()
    await init_db()
    yield


app = FastAPI(
    title="docsfy",
    description="AI-powered documentation generator",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/", response_class=HTMLResponse)
async def dashboard() -> HTMLResponse:
    settings = get_settings()
    projects = await list_projects()
    known_models = await get_known_models()

    # Group by repo name
    grouped: dict[str, list[dict[str, Any]]] = {}
    for p in projects:
        name = str(p["name"])
        if name not in grouped:
            grouped[name] = []
        grouped[name].append(p)

    env = Environment(
        loader=FileSystemLoader(str(Path(__file__).parent / "templates")),
        autoescape=select_autoescape(["html"]),
    )
    template = env.get_template("dashboard.html")
    html = template.render(
        grouped_projects=grouped,
        projects=projects,  # keep for backward compat
        default_provider=settings.ai_provider,
        default_model=settings.ai_model,
        known_models=known_models,
    )
    return HTMLResponse(content=html)


@app.get("/status/{name}/{provider}/{model}", response_class=HTMLResponse)
async def project_status_page(name: str, provider: str, model: str) -> HTMLResponse:
    name = _validate_project_name(name)
    project = await get_project(name, ai_provider=provider, ai_model=model)
    if not project:
        raise HTTPException(status_code=404, detail="Variant not found")

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

    env = Environment(
        loader=FileSystemLoader(str(Path(__file__).parent / "templates")),
        autoescape=select_autoescape(["html"]),
    )
    template = env.get_template("status.html")
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
async def status() -> dict[str, Any]:
    projects = await list_projects()
    known_models = await get_known_models()
    return {"projects": projects, "known_models": known_models}


@app.post("/api/generate", status_code=202)
async def generate(request: GenerateRequest) -> dict[str, str]:
    settings = get_settings()
    ai_provider = request.ai_provider or settings.ai_provider
    ai_model = request.ai_model or settings.ai_model
    project_name = request.project_name

    if ai_provider not in ("claude", "gemini", "cursor"):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid AI provider: '{ai_provider}'. Must be claude, gemini, or cursor.",
        )
    if not ai_model:
        raise HTTPException(status_code=400, detail="AI model must be specified.")

    gen_key = f"{project_name}/{ai_provider}/{ai_model}"
    if gen_key in _generating:
        raise HTTPException(
            status_code=409,
            detail=f"Variant '{gen_key}' is already being generated",
        )

    await save_project(
        name=project_name,
        repo_url=request.repo_url or request.repo_path or "",
        status="generating",
        ai_provider=ai_provider,
        ai_model=ai_model,
    )

    try:
        task = asyncio.create_task(
            _run_generation(
                repo_url=request.repo_url,
                repo_path=request.repo_path,
                project_name=project_name,
                ai_provider=ai_provider,
                ai_model=ai_model,
                ai_cli_timeout=request.ai_cli_timeout or settings.ai_cli_timeout,
                force=request.force,
            )
        )
        _generating[gen_key] = task
    except Exception:
        _generating.pop(gen_key, None)
        raise

    return {"project": project_name, "status": "generating"}


@app.post("/api/projects/{name}/abort")
async def abort_generation(name: str) -> dict[str, str]:
    """Abort generation for any variant of the given project name.

    Kept for backward compatibility. Finds the first active generation
    matching the project name.
    """
    name = _validate_project_name(name)
    # Find any active generation key that starts with this project name
    matching_key = None
    for key in _generating:
        if key.startswith(f"{name}/"):
            matching_key = key
            break
    task = _generating.get(matching_key) if matching_key else None
    if not task or not matching_key:
        raise HTTPException(
            status_code=404, detail=f"No active generation for '{name}'"
        )

    # Extract provider/model from the key
    parts = matching_key.split("/", 2)
    ai_provider = parts[1] if len(parts) > 1 else ""
    ai_model = parts[2] if len(parts) > 2 else ""

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
        error_message="Generation aborted by user",
        current_stage=None,
    )
    _generating.pop(matching_key, None)

    return {"aborted": name}


@app.post("/api/projects/{name}/{provider}/{model}/abort")
async def abort_variant(name: str, provider: str, model: str) -> dict[str, str]:
    name = _validate_project_name(name)
    gen_key = f"{name}/{provider}/{model}"
    task = _generating.get(gen_key)
    if not task:
        raise HTTPException(
            status_code=404,
            detail="No active generation for this variant",
        )

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
        error_message="Generation aborted by user",
        current_stage=None,
    )
    _generating.pop(gen_key, None)

    return {"aborted": gen_key}


async def _run_generation(
    repo_url: str | None,
    repo_path: str | None,
    project_name: str,
    ai_provider: str,
    ai_model: str,
    ai_cli_timeout: int,
    force: bool = False,
) -> None:
    gen_key = f"{project_name}/{ai_provider}/{ai_model}"
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
                error_message=msg,
            )
            return

        await update_project_status(
            project_name,
            ai_provider,
            ai_model,
            status="generating",
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
                )

    except asyncio.CancelledError:
        logger.warning(f"[{project_name}] Generation cancelled")
        await update_project_status(
            project_name,
            ai_provider,
            ai_model,
            status="aborted",
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
) -> None:
    if force:
        cache_dir = get_project_cache_dir(project_name, ai_provider, ai_model)
        if cache_dir.exists():
            shutil.rmtree(cache_dir)
            logger.info(f"[{project_name}] Cleared cache (force=True)")
        # Reset page count so API shows 0 during regeneration
        await update_project_status(
            project_name,
            ai_provider,
            ai_model,
            status="generating",
            page_count=0,
        )
    else:
        existing = await get_project(
            project_name, ai_provider=ai_provider, ai_model=ai_model
        )
        if (
            existing
            and existing.get("last_commit_sha") == commit_sha
            and existing.get("last_generated")  # docs were previously generated
        ):
            logger.info(f"[{project_name}] Project is up to date at {commit_sha[:8]}")
            await update_project_status(
                project_name,
                ai_provider,
                ai_model,
                status="ready",
                current_stage="up_to_date",
            )
            return

    await update_project_status(
        project_name,
        ai_provider,
        ai_model,
        status="generating",
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

    # Store plan so API consumers can see doc structure while pages generate
    await update_project_status(
        project_name,
        ai_provider,
        ai_model,
        status="generating",
        current_stage="generating_pages",
        plan_json=json.dumps(plan),
    )

    cache_dir = get_project_cache_dir(project_name, ai_provider, ai_model)
    pages = await generate_all_pages(
        repo_path=repo_dir,
        plan=plan,
        cache_dir=cache_dir,
        ai_provider=ai_provider,
        ai_model=ai_model,
        ai_cli_timeout=ai_cli_timeout,
        use_cache=not force,
        project_name=project_name,
    )

    await update_project_status(
        project_name,
        ai_provider,
        ai_model,
        status="generating",
        current_stage="rendering",
        page_count=len(pages),
    )

    site_dir = get_project_site_dir(project_name, ai_provider, ai_model)
    render_site(plan=plan, pages=pages, output_dir=site_dir)

    project_dir = get_project_dir(project_name, ai_provider, ai_model)
    (project_dir / "plan.json").write_text(json.dumps(plan, indent=2), encoding="utf-8")

    page_count = len(pages)
    await update_project_status(
        project_name,
        ai_provider,
        ai_model,
        status="ready",
        current_stage=None,
        last_commit_sha=commit_sha,
        page_count=page_count,
        plan_json=json.dumps(plan),
    )
    logger.info(f"[{project_name}] Documentation ready ({page_count} pages)")


@app.get("/api/projects/{name}/{provider}/{model}")
async def get_variant_details(
    name: str,
    provider: str,
    model: str,
) -> dict[str, str | int | None]:
    name = _validate_project_name(name)
    project = await get_project(name, ai_provider=provider, ai_model=model)
    if not project:
        raise HTTPException(status_code=404, detail="Variant not found")
    return project


@app.delete("/api/projects/{name}/{provider}/{model}")
async def delete_variant(
    name: str,
    provider: str,
    model: str,
) -> dict[str, str]:
    name = _validate_project_name(name)
    gen_key = f"{name}/{provider}/{model}"
    if gen_key in _generating:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot delete '{name}/{provider}/{model}' while generation is in progress. Abort first.",
        )
    deleted = await delete_project(name, ai_provider=provider, ai_model=model)
    if not deleted:
        raise HTTPException(status_code=404, detail="Variant not found")
    project_dir = get_project_dir(name, provider, model)
    if project_dir.exists():
        shutil.rmtree(project_dir)
    return {"deleted": f"{name}/{provider}/{model}"}


@app.get("/api/projects/{name}/{provider}/{model}/download")
async def download_variant(
    name: str,
    provider: str,
    model: str,
) -> StreamingResponse:
    name = _validate_project_name(name)
    project = await get_project(name, ai_provider=provider, ai_model=model)
    if not project:
        raise HTTPException(status_code=404, detail="Variant not found")
    if project["status"] != "ready":
        raise HTTPException(status_code=400, detail="Variant not ready")
    site_dir = get_project_site_dir(name, provider, model)
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
            "Content-Disposition": f"attachment; filename={name}-{provider}-{model}-docs.tar.gz"
        },
    )


@app.get("/api/projects/{name}")
async def get_project_details(name: str) -> dict[str, Any]:
    name = _validate_project_name(name)
    variants = await list_variants(name)
    if not variants:
        raise HTTPException(status_code=404, detail=f"Project '{name}' not found")
    return {"name": name, "variants": variants}


@app.delete("/api/projects/{name}")
async def delete_project_endpoint(name: str) -> dict[str, str]:
    name = _validate_project_name(name)
    # Check if any variant is generating
    for gen_key in _generating:
        if gen_key.startswith(f"{name}/"):
            raise HTTPException(
                status_code=409,
                detail=f"Cannot delete '{name}' while generation is in progress. Abort running variants first.",
            )
    variants = await list_variants(name)
    if not variants:
        raise HTTPException(status_code=404, detail=f"Project '{name}' not found")
    for v in variants:
        provider = str(v.get("ai_provider", ""))
        model = str(v.get("ai_model", ""))
        await delete_project(name, ai_provider=provider, ai_model=model)
        project_dir = get_project_dir(name, provider, model)
        if project_dir.exists():
            shutil.rmtree(project_dir)
    return {"deleted": name}


@app.get("/api/projects/{name}/download")
async def download_project(name: str) -> StreamingResponse:
    name = _validate_project_name(name)
    latest = await get_latest_variant(name)
    if not latest:
        raise HTTPException(status_code=404, detail=f"No ready variant for '{name}'")
    provider = str(latest.get("ai_provider", ""))
    model = str(latest.get("ai_model", ""))
    site_dir = get_project_site_dir(name, provider, model)
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
        headers={"Content-Disposition": f"attachment; filename={name}-docs.tar.gz"},
    )


# IMPORTANT: variant-specific route MUST be defined BEFORE the generic route
# so FastAPI matches it first.
@app.get("/docs/{project}/{provider}/{model}/{path:path}")
async def serve_variant_docs(
    project: str,
    provider: str,
    model: str,
    path: str = "index.html",
) -> FileResponse:
    if not path or path == "/":
        path = "index.html"
    project = _validate_project_name(project)
    site_dir = get_project_site_dir(project, provider, model)
    file_path = site_dir / path
    try:
        file_path.resolve().relative_to(site_dir.resolve())
    except ValueError as exc:
        raise HTTPException(status_code=403, detail="Access denied") from exc
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path)


@app.get("/docs/{project}/{path:path}")
async def serve_docs(project: str, path: str = "index.html") -> FileResponse:
    """Serve the most recently generated variant."""
    if not path or path == "/":
        path = "index.html"
    project = _validate_project_name(project)
    latest = await get_latest_variant(project)
    if not latest:
        raise HTTPException(status_code=404, detail="No docs available")
    site_dir = get_project_site_dir(
        project,
        str(latest["ai_provider"]),
        str(latest["ai_model"]),
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
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("docsfy.main:app", host=host, port=port, reload=reload)
