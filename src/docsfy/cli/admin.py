from __future__ import annotations

import json
from typing import Any, Optional

import typer

from docsfy.cli.formatting import print_table

admin_app = typer.Typer(name="admin", help="Admin commands")
users_app = typer.Typer(name="users", help="Manage users")
access_app = typer.Typer(name="access", help="Manage project access")
admin_app.add_typer(users_app)
admin_app.add_typer(access_app)


# --- Users commands ---


@users_app.command("list")
def users_list(
    output_json: bool = typer.Option(False, "--json", help="Output as JSON"),  # noqa: M511
) -> None:
    """List all users."""
    from docsfy.cli.main import get_client

    client = get_client()
    try:
        response = client.get("/api/admin/users")
        data = response.json()
        users = data.get("users", [])

        if output_json:
            typer.echo(json.dumps(users, indent=2))
            return

        if not users:
            typer.echo("No users found.")
            return

        # Format as table
        headers = ["USERNAME", "ROLE", "CREATED"]
        rows = [
            [
                str(u.get("username", "")),
                str(u.get("role", "user")),
                str(u.get("created_at", ""))[:19],
            ]
            for u in users
        ]

        print_table(headers, rows)
    finally:
        client.close()


@users_app.command("create")
def users_create(
    username: str = typer.Argument(help="Username to create"),  # noqa: M511
    role: str = typer.Option(  # noqa: M511
        "user", "--role", "-r", help="User role (user, viewer, admin)"
    ),
    output_json: bool = typer.Option(False, "--json", help="Output as JSON"),  # noqa: M511
) -> None:
    """Create a new user."""
    from docsfy.cli.main import get_client

    client = get_client()
    try:
        response = client.post(
            "/api/admin/users",
            json={"username": username, "role": role},
        )
        data = response.json()

        if output_json:
            typer.echo(json.dumps(data, indent=2))
            return

        typer.echo(f"User created: {data.get('username', '')}")
        typer.echo(f"Role: {data.get('role', '')}")
        typer.echo(f"API Key: {data.get('api_key', '')}")
        typer.echo("")
        typer.echo("Save this API key -- it will not be shown again.")
    finally:
        client.close()


@users_app.command("delete")
def users_delete(
    username: str = typer.Argument(help="Username to delete"),  # noqa: M511
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),  # noqa: M511
) -> None:
    """Delete a user."""
    if not yes:
        confirmed = typer.confirm(f"Delete user '{username}'?")
        if not confirmed:
            typer.echo("Aborted.")
            raise typer.Exit()

    from docsfy.cli.main import get_client

    client = get_client()
    try:
        client.delete(f"/api/admin/users/{username}")
        typer.echo(f"Deleted user '{username}'.")
    finally:
        client.close()


@users_app.command("rotate-key")
def users_rotate_key(
    username: str = typer.Argument(help="Username whose key to rotate"),  # noqa: M511
    new_key: Optional[str] = typer.Option(  # noqa: M511
        None, "--new-key", help="Custom API key (generated if omitted)"
    ),
    output_json: bool = typer.Option(False, "--json", help="Output as JSON"),  # noqa: M511
) -> None:
    """Rotate a user's API key."""
    from docsfy.cli.main import get_client

    client = get_client()
    try:
        payload: dict[str, Any] = {}
        if new_key:
            payload["new_key"] = new_key
        response = client.post(
            f"/api/admin/users/{username}/rotate-key",
            json=payload,
        )
        data = response.json()

        if output_json:
            typer.echo(json.dumps(data, indent=2))
            return

        typer.echo(f"User: {data.get('username', '')}")
        typer.echo(f"New API Key: {data.get('new_api_key', '')}")
        typer.echo("")
        typer.echo("Save this API key -- it will not be shown again.")
    finally:
        client.close()


# --- Access commands ---


@access_app.command("list")
def access_list(
    project: str = typer.Argument(help="Project name"),  # noqa: M511
    owner: str = typer.Option(..., "--owner", help="Project owner"),  # noqa: M511
    output_json: bool = typer.Option(False, "--json", help="Output as JSON"),  # noqa: M511
) -> None:
    """List users with access to a project."""
    from docsfy.cli.main import get_client

    client = get_client()
    try:
        response = client.get(f"/api/admin/projects/{project}/access", owner=owner)
        data = response.json()

        if output_json:
            typer.echo(json.dumps(data, indent=2))
            return

        users = data.get("users", [])
        typer.echo(f"Project: {data.get('project', project)}")
        typer.echo(f"Owner: {data.get('owner', owner)}")
        if not users:
            typer.echo("No access grants.")
        else:
            typer.echo(f"Users with access: {', '.join(users)}")
    finally:
        client.close()


@access_app.command("grant")
def access_grant(
    project: str = typer.Argument(help="Project name"),  # noqa: M511
    username: str = typer.Option(..., "--username", help="Username to grant access"),  # noqa: M511
    owner: str = typer.Option(..., "--owner", help="Project owner"),  # noqa: M511
) -> None:
    """Grant a user access to a project."""
    from docsfy.cli.main import get_client

    client = get_client()
    try:
        client.post(
            f"/api/admin/projects/{project}/access",
            json={"username": username, "owner": owner},
        )
        typer.echo(f"Granted '{username}' access to '{project}' (owner: {owner}).")
    finally:
        client.close()


@access_app.command("revoke")
def access_revoke(
    project: str = typer.Argument(help="Project name"),  # noqa: M511
    username: str = typer.Option(..., "--username", help="Username to revoke access"),  # noqa: M511
    owner: str = typer.Option(..., "--owner", help="Project owner"),  # noqa: M511
) -> None:
    """Revoke a user's access to a project."""
    from docsfy.cli.main import get_client

    client = get_client()
    try:
        client.delete(f"/api/admin/projects/{project}/access/{username}", owner=owner)
        typer.echo(f"Revoked '{username}' access to '{project}' (owner: {owner}).")
    finally:
        client.close()
