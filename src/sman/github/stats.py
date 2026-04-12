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


@dataclass
class OrgRepoSummaryResult:
    summaries: list[OrgRepoSummary]
    cached_at: datetime
    from_cache: bool


def fetch_org_repo_summaries(
    client: GitHubClient,
    repo_names: list[str] | None = None,
    max_repos: int = 100,
    force_refresh: bool = False,
) -> OrgRepoSummaryResult:
    """Fetch summary stats for repos in the org."""
    cache_key = f"org_summaries:{client.name}"

    if not force_refresh:
        pcached = client.persistent_cache.get(cache_key)
        if pcached is not None:
            value, ts = pcached
            return OrgRepoSummaryResult(
                summaries=value,
                cached_at=datetime.fromtimestamp(ts),
                from_cache=True,
            )
        mcached = client.cache.get(cache_key)
        if mcached is not None:
            return OrgRepoSummaryResult(
                summaries=mcached, cached_at=datetime.now(), from_cache=True
            )

    org = client.get_org()
    name_set = set(repo_names) if repo_names is not None else None
    summaries = []
    for i, repo in enumerate(org.get_repos(sort="updated")):
        if i >= max_repos:
            break
        if name_set is not None and repo.name not in name_set:
            continue
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
    client.persistent_cache.set(cache_key, summaries)
    return OrgRepoSummaryResult(
        summaries=summaries, cached_at=datetime.now(), from_cache=False
    )


def get_cached_org_repo_summaries(
    client: GitHubClient,
) -> OrgRepoSummaryResult | None:
    """Return cached org repo summaries without network calls, or None."""
    cache_key = f"org_summaries:{client.name}"
    cached = client.persistent_cache.get(cache_key)
    if cached is None:
        return None
    value, ts = cached
    return OrgRepoSummaryResult(
        summaries=value,
        cached_at=datetime.fromtimestamp(ts),
        from_cache=True,
    )
