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
from fastapi.responses import FileResponse, StreamingResponse
from simple_logger.logger import get_logger

from docsfy.ai_client import check_ai_cli_available
from docsfy.config import get_settings
from docsfy.generator import generate_all_pages, run_planner
from docsfy.models import GenerateRequest
from docsfy.repository import clone_repo, get_local_repo_info
from docsfy.renderer import render_site
from docsfy.storage import (
    delete_project,
    get_project,
    get_project_cache_dir,
    get_project_dir,
    get_project_site_dir,
    init_db,
    list_projects,
    save_project,
    update_project_status,
)

logger = get_logger(name=__name__)

_generating: set[str] = set()


def _validate_project_name(name: str) -> str:
    """Validate project name to prevent path traversal."""
    if not _re.match(r"^[a-zA-Z0-9][a-zA-Z0-9._-]*$", name):
        raise HTTPException(status_code=400, detail=f"Invalid project name: '{name}'")
    return name


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    await init_db()
    yield


app = FastAPI(
    title="docsfy",
    description="AI-powered documentation generator",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/status")
async def status() -> dict[str, Any]:
    projects = await list_projects()
    return {"projects": projects}


@app.post("/api/generate", status_code=202)
async def generate(request: GenerateRequest) -> dict[str, str]:
    settings = get_settings()
    ai_provider = request.ai_provider or settings.ai_provider
    ai_model = request.ai_model or settings.ai_model
    project_name = request.project_name

    if project_name in _generating:
        raise HTTPException(
            status_code=409,
            detail=f"Project '{project_name}' is already being generated",
        )

    _generating.add(project_name)

    await save_project(
        name=project_name,
        repo_url=request.repo_url or request.repo_path or "",
        status="generating",
    )

    try:
        asyncio.create_task(
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
    except Exception:
        _generating.discard(project_name)
        raise

    return {"project": project_name, "status": "generating"}


async def _run_generation(
    repo_url: str | None,
    repo_path: str | None,
    project_name: str,
    ai_provider: str,
    ai_model: str,
    ai_cli_timeout: int,
    force: bool = False,
) -> None:
    try:
        available, msg = await check_ai_cli_available(ai_provider, ai_model)
        if not available:
            await update_project_status(project_name, status="error", error_message=msg)
            return

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
        logger.warning(f"Generation cancelled for {project_name}")
        await update_project_status(
            project_name, status="error", error_message="Generation was cancelled"
        )
        raise
    except Exception as exc:
        logger.error(f"Generation failed for {project_name}: {exc}")
        await update_project_status(
            project_name, status="error", error_message=str(exc)
        )
    finally:
        _generating.discard(project_name)


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
        cache_dir = get_project_cache_dir(project_name)
        if cache_dir.exists():
            shutil.rmtree(cache_dir)
            logger.info(f"Cleared cache for {project_name} (force=True)")
    else:
        existing = await get_project(project_name)
        if (
            existing
            and existing.get("last_commit_sha") == commit_sha
            and existing.get("status") == "ready"
        ):
            logger.info(f"Project {project_name} is up to date at {commit_sha[:8]}")
            await update_project_status(project_name, status="ready")
            return

    plan = await run_planner(
        repo_path=repo_dir,
        project_name=project_name,
        ai_provider=ai_provider,
        ai_model=ai_model,
        ai_cli_timeout=ai_cli_timeout,
    )

    plan["repo_url"] = source_url

    cache_dir = get_project_cache_dir(project_name)
    pages = await generate_all_pages(
        repo_path=repo_dir,
        plan=plan,
        cache_dir=cache_dir,
        ai_provider=ai_provider,
        ai_model=ai_model,
        ai_cli_timeout=ai_cli_timeout,
        use_cache=not force,
    )

    site_dir = get_project_site_dir(project_name)
    render_site(plan=plan, pages=pages, output_dir=site_dir)

    project_dir = get_project_dir(project_name)
    (project_dir / "plan.json").write_text(json.dumps(plan, indent=2), encoding="utf-8")

    page_count = len(pages)
    await update_project_status(
        project_name,
        status="ready",
        last_commit_sha=commit_sha,
        page_count=page_count,
        plan_json=json.dumps(plan),
    )
    logger.info(f"Documentation for {project_name} is ready ({page_count} pages)")


@app.get("/api/projects/{name}")
async def get_project_details(name: str) -> dict[str, str | int | None]:
    name = _validate_project_name(name)
    project = await get_project(name)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project '{name}' not found")
    return project


@app.delete("/api/projects/{name}")
async def delete_project_endpoint(name: str) -> dict[str, str]:
    name = _validate_project_name(name)
    deleted = await delete_project(name)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Project '{name}' not found")
    project_dir = get_project_dir(name)
    if project_dir.exists():
        shutil.rmtree(project_dir)
    return {"deleted": name}


@app.get("/api/projects/{name}/download")
async def download_project(name: str) -> StreamingResponse:
    name = _validate_project_name(name)
    project = await get_project(name)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project '{name}' not found")
    if project["status"] != "ready":
        raise HTTPException(
            status_code=400,
            detail=f"Project '{name}' is not ready (status: {project['status']})",
        )
    site_dir = get_project_site_dir(name)
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


@app.get("/docs/{project}/{path:path}")
async def serve_docs(project: str, path: str = "index.html") -> FileResponse:
    project = _validate_project_name(project)
    if not path or path == "/":
        path = "index.html"
    site_dir = get_project_site_dir(project)
    file_path = site_dir / path
    try:
        file_path.resolve().relative_to(site_dir.resolve())
    except ValueError:
        raise HTTPException(status_code=403, detail="Access denied")
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path)


def run() -> None:
    import uvicorn

    reload = os.getenv("DEBUG", "").lower() == "true"
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("docsfy.main:app", host=host, port=port, reload=reload)
