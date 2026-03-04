from __future__ import annotations

import asyncio
import json
import os
import shutil
import tarfile
import tempfile
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from io import BytesIO
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from simple_logger.logger import get_logger

from docsfy.ai_client import check_ai_cli_available
from docsfy.config import get_settings
from docsfy.generator import generate_all_pages, run_planner
from docsfy.models import GenerateRequest
from docsfy.repository import clone_repo
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

    await save_project(
        name=project_name, repo_url=request.repo_url, status="generating"
    )

    asyncio.create_task(
        _run_generation(
            repo_url=request.repo_url,
            project_name=project_name,
            ai_provider=ai_provider,
            ai_model=ai_model,
            ai_cli_timeout=request.ai_cli_timeout or settings.ai_cli_timeout,
        )
    )

    return {"project": project_name, "status": "generating"}


async def _run_generation(
    repo_url: str,
    project_name: str,
    ai_provider: str,
    ai_model: str,
    ai_cli_timeout: int,
) -> None:
    try:
        available, msg = await check_ai_cli_available(ai_provider, ai_model)
        if not available:
            await update_project_status(project_name, status="error", error_message=msg)
            return

        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_path, commit_sha = await asyncio.to_thread(
                clone_repo, repo_url, Path(tmp_dir)
            )

            existing = await get_project(project_name)
            if (
                existing
                and existing.get("last_commit_sha") == commit_sha
                and existing.get("status") == "ready"
            ):
                logger.info(f"Project {project_name} is up to date at {commit_sha[:8]}")
                return

            plan = await run_planner(
                repo_path=repo_path,
                project_name=project_name,
                ai_provider=ai_provider,
                ai_model=ai_model,
                ai_cli_timeout=ai_cli_timeout,
            )

            cache_dir = get_project_cache_dir(project_name)
            pages = await generate_all_pages(
                repo_path=repo_path,
                plan=plan,
                cache_dir=cache_dir,
                ai_provider=ai_provider,
                ai_model=ai_model,
                ai_cli_timeout=ai_cli_timeout,
            )

        site_dir = get_project_site_dir(project_name)
        render_site(plan=plan, pages=pages, output_dir=site_dir)

        project_dir = get_project_dir(project_name)
        (project_dir / "plan.json").write_text(json.dumps(plan, indent=2))

        page_count = len(pages)
        await update_project_status(
            project_name,
            status="ready",
            last_commit_sha=commit_sha,
            page_count=page_count,
            plan_json=json.dumps(plan),
        )
        logger.info(f"Documentation for {project_name} is ready ({page_count} pages)")

    except Exception as exc:
        logger.error(f"Generation failed for {project_name}: {exc}")
        await update_project_status(
            project_name, status="error", error_message=str(exc)
        )


@app.get("/api/projects/{name}")
async def get_project_details(name: str) -> dict[str, str | int | None]:
    project = await get_project(name)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project '{name}' not found")
    return project


@app.delete("/api/projects/{name}")
async def delete_project_endpoint(name: str) -> dict[str, str]:
    deleted = await delete_project(name)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Project '{name}' not found")
    project_dir = get_project_dir(name)
    if project_dir.exists():
        shutil.rmtree(project_dir)
    return {"deleted": name}


@app.get("/api/projects/{name}/download")
async def download_project(name: str) -> StreamingResponse:
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
    buffer = BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
        tar.add(str(site_dir), arcname=name)
    buffer.seek(0)
    return StreamingResponse(
        buffer,
        media_type="application/gzip",
        headers={"Content-Disposition": f"attachment; filename={name}-docs.tar.gz"},
    )


@app.get("/docs/{project}/{path:path}")
async def serve_docs(project: str, path: str = "index.html") -> FileResponse:
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
    uvicorn.run("docsfy.main:app", host="0.0.0.0", port=8000, reload=reload)
