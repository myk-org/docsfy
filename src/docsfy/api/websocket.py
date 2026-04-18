from __future__ import annotations

import asyncio
import hmac
import json
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from simple_logger.logger import get_logger

from docsfy.config import get_settings
from docsfy.storage import (
    get_session,
    get_user_by_key,
    get_user_by_username,
)

logger = get_logger(name=__name__)

router = APIRouter()

_WS_HEARTBEAT_INTERVAL = 30
_WS_PONG_TIMEOUT = 10
_WS_MAX_MISSED_PONGS = 2

# Connection registry: username -> set of (websocket, is_admin, role).
# Thread-safety note: this dict is only accessed from coroutines running in
# FastAPI's single asyncio event loop, so no additional locking is needed.
_connections: dict[str, set[tuple[WebSocket, bool, str]]] = {}


async def _get_projects_for_user(username: str, is_admin: bool) -> dict[str, Any]:
    """Build a sync payload for the given user.

    Delegates to the shared ``build_projects_payload`` helper in
    ``docsfy.api.projects`` so the REST and WebSocket paths stay in sync.
    """
    from docsfy.api.projects import build_projects_payload

    return await build_projects_payload(username, is_admin)


async def _authenticate_ws(
    websocket: WebSocket,
) -> tuple[str, bool, str] | None:
    """Authenticate WebSocket via query param ``?token=`` (Bearer) or session cookie.

    Returns ``(username, is_admin, role)`` on success, ``None`` on failure.
    """
    settings = get_settings()

    # 1. Check ?token= query param (treated as Bearer token)
    token = websocket.query_params.get("token")
    if token:
        if hmac.compare_digest(token, settings.admin_key):
            return ("admin", True, "admin")

        user = await get_user_by_key(token)
        if user:
            username = str(user["username"])
            role = str(user.get("role", "user"))
            is_admin = role == "admin"
            return (username, is_admin, role)

    # 2. Check session cookie
    session_token = websocket.cookies.get("docsfy_session")
    if session_token:
        session = await get_session(session_token)
        if session:
            is_admin = bool(session["is_admin"])
            username = str(session["username"])
            role = "admin" if is_admin else "user"

            # For DB users (not ADMIN_KEY admin), verify user still exists
            # and refresh role from DB (handles promotions AND demotions)
            if username != "admin":
                user = await get_user_by_username(username)
                if not user:
                    return None
                role = str(user.get("role", "user"))
                is_admin = role == "admin"

            return (username, is_admin, role)

    return None


async def _heartbeat(websocket: WebSocket) -> None:
    """Send periodic pings and close the connection after too many missed pongs."""
    missed_pongs = 0
    while True:
        await asyncio.sleep(_WS_HEARTBEAT_INTERVAL)
        try:
            await websocket.send_json({"type": "ping"})
        except Exception:
            logger.debug("WebSocket heartbeat send failed, stopping heartbeat")
            return

        # Wait for pong
        try:
            pong_received = asyncio.Event()

            # Store the event on the websocket so the message loop can set it
            websocket.state.pong_event = pong_received

            try:
                await asyncio.wait_for(pong_received.wait(), timeout=_WS_PONG_TIMEOUT)
                missed_pongs = 0
            except TimeoutError:
                missed_pongs += 1
                logger.debug(
                    f"WebSocket missed pong ({missed_pongs}/{_WS_MAX_MISSED_PONGS})"
                )
                if missed_pongs >= _WS_MAX_MISSED_PONGS:
                    logger.info("WebSocket closing due to missed pongs")
                    await websocket.close(code=1001)
                    return
        except Exception:
            logger.debug("WebSocket heartbeat pong-wait failed, stopping heartbeat")
            return


