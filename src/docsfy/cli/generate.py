from __future__ import annotations

import json
from typing import Any, Optional
from urllib.parse import urlencode

import typer
import websockets.sync.client

from docsfy.cli.config_cmd import resolve_connection

_WS_CLOSE_TIMEOUT = 5


def _watch_progress(
    server_url: str,
    password: str,
    project_name: str,
    branch: str,
    provider: str,
    model: str,
) -> None:
    """Connect to the WebSocket and stream generation progress to stderr."""
    # Build ws:// or wss:// URL from the server URL
    ws_url = (
        server_url.rstrip("/").replace("https://", "wss://").replace("http://", "ws://")
    )
    ws_url = f"{ws_url}/api/ws?{urlencode({'token': password})}"

    typer.echo("Watching generation progress...", err=True)

    try:
        with websockets.sync.client.connect(
            ws_url, close_timeout=_WS_CLOSE_TIMEOUT
        ) as ws:
            while True:
                try:
                    raw = ws.recv(timeout=300)
                except TimeoutError:
                    typer.echo("Timed out waiting for progress update.", err=True)
                    raise typer.Exit(code=1)

                try:
                    msg = json.loads(raw)
                except (json.JSONDecodeError, TypeError):
                    continue

                msg_type = msg.get("type", "")

                # Respond to server pings
                if msg_type == "ping":
                    ws.send(json.dumps({"type": "pong"}))
                    continue

                # Sync messages carry a full project list, not per-variant
                # fields, so skip the name/branch/provider/model filter.
                if msg_type == "sync":
                    for proj in msg.get("projects", []):
                        if (
                            proj.get("name") == project_name
                            and proj.get("branch") == branch
                            and proj.get("ai_provider") == provider
                            and proj.get("ai_model") == model
                        ):
                            proj_status = proj.get("status", "")
                            if proj_status == "ready":
                                pc = proj.get("page_count")
                                pm = f" ({pc} pages)" if pc else ""
                                typer.echo(
                                    f"Generation complete!{pm}",
                                    err=True,
                                )
                                return
                            elif proj_status in ("error", "aborted"):
                                err_msg = proj.get("error_message", "")
                                typer.echo(
                                    f"Generation {proj_status}: {err_msg}",
                                    err=True,
                                )
                                raise typer.Exit(code=1)
                    continue

                # Only process progress/status messages for our project/variant
                msg_name = msg.get("name") or msg.get("project")
                if msg_name != project_name:
                    continue
                if msg.get("branch") != branch:
                    continue
                # Also filter by provider/model when present
                if msg.get("provider") and msg.get("provider") != provider:
                    continue
                if msg.get("model") and msg.get("model") != model:
                    continue

                if msg_type == "progress":
                    stage = msg.get("current_stage", "")
                    page_count = msg.get("page_count")
                    status = msg.get("status", "")
                    parts = [f"[{status}]"]
                    if stage:
                        parts.append(stage)
                    if page_count is not None:
                        parts.append(f"({page_count} pages)")
                    typer.echo(" ".join(parts), err=True)

                elif msg_type == "status_change":
                    status = msg.get("status", "")
                    error = msg.get("error_message")
                    page_count = msg.get("page_count")
                    if status == "ready":
                        pages_msg = f" ({page_count} pages)" if page_count else ""
                        typer.echo(
                            f"Generation complete!{pages_msg}",
                            err=True,
                        )
                        return
                    elif status == "error":
                        typer.echo(
                            f"Generation failed: {error or 'unknown error'}",
                            err=True,
                        )
                        raise typer.Exit(code=1)
                    elif status == "aborted":
                        typer.echo("Generation was aborted.", err=True)
                        raise typer.Exit(code=1)
                    else:
                        typer.echo(f"Status: {status}", err=True)

    except websockets.exceptions.ConnectionClosed:
        typer.echo("WebSocket connection closed unexpectedly.", err=True)
        raise typer.Exit(code=1)
    except OSError as exc:
        typer.echo(f"WebSocket connection failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc


def generate(
    repo_url: str = typer.Argument(help="Git repository URL"),  # noqa: M511
    branch: str = typer.Option("main", "--branch", "-b", help="Git branch"),  # noqa: M511
    provider: Optional[str] = typer.Option(  # noqa: M511
        None, "--provider", help="AI provider (claude, gemini, cursor)"
    ),
    model: Optional[str] = typer.Option(None, "--model", "-m", help="AI model name"),  # noqa: M511
    force: bool = typer.Option(False, "--force", "-f", help="Force full regeneration"),  # noqa: M511
    watch: bool = typer.Option(  # noqa: M511
        False, "--watch", "-w", help="Watch generation progress via WebSocket"
    ),
) -> None:
    """Generate documentation for a Git repository."""
    from docsfy.cli.main import _state, get_client

    client = get_client()
    try:
        payload: dict[str, Any] = {
            "repo_url": repo_url,
            "branch": branch,
            "force": force,
        }
        if provider:
            payload["ai_provider"] = provider
        if model:
            payload["ai_model"] = model

        response = client.post("/api/generate", json=payload)
        data = response.json()
        project_name = data.get("project", "")
        status = data.get("status", "")
        result_branch = data.get("branch", branch)

        typer.echo(f"Project: {project_name}")
        typer.echo(f"Branch: {result_branch}")
        typer.echo(f"Status: {status}")

        if watch and status == "generating":
            srv_url, _, srv_pw = resolve_connection(
                server=_state.get("server"),
                host=_state.get("host"),
                port=_state.get("port"),
                username=_state.get("username"),
                password=_state.get("password"),
            )
            # Determine the actual provider/model used (server defaults may apply)
            actual_provider = provider or ""
            actual_model = model or ""
            if not actual_provider or not actual_model:
                # Fetch the variant details to get actual provider/model
                try:
                    detail_resp = client.get(
                        f"/api/projects/{project_name}/{result_branch}/{actual_provider or '_'}/{actual_model or '_'}"
                    )
                    detail = detail_resp.json()
                    actual_provider = actual_provider or str(
                        detail.get("ai_provider", "")
                    )
                    actual_model = actual_model or str(detail.get("ai_model", ""))
                except (typer.Exit, Exception) as exc:
                    # If we can't fetch details, try watching anyway
                    typer.echo(
                        f"Warning: could not fetch variant details: {exc}",
                        err=True,
                    )

            # If we still don't have provider/model, get from status endpoint
            if not actual_provider or not actual_model:
                try:
                    status_resp = client.get("/api/status")
                    status_data = status_resp.json()
                    for proj in status_data.get("projects", []):
                        if (
                            proj.get("name") == project_name
                            and proj.get("branch") == result_branch
                            and proj.get("status") == "generating"
                        ):
                            actual_provider = actual_provider or str(
                                proj.get("ai_provider", "")
                            )
                            actual_model = actual_model or str(proj.get("ai_model", ""))
                            break
                except (typer.Exit, Exception) as exc:
                    typer.echo(
                        f"Warning: could not fetch status details: {exc}",
                        err=True,
                    )

            if actual_provider and actual_model:
                _watch_progress(
                    srv_url,
                    srv_pw,
                    project_name,
                    result_branch,
                    actual_provider,
                    actual_model,
                )
            else:
                typer.echo(
                    "Cannot determine provider/model for --watch. "
                    "Check status with: docsfy status <project>",
                    err=True,
                )
    finally:
        client.close()
