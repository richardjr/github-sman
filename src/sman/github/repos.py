"""Repo-related GitHub API operations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sman.github.client import GitHubClient


@dataclass
class RepoInfo:
    """Plain data representation of a GitHub repository."""

    name: str
    full_name: str
    description: str
    private: bool
    language: str
    stars: int
    forks: int
    open_issues: int
    updated_at: datetime
    default_branch: str
    html_url: str


@dataclass
class RepoDetail(RepoInfo):
    """Extended repo info for detail view."""

    created_at: datetime = datetime.min
    pushed_at: datetime = datetime.min
    size_kb: int = 0
    topics: list[str] | None = None
    archived: bool = False


def list_repos(client: GitHubClient, sort: str = "updated") -> list[RepoInfo]:
    """List all repos for the current org/account."""
    cache_key = f"repos:{client.name}:{sort}"
    cached = client.cache.get(cache_key)
    if cached is not None:
        return cached

    org = client.get_org()
    repos = [
        RepoInfo(
            name=r.name,
            full_name=r.full_name,
            description=r.description or "",
            private=r.private,
            language=r.language or "",
            stars=r.stargazers_count,
            forks=r.forks_count,
            open_issues=r.open_issues_count,
            updated_at=r.updated_at,
            default_branch=r.default_branch,
            html_url=r.html_url,
        )
        for r in org.get_repos(sort=sort)
    ]
    client.cache.set(cache_key, repos)
    return repos


def get_repo_detail(client: GitHubClient, repo_name: str) -> RepoDetail:
    """Get detailed info for a specific repo."""
    cache_key = f"repo_detail:{client.name}:{repo_name}"
    cached = client.cache.get(cache_key)
    if cached is not None:
        return cached

    r = client.github.get_repo(f"{client.name}/{repo_name}")
    detail = RepoDetail(
        name=r.name,
        full_name=r.full_name,
        description=r.description or "",
        private=r.private,
        language=r.language or "",
        stars=r.stargazers_count,
        forks=r.forks_count,
        open_issues=r.open_issues_count,
        updated_at=r.updated_at,
        default_branch=r.default_branch,
        html_url=r.html_url,
        created_at=r.created_at,
        pushed_at=r.pushed_at,
        size_kb=r.size,
        topics=r.get_topics(),
        archived=r.archived,
    )
    client.cache.set(cache_key, detail)
    return detail


@dataclass
class CreateRepoParams:
    """Parameters for creating a new repository."""

    name: str
    description: str = ""
    private: bool = True
    auto_init: bool = True


def create_repo(client: GitHubClient, params: CreateRepoParams) -> RepoInfo:
    """Create a new repository under the current org/account."""
    org = client.get_org()
    r = org.create_repo(
        name=params.name,
        description=params.description,
        private=params.private,
        auto_init=params.auto_init,
    )
    # Invalidate repo list cache
    client.cache.invalidate_prefix(f"repos:{client.name}")

    return RepoInfo(
        name=r.name,
        full_name=r.full_name,
        description=r.description or "",
        private=r.private,
        language=r.language or "",
        stars=r.stargazers_count,
        forks=r.forks_count,
        open_issues=r.open_issues_count,
        updated_at=r.updated_at,
        default_branch=r.default_branch,
        html_url=r.html_url,
    )