@router.websocket("/api/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """WebSocket endpoint for real-time project updates."""
    auth = await _authenticate_ws(websocket)
    if auth is None:
        logger.debug("WebSocket auth failed, closing with 1008")
        await websocket.close(code=1008)
        return

    username, is_admin, role = auth
    logger.debug(f"WebSocket connected: username='{username}', is_admin={is_admin}")
    await websocket.accept()

    conn_tuple = (websocket, is_admin, role)
    if username not in _connections:
        _connections[username] = set()
    _connections[username].add(conn_tuple)

    heartbeat_task: asyncio.Task[None] | None = None
    try:
        # Send initial sync
        sync_data = await _get_projects_for_user(username, is_admin)
        await websocket.send_json({"type": "sync", **sync_data})

        # Start heartbeat
        heartbeat_task = asyncio.create_task(_heartbeat(websocket))

        # Listen for messages (primarily pong responses)
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                continue

            if msg.get("type") == "pong":
                logger.debug(f"WebSocket pong received from '{username}'")
                pong_event = getattr(websocket.state, "pong_event", None)
                if pong_event is not None:
                    pong_event.set()

    except WebSocketDisconnect:
        logger.debug(f"WebSocket disconnected: username='{username}'")
    except Exception as exc:
        logger.debug(f"WebSocket error for {username}: {exc}")
    finally:
        if heartbeat_task is not None:
            heartbeat_task.cancel()
            try:
                await heartbeat_task
            except (asyncio.CancelledError, Exception):
                pass

        conns = _connections.get(username)
        if conns is not None:
            conns.discard(conn_tuple)
            if not conns:
                del _connections[username]


async def _broadcast_to_relevant(
    message: dict[str, Any],
    owner: str,
    project_name: str,
) -> None:
    """Send a message to admins, the project owner, and users with access."""
    from docsfy.storage import get_project_access

    checked_users: set[str] = set()
    # Cache the access list once -- it is the same for every user in the loop.
    access_list: list[str] | None = None

    for username, conns in list(_connections.items()):
        # Determine once per user whether they should receive messages
        if username not in checked_users:
            checked_users.add(username)
            # Check if any connection is admin, or user is owner
            user_is_admin = any(ws_admin for _, ws_admin, _ in conns)
            should_send_user = user_is_admin or username == owner
            if not should_send_user:
                if access_list is None:
                    access_list = await get_project_access(
                        project_name, project_owner=owner
                    )
                should_send_user = username in access_list
        else:
            should_send_user = True  # already checked

        if should_send_user:
            for ws, _ws_is_admin, _role in list(conns):
                try:
                    await ws.send_json(message)
                except Exception:
                    logger.debug(f"WebSocket broadcast failed for user '{username}'")


async def notify_progress(
    gen_key: str,
    status: str,
    current_stage: str | None = None,
    page_count: int | None = None,
    plan_json: str | None = None,
    error_message: str | None = None,
    generation_id: str | None = None,
) -> None:
    """Send a progress update for an in-progress generation."""
    # gen_key format: "owner/name/branch/provider/model"
    parts = gen_key.split("/", 4)
    if len(parts) != 5:
        return
    owner, project_name, branch, provider, model = parts
    logger.debug(
        f"WS notify progress: name='{project_name}', status='{status}', stage='{current_stage}'"
    )

    message: dict[str, Any] = {
        "type": "progress",
        "name": project_name,
        "branch": branch,
        "provider": provider,
        "model": model,
        "owner": owner,
        "status": status,
    }
    if generation_id:
        message["generation_id"] = generation_id
    if current_stage is not None:
        message["current_stage"] = current_stage
    if page_count is not None:
        message["page_count"] = page_count
    if plan_json is not None:
        message["plan_json"] = plan_json
    if error_message is not None:
        message["error_message"] = error_message

    await _broadcast_to_relevant(message, owner, project_name)


async def notify_status_change(
    gen_key: str,
    status: str,
    page_count: int | None = None,
    last_generated: str | None = None,
    last_commit_sha: str | None = None,
    error_message: str | None = None,
    generation_id: str | None = None,
) -> None:
    """Send a status change notification (for terminal states)."""
    parts = gen_key.split("/", 4)
    if len(parts) != 5:
        return
    owner, project_name, branch, provider, model = parts
    logger.debug(f"WS notify status_change: name='{project_name}', status='{status}'")

    message: dict[str, Any] = {
        "type": "status_change",
        "name": project_name,
        "branch": branch,
        "provider": provider,
        "model": model,
        "owner": owner,
        "status": status,
    }
    if generation_id:
        message["generation_id"] = generation_id
    if page_count is not None:
        message["page_count"] = page_count
    if last_generated is not None:
        message["last_generated"] = last_generated
    if last_commit_sha is not None:
        message["last_commit_sha"] = last_commit_sha
    if error_message is not None:
        message["error_message"] = error_message

    await _broadcast_to_relevant(message, owner, project_name)


async def _send_sync_to_connections(
    target_username: str, conns: set[tuple[WebSocket, bool, str]]
) -> None:
    """Send a full sync payload to all connections for a given user."""
    for ws, ws_is_admin, _role in list(conns):
        try:
            sync_data = await _get_projects_for_user(target_username, ws_is_admin)
            await ws.send_json({"type": "sync", **sync_data})
        except Exception:
            logger.debug(f"WebSocket sync send failed for user '{target_username}'")


async def notify_sync(username: str | None = None) -> None:
    """Send a full sync to one user or all connected users."""
    if username is not None:
        conns = _connections.get(username)
        if not conns:
            return
        await _send_sync_to_connections(username, conns)
    else:
        for uname, conns in list(_connections.items()):
            await _send_sync_to_connections(uname, conns)


async def notify_access_change(username: str) -> None:
    """Re-send sync after a user's access has changed."""
    await notify_sync(username=username)
