from __future__ import annotations

from pathlib import Path

import pytest


def test_generate_request_valid_https() -> None:
    from docsfy.models import GenerateRequest

    req = GenerateRequest(repo_url="https://github.com/org/repo.git")
    assert req.repo_url == "https://github.com/org/repo.git"


def test_generate_request_valid_ssh() -> None:
    from docsfy.models import GenerateRequest

    req = GenerateRequest(repo_url="git@github.com:org/repo.git")
    assert req.repo_url == "git@github.com:org/repo.git"


def test_generate_request_extracts_project_name() -> None:
    from docsfy.models import GenerateRequest

    req = GenerateRequest(repo_url="https://github.com/org/my-repo.git")
    assert req.project_name == "my-repo"

    req2 = GenerateRequest(repo_url="https://github.com/org/my-repo")
    assert req2.project_name == "my-repo"


def test_generate_request_invalid_url() -> None:
    from docsfy.models import GenerateRequest

    with pytest.raises(Exception):
        GenerateRequest(repo_url="not-a-url")


def test_doc_page_model() -> None:
    from docsfy.models import DocPage

    page = DocPage(slug="intro", title="Introduction", description="Project overview")
    assert page.slug == "intro"


def test_doc_plan_model() -> None:
    from docsfy.models import DocPage, DocPlan, NavGroup

    plan = DocPlan(
        project_name="my-repo",
        tagline="A cool project",
        navigation=[
            NavGroup(
                group="Getting Started",
                pages=[
                    DocPage(slug="intro", title="Introduction", description="Overview")
                ],
            )
        ],
    )
    assert plan.project_name == "my-repo"
    assert len(plan.navigation) == 1
    assert len(plan.navigation[0].pages) == 1


def test_generate_request_local_path(tmp_path: Path) -> None:
    from docsfy.models import GenerateRequest

    # Create a fake git repo
    (tmp_path / ".git").mkdir()
    req = GenerateRequest(repo_path=str(tmp_path))
    assert req.project_name == tmp_path.name


def test_generate_request_requires_source() -> None:
    from docsfy.models import GenerateRequest

    with pytest.raises(Exception):
        GenerateRequest()


def test_generate_request_rejects_both() -> None:
    from docsfy.models import GenerateRequest

    with pytest.raises(Exception):
        GenerateRequest(
            repo_url="https://github.com/org/repo.git", repo_path="/some/path"
        )


def test_generate_request_with_branch() -> None:
    from docsfy.models import GenerateRequest

    req = GenerateRequest(repo_url="https://github.com/org/repo.git", branch="v2.0")
    assert req.branch == "v2.0"


def test_generate_request_branch_defaults_to_main() -> None:
    from docsfy.models import GenerateRequest

    req = GenerateRequest(repo_url="https://github.com/org/repo.git")
    assert req.branch == "main"


def test_generate_request_branch_validation_rejects_traversal() -> None:
    from docsfy.models import GenerateRequest

    with pytest.raises(ValueError, match="Invalid branch"):
        GenerateRequest(
            repo_url="https://github.com/org/repo.git", branch="../etc/passwd"
        )

    with pytest.raises(ValueError, match="Invalid branch"):
        GenerateRequest(repo_url="https://github.com/org/repo.git", branch=".hidden")


def test_generate_request_branch_rejects_slashes() -> None:
    from docsfy.models import GenerateRequest

    with pytest.raises(ValueError, match="Invalid branch"):
        GenerateRequest(
            repo_url="https://github.com/org/repo.git", branch="release/v2.0"
        )


def test_generate_request_branch_allows_dots_and_hyphens() -> None:
    from docsfy.models import GenerateRequest

    req = GenerateRequest(
        repo_url="https://github.com/org/repo.git", branch="release-v2.0"
    )
    assert req.branch == "release-v2.0"
    req2 = GenerateRequest(repo_url="https://github.com/org/repo.git", branch="v2.0.1")
    assert req2.branch == "v2.0.1"
