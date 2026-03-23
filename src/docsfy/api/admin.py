from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from simple_logger.logger import get_logger
from starlette.responses import JSONResponse

from docsfy.api.websocket import notify_access_change
from docsfy.storage import (
    create_user,
    delete_user,
    get_project_access,
    get_user_by_username,
    grant_project_access,
    list_users,
    list_variants,
    revoke_project_access,
    rotate_user_key,
)

logger = get_logger(name=__name__)

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _require_admin(request: Request) -> None:
    """Raise 403 if the user is not an admin."""
    if not request.state.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")


@router.post("/users")
async def create_user_endpoint(request: Request) -> JSONResponse:
    """Create a new user and return the generated API key."""
    _require_admin(request)
    try:
        body = await request.json()
    except Exception as exc:
        raise HTTPException(
            status_code=400, detail="Malformed JSON in request body"
        ) from exc
    if not isinstance(body, dict):
        raise HTTPException(
            status_code=400, detail="Request body must be a JSON object"
        )
    username = body.get("username", "")
    role = body.get("role", "user")
    logger.debug(f"User creation requested: username='{username}', role='{role}'")
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


@router.delete("/users/{username}")
async def delete_user_endpoint(request: Request, username: str) -> dict[str, str]:
    """Delete a user by username."""
    _require_admin(request)
    logger.debug(f"User deletion requested: username='{username}'")
    # Fix 13: Prevent admin self-delete
    if username == request.state.username:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")
    # Block deletion while any generation is in progress for this user
    from docsfy.api.projects import _gen_lock, _generating

    async with _gen_lock:
        for gen_key in _generating:
            parts = gen_key.split("/", 4)
            if len(parts) != 5:
                logger.warning(f"Malformed gen_key encountered: '{gen_key}'")
                continue
            if parts[0] == username:
                raise HTTPException(
                    status_code=409,
                    detail="Cannot delete user while generation is in progress",
                )
        deleted = await delete_user(username)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"User '{username}' not found")
    # Fix 18: Audit logging
    logger.info(f"[AUDIT] User '{request.state.username}' deleted user '{username}'")
    return {"deleted": username}


@router.get("/users")
async def list_users_endpoint(
    request: Request,
) -> dict[str, list[dict[str, str | int | None]]]:
    """List all users."""
    _require_admin(request)
    users = await list_users()
    return {"users": users}


@router.post("/projects/{name}/access")
async def grant_access(request: Request, name: str) -> dict[str, str]:
    _require_admin(request)
    try:
        body = await request.json()
    except Exception as exc:
        raise HTTPException(
            status_code=400, detail="Malformed JSON in request body"
        ) from exc
    if not isinstance(body, dict):
        raise HTTPException(
            status_code=400, detail="Request body must be a JSON object"
        )
    username = body.get("username", "")
    project_owner = body.get("owner", "")
    logger.debug(
        f"Access grant requested: project='{name}', username='{username}', owner='{project_owner}'"
    )
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
    await notify_access_change(username)
    logger.info(
        f"[AUDIT] Admin '{request.state.username}' granted '{username}' access to '{name}' (owner: '{project_owner}')"
    )
    return {"granted": name, "username": username, "owner": project_owner}


@router.delete("/projects/{name}/access/{username}")
async def revoke_access(request: Request, name: str, username: str) -> dict[str, str]:
    _require_admin(request)
    logger.debug(f"Access revoke requested: project='{name}', username='{username}'")
    project_owner = request.query_params.get("owner", "")
    if not project_owner:
        raise HTTPException(status_code=400, detail="Project owner is required")
    await revoke_project_access(name, username, project_owner=project_owner)
    await notify_access_change(username)
    logger.info(
        f"[AUDIT] Admin '{request.state.username}' revoked '{username}' access to '{name}' (owner: '{project_owner}')"
    )
    return {"revoked": name, "username": username, "owner": project_owner}


@router.get("/projects/{name}/access")
async def list_access(request: Request, name: str) -> dict[str, Any]:
    _require_admin(request)
    project_owner = request.query_params.get("owner", "")
    if not project_owner:
        raise HTTPException(status_code=400, detail="Project owner is required")
    users = await get_project_access(name, project_owner=project_owner)
    return {"project": name, "owner": project_owner, "users": users}


@router.post("/users/{username}/rotate-key")
async def admin_rotate_key(request: Request, username: str) -> JSONResponse:
    """Admin rotates a user's API key."""
    _require_admin(request)
    body_bytes = await request.body()
    if not body_bytes or body_bytes.strip() == b"":
        body: dict[str, Any] = {}
    else:
        try:
            body = await request.json()
        except Exception as exc:
            raise HTTPException(
                status_code=400, detail="Malformed JSON in request body"
            ) from exc
    if not isinstance(body, dict):
        raise HTTPException(
            status_code=400, detail="Request body must be a JSON object"
        )
    custom_key = body.get("new_key")
    try:
        new_key = await rotate_user_key(username, custom_key=custom_key)
    except ValueError as exc:
        detail = str(exc)
        status = 404 if "not found" in detail.lower() else 400
        raise HTTPException(status_code=status, detail=detail) from exc
    logger.info(
        f"[AUDIT] Admin '{request.state.username}' rotated API key for user '{username}'"
    )
    return JSONResponse(
        content={"username": username, "new_api_key": new_key},
        headers={"Cache-Control": "no-store"},
    )
