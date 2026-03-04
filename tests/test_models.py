from __future__ import annotations

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


def test_project_status_model() -> None:
    from docsfy.models import ProjectStatus

    status = ProjectStatus(
        name="my-repo",
        repo_url="https://github.com/org/my-repo.git",
        status="ready",
    )
    assert status.name == "my-repo"
    assert status.status == "ready"
