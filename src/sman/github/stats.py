"""Repo-level statistics — languages, releases, branches, contributors."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sman.github.client import GitHubClient


@dataclass
class RepoStats:
    """Aggregated statistics for a repository."""

    name: str
    language_breakdown: dict[str, int]  # language -> bytes
    total_bytes: int
    release_count: int
    latest_release: str
    latest_release_date: datetime | None
    branch_count: int
    contributor_count: int
    open_prs: int
    open_issues: int


def fetch_repo_stats(client: GitHubClient, repo_name: str) -> RepoStats:
    """Fetch detailed stats for a single repo."""
    cache_key = f"stats:{client.name}:{repo_name}"
    cached = client.cache.get(cache_key)
    if cached is not None:
        return cached

    repo = client.github.get_repo(f"{client.name}/{repo_name}")

    languages = repo.get_languages()
    total_bytes = sum(languages.values())

    releases = list(repo.get_releases()[:10])
    release_count = repo.get_releases().totalCount

    branches = repo.get_branches()
    branch_count = branches.totalCount

    contributors = repo.get_contributors()
    contributor_count = contributors.totalCount

    stats = RepoStats(
        name=repo_name,
        language_breakdown=languages,
        total_bytes=total_bytes,
        release_count=release_count,
        latest_release=releases[0].tag_name if releases else "",
        latest_release_date=releases[0].published_at if releases else None,
        branch_count=branch_count,
        contributor_count=contributor_count,
        open_prs=repo.get_pulls(state="open").totalCount,
        open_issues=repo.open_issues_count,
    )
    client.cache.set(cache_key, stats)
    return stats


@dataclass
class OrgRepoSummary:
    """Summary stats for a repo, used in the org-wide overview."""

    name: str
    language: str
    stars: int
    forks: int
    open_issues: int
    open_prs: int
    contributors: int
    last_push: datetime | None


def fetch_org_repo_summaries(
    client: GitHubClient, max_repos: int = 100
) -> list[OrgRepoSummary]:
    """Fetch summary stats for all repos in the org."""
    cache_key = f"org_summaries:{client.name}"
    cached = client.cache.get(cache_key)
    if cached is not None:
        return cached

    org = client.get_org()
    summaries = []
    for i, repo in enumerate(org.get_repos(sort="updated")):
        if i >= max_repos:
            break
        summaries.append(
            OrgRepoSummary(
                name=repo.name,
                language=repo.language or "",
                stars=repo.stargazers_count,
                forks=repo.forks_count,
                open_issues=repo.open_issues_count,
                open_prs=repo.get_pulls(state="open").totalCount,
                contributors=repo.get_contributors().totalCount,
                last_push=repo.pushed_at,
            )
        )
    client.cache.set(cache_key, summaries)
    return summaries
