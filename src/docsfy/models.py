from __future__ import annotations

import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


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
        if not path.exists():
            msg = f"Repository path does not exist: '{v}'"
            raise ValueError(msg)
        if not (path / ".git").exists():
            msg = f"Not a git repository (no .git directory): '{v}'"
            raise ValueError(msg)
        return v

    @property
    def project_name(self) -> str:
        if self.repo_url:
            name = self.repo_url.rstrip("/").split("/")[-1]
            if name.endswith(".git"):
                name = name[:-4]
            return name
        if self.repo_path:
            return Path(self.repo_path).resolve().name
        return "unknown"


class DocPage(BaseModel):
    slug: str
    title: str
    description: str = ""


class NavGroup(BaseModel):
    group: str
    pages: list[DocPage]


class DocPlan(BaseModel):
    project_name: str
    tagline: str = ""
    navigation: list[NavGroup] = Field(default_factory=list)
