from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import httpx
import pytest
from typer.testing import CliRunner

from docsfy.cli.main import app

runner = CliRunner()


def _make_response(
    status_code: int = 200,
    json_data: dict | list | None = None,
    method: str = "GET",
    url: str = "https://example.com/api/admin/users",
) -> httpx.Response:
    return httpx.Response(
        status_code,
        json=json_data or {},
        request=httpx.Request(method, url),
    )


def _make_mock_client() -> MagicMock:
    """Create a mock DocsfyClient."""
    client = MagicMock()
    client.server_url = "https://example.com"
    client.username = "admin"
    client.password = "test-admin-key"  # pragma: allowlist secret
    return client


@pytest.fixture
def mock_client():
    """Mock get_client to return a fake DocsfyClient."""
    client = _make_mock_client()
    with patch("docsfy.cli.main.get_client", return_value=client):
        yield client


class TestUsersListCommand:
    def test_users_list_empty(self, mock_client: MagicMock) -> None:
        mock_client.get.return_value = _make_response(json_data={"users": []})
        result = runner.invoke(app, ["admin", "users", "list"])
        assert result.exit_code == 0
        assert "No users found" in result.output

    def test_users_list_table(self, mock_client: MagicMock) -> None:
        users = [
            {
                "username": "alice",
                "role": "user",
                "created_at": "2026-01-01T00:00:00",
            },
            {
                "username": "bob",
                "role": "admin",
                "created_at": "2026-01-02T12:00:00",
            },
        ]
        mock_client.get.return_value = _make_response(json_data={"users": users})
        result = runner.invoke(app, ["admin", "users", "list"])
        assert result.exit_code == 0
        assert "alice" in result.output
        assert "bob" in result.output
        assert "admin" in result.output

    def test_users_list_json(self, mock_client: MagicMock) -> None:
        users = [{"username": "alice", "role": "user"}]
        mock_client.get.return_value = _make_response(json_data={"users": users})
        result = runner.invoke(app, ["admin", "users", "list", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 1
        assert data[0]["username"] == "alice"


class TestUsersCreateCommand:
    def test_users_create(self, mock_client: MagicMock) -> None:
        mock_client.post.return_value = _make_response(
            json_data={
                "username": "newuser",
                "api_key": "generated-key-123",  # pragma: allowlist secret
                "role": "user",
            },
            method="POST",
        )
        result = runner.invoke(app, ["admin", "users", "create", "newuser"])
        assert result.exit_code == 0
        assert "newuser" in result.output
        assert "generated-key-123" in result.output
        assert "Save this API key" in result.output

    def test_users_create_admin_role(self, mock_client: MagicMock) -> None:
        mock_client.post.return_value = _make_response(
            json_data={
                "username": "newadmin",
                "api_key": "admin-key-456",  # pragma: allowlist secret
                "role": "admin",
            },
            method="POST",
        )
        result = runner.invoke(
            app,
            ["admin", "users", "create", "newadmin", "--role", "admin"],
        )
        assert result.exit_code == 0
        assert "newadmin" in result.output

    def test_users_create_json(self, mock_client: MagicMock) -> None:
        mock_client.post.return_value = _make_response(
            json_data={
                "username": "newuser",
                "api_key": "key-789",  # pragma: allowlist secret
                "role": "user",
            },
            method="POST",
        )
        result = runner.invoke(app, ["admin", "users", "create", "newuser", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["username"] == "newuser"
        assert data["api_key"] == "key-789"  # pragma: allowlist secret


class TestUsersDeleteCommand:
    def test_users_delete_confirmed(self, mock_client: MagicMock) -> None:
        mock_client.delete.return_value = _make_response(
            json_data={"deleted": "alice"}, method="DELETE"
        )
        result = runner.invoke(app, ["admin", "users", "delete", "alice", "--yes"])
        assert result.exit_code == 0
        assert "Deleted user 'alice'" in result.output

    def test_users_delete_aborted(self, mock_client: MagicMock) -> None:
        result = runner.invoke(app, ["admin", "users", "delete", "alice"], input="n\n")
        assert result.exit_code == 0
        assert "Aborted" in result.output


class TestUsersRotateKeyCommand:
    def test_users_rotate_key(self, mock_client: MagicMock) -> None:
        mock_client.post.return_value = _make_response(
            json_data={
                "username": "alice",
                "new_api_key": "new-key-xyz",  # pragma: allowlist secret
            },
            method="POST",
        )
        result = runner.invoke(app, ["admin", "users", "rotate-key", "alice"])
        assert result.exit_code == 0
        assert "alice" in result.output
        assert "new-key-xyz" in result.output
        assert "Save this API key" in result.output

    def test_users_rotate_key_json(self, mock_client: MagicMock) -> None:
        mock_client.post.return_value = _make_response(
            json_data={
                "username": "alice",
                "new_api_key": "new-key-xyz",  # pragma: allowlist secret
            },
            method="POST",
        )
        result = runner.invoke(app, ["admin", "users", "rotate-key", "alice", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["new_api_key"] == "new-key-xyz"  # pragma: allowlist secret


class TestAccessListCommand:
    def test_access_list(self, mock_client: MagicMock) -> None:
        mock_client.get.return_value = _make_response(
            json_data={
                "project": "my-repo",
                "owner": "admin",
                "users": ["alice", "bob"],
            }
        )
        result = runner.invoke(
            app,
            [
                "admin",
                "access",
                "list",
                "my-repo",
                "--owner",
                "admin",
            ],
        )
        assert result.exit_code == 0
        assert "my-repo" in result.output
        assert "alice" in result.output
        assert "bob" in result.output

    def test_access_list_empty(self, mock_client: MagicMock) -> None:
        mock_client.get.return_value = _make_response(
            json_data={
                "project": "my-repo",
                "owner": "admin",
                "users": [],
            }
        )
        result = runner.invoke(
            app,
            [
                "admin",
                "access",
                "list",
                "my-repo",
                "--owner",
                "admin",
            ],
        )
        assert result.exit_code == 0
        assert "No access grants" in result.output

    def test_access_list_json(self, mock_client: MagicMock) -> None:
        mock_client.get.return_value = _make_response(
            json_data={
                "project": "my-repo",
                "owner": "admin",
                "users": ["alice"],
            }
        )
        result = runner.invoke(
            app,
            [
                "admin",
                "access",
                "list",
                "my-repo",
                "--owner",
                "admin",
                "--json",
            ],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["users"] == ["alice"]


class TestAccessGrantCommand:
    def test_access_grant(self, mock_client: MagicMock) -> None:
        mock_client.post.return_value = _make_response(
            json_data={"granted": "my-repo", "username": "alice", "owner": "admin"},
            method="POST",
        )
        result = runner.invoke(
            app,
            [
                "admin",
                "access",
                "grant",
                "my-repo",
                "--username",
                "alice",
                "--owner",
                "admin",
            ],
        )
        assert result.exit_code == 0
        assert "Granted" in result.output
        assert "alice" in result.output


class TestAccessRevokeCommand:
    def test_access_revoke(self, mock_client: MagicMock) -> None:
        mock_client.delete.return_value = _make_response(
            json_data={"revoked": "my-repo", "username": "alice"},
            method="DELETE",
        )
        result = runner.invoke(
            app,
            [
                "admin",
                "access",
                "revoke",
                "my-repo",
                "--username",
                "alice",
                "--owner",
                "admin",
            ],
        )
        assert result.exit_code == 0
        assert "Revoked" in result.output
        assert "alice" in result.output
