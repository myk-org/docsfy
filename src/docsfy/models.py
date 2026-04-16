from __future__ import annotations

import re
from pathlib import Path
from typing import Literal, get_args

from pydantic import BaseModel, Field, field_validator, model_validator

from docsfy.repository import extract_repo_name

VALID_PROVIDERS = ("claude", "gemini", "cursor")
DEFAULT_BRANCH = "main"
DOCSFY_DOCS_URL = "https://myk-org.github.io/docsfy/"
DOCSFY_REPO_URL = "https://github.com/myk-org/docsfy"
MAX_CONCURRENT_PAGES = 5


class GenerateRequest(BaseModel):
    repo_url: str | None = Field(
        default=None, description="Git repository URL (HTTPS or SSH)"
    )
    repo_path: str | None = Field(default=None, description="Local git repository path")
    ai_provider: Literal["claude", "gemini", "cursor"] | None = None
    ai_model: str | None = None
    ai_cli_timeout: int | None = Field(default=None, gt=0)
    force: bool = Field(
        default=False, description="Force full regeneration, ignoring cache"
    )
    branch: str = Field(
        default=DEFAULT_BRANCH, description="Git branch to generate docs from"
    )

    @field_validator("branch")
    @classmethod
    def validate_branch(cls, v: str) -> str:
        if "/" in v:
            msg = (
                f"Invalid branch name: '{v}'. Branch names cannot contain slashes "
                "— use hyphens instead (e.g., release-1.x)."
            )
            raise ValueError(msg)
        if not re.match(r"^[a-zA-Z0-9][a-zA-Z0-9._-]*$", v):
            msg = f"Invalid branch name: '{v}'"
            raise ValueError(msg)
        if ".." in v:
            msg = f"Invalid branch name: '{v}'"
            raise ValueError(msg)
        return v

    @model_validator(mode="after")
    def validate_source(self) -> GenerateRequest:
        if not self.repo_url and not self.repo_path:
            msg = "Either 'repo_url' or 'repo_path' must be provided"
            raise ValueError(msg)
        if self.repo_url and self.repo_path:
            msg = "Provide either 'repo_url' or 'repo_path', not both"
            raise ValueError(msg)
        return self

    @field_validator("repo_url")
    @classmethod
    def validate_repo_url(cls, v: str | None) -> str | None:
        if v is None:
            return v
        https_pattern = r"^https?://[\w.\-]+/[\w.\-]+/[\w.\-]+(\.git)?$"
        ssh_pattern = r"^git@[\w.\-]+:[\w.\-]+/[\w.\-]+(\.git)?$"
        if not re.match(https_pattern, v) and not re.match(ssh_pattern, v):
            msg = f"Invalid git repository URL: '{v}'"
            raise ValueError(msg)
        return v

    @field_validator("repo_path")
    @classmethod
    def validate_repo_path(cls, v: str | None) -> str | None:
        if v is None:
            return v
        path = Path(v)
        if not path.is_absolute():
            msg = "repo_path must be an absolute path"
            raise ValueError(msg)
        return v

    @property
    def project_name(self) -> str:
        if self.repo_url:
            return extract_repo_name(self.repo_url)
        if self.repo_path:
            return Path(self.repo_path).resolve().name
        return "unknown"


PageType = Literal["guide", "reference", "recipe", "concept"]
PAGE_TYPES: tuple[str, ...] = get_args(PageType)


class DocPage(BaseModel):
    slug: str
    title: str
    description: str = ""
    type: PageType = "guide"


class NavGroup(BaseModel):
    group: str
    pages: list[DocPage]


class DocPlan(BaseModel):
    project_name: str
    tagline: str = ""
    navigation: list[NavGroup] = Field(default_factory=list)
    version: str | None = None
