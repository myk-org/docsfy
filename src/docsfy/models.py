from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class GenerateRequest(BaseModel):
    repo_url: str = Field(description="Git repository URL (HTTPS or SSH)")
    ai_provider: Literal["claude", "gemini", "cursor"] | None = None
    ai_model: str | None = None
    ai_cli_timeout: int | None = Field(default=None, gt=0)

    @field_validator("repo_url")
    @classmethod
    def validate_repo_url(cls, v: str) -> str:
        https_pattern = r"^https?://[\w.\-]+/[\w.\-]+/[\w.\-]+(\.git)?$"
        ssh_pattern = r"^git@[\w.\-]+:[\w.\-]+/[\w.\-]+(\.git)?$"
        if not re.match(https_pattern, v) and not re.match(ssh_pattern, v):
            msg = f"Invalid git repository URL: '{v}'"
            raise ValueError(msg)
        return v

    @property
    def project_name(self) -> str:
        name = self.repo_url.rstrip("/").split("/")[-1]
        if name.endswith(".git"):
            name = name[:-4]
        return name


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


class ProjectStatus(BaseModel):
    name: str
    repo_url: str
    status: Literal["generating", "ready", "error"] = "generating"
    last_commit_sha: str | None = None
    last_generated: str | None = None
    error_message: str | None = None
    page_count: int = 0
