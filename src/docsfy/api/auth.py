from __future__ import annotations

import hmac
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from simple_logger.logger import get_logger
from starlette.responses import JSONResponse

from docsfy.config import get_settings
from docsfy.storage import (
    SESSION_TTL_SECONDS,
    create_session,
    delete_session,
    get_user_by_key,
    rotate_user_key,
)

logger = get_logger(name=__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login")
async def login(request: Request) -> JSONResponse:
    """Authenticate with JSON {username, api_key} and return user info + session cookie."""
    try:
        body = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON body") from exc
    if not isinstance(body, dict):
        raise HTTPException(
            status_code=400, detail="Request body must be a JSON object"
        )
    username = str(body.get("username", ""))
    api_key = str(body.get("api_key", ""))
    settings = get_settings()
    safe_username = username.replace("\n", "").replace("\r", "")[:100]

    logger.debug(f"Login attempt for username '{safe_username}'")

    is_admin = False
    authenticated = False
    role = "user"

    # Check admin -- username must be "admin" and key must match
    if username == "admin" and hmac.compare_digest(api_key, settings.admin_key):
        is_admin = True
        authenticated = True
        role = "admin"
    else:
        # Check user key -- verify username matches the key's owner
        user = await get_user_by_key(api_key)
        if user and user["username"] == username:
            authenticated = True
            role = str(user.get("role", "user"))
            if role == "admin":
                is_admin = True

    if authenticated:
        logger.debug(
            f"Login successful for '{safe_username}', role='{role}', is_admin={is_admin}"
        )
        session_token = await create_session(username, is_admin=is_admin)
        response = JSONResponse(
            content={
                "username": username,
                "role": role,
                "is_admin": is_admin,
            }
        )
        response.set_cookie(
            "docsfy_session",
            session_token,
            httponly=True,
            samesite="strict",
            secure=settings.secure_cookies,
            max_age=SESSION_TTL_SECONDS,
        )
        return response

    logger.info(f"[AUDIT] Failed login attempt for username '{safe_username}'")

    raise HTTPException(status_code=401, detail="Invalid username or password")


@router.post("/logout")
async def logout(request: Request) -> JSONResponse:
    """Clear the session cookie, delete session from DB, and return {ok: true}."""
    logger.debug("Logout request received")
    session_token = request.cookies.get("docsfy_session")
    if session_token:
        await delete_session(session_token)
    settings = get_settings()
    response = JSONResponse(content={"ok": True})
    response.delete_cookie(
        "docsfy_session",
        httponly=True,
        samesite="strict",
        secure=settings.secure_cookies,
    )
    return response


@router.get("/me")
async def me(request: Request) -> JSONResponse:
    """Return current user info from request.state (set by AuthMiddleware)."""
    return JSONResponse(
        content={
            "username": request.state.username,
            "role": request.state.role,
            "is_admin": request.state.is_admin,
        }
    )


@router.post("/rotate-key")
async def rotate_key(request: Request) -> JSONResponse:
    """Rotate the current user's API key. Rejects ADMIN_KEY users."""
    logger.debug(f"Key rotation requested by '{request.state.username}'")
    if request.state.is_admin and not request.state.user:
        raise HTTPException(
            status_code=400,
            detail="ADMIN_KEY users cannot rotate keys. Change the ADMIN_KEY env var instead.",
        )

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
