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
    ssh_url: str


@dataclass
class RepoDetail(RepoInfo):
    """Extended repo info for detail view."""

    created_at: datetime = datetime.min
    pushed_at: datetime = datetime.min
    size_kb: int = 0
    topics: list[str] | None = None
    archived: bool = False


@dataclass
class ListReposResult:
    """Result of a cache-aware repo list fetch."""

    repos: list[RepoInfo]
    cached_at: datetime
    from_cache: bool


@dataclass
class RepoDetailResult:
    """Result of a cache-aware repo detail fetch."""

    detail: RepoDetail
    cached_at: datetime
    from_cache: bool


def _build_repo_info(r) -> RepoInfo:
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
        ssh_url=r.ssh_url,
    )


def list_repos(
    client: GitHubClient,
    sort: str = "updated",
    force_refresh: bool = False,
) -> ListReposResult:
    """List all repos for the current org/account.

    By default, returns persisted cache data if present (regardless of age).
    When ``force_refresh`` is True, bypasses the cache and fetches fresh data
    from GitHub, updating both the in-memory and persistent caches.
    """
    cache_key = f"repos:{client.name}:{sort}"

    if not force_refresh:
        cached = client.persistent_cache.get(cache_key)
        if cached is not None:
            value, ts = cached
            return ListReposResult(
                repos=value,
                cached_at=datetime.fromtimestamp(ts),
                from_cache=True,
            )

    org = client.get_org()
    repos = [_build_repo_info(r) for r in org.get_repos(sort=sort)]
    client.persistent_cache.set(cache_key, repos)
    client.cache.set(cache_key, repos)
    return ListReposResult(
        repos=repos,
        cached_at=datetime.now(),
        from_cache=False,
    )


def get_cached_repo_detail(
    client: GitHubClient, repo_name: str
) -> RepoDetailResult | None:
    """Return a cached RepoDetailResult without making any network call.

    Used by the detail screen to render immediately while a fresh fetch runs
    in the background. Returns None if nothing has been cached yet.
    """
    cache_key = f"repo_detail:{client.name}:{repo_name}"
    cached = client.persistent_cache.get(cache_key)
    if cached is None:
        return None
    value, ts = cached
    return RepoDetailResult(
        detail=value,
        cached_at=datetime.fromtimestamp(ts),
        from_cache=True,
    )


def get_repo_detail(client: GitHubClient, repo_name: str) -> RepoDetailResult:
    """Get detailed info for a specific repo.

    Always attempts to fetch fresh data from GitHub. If that fails for any
    reason (network, rate limit, auth, etc.) and a cached entry exists,
    returns the cached copy marked as stale. If no cache is available, the
    underlying exception is re-raised.
    """
    cache_key = f"repo_detail:{client.name}:{repo_name}"

    try:
        qualified = (
            repo_name if "/" in repo_name else f"{client.name}/{repo_name}"
        )
        r = client.github.get_repo(qualified)
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
            ssh_url=r.ssh_url,
            created_at=r.created_at,
            pushed_at=r.pushed_at,
            size_kb=r.size,
            topics=r.get_topics(),
            archived=r.archived,
        )
        client.persistent_cache.set(cache_key, detail)
        return RepoDetailResult(
            detail=detail,
            cached_at=datetime.now(),
            from_cache=False,
        )
    except Exception:
        cached = client.persistent_cache.get(cache_key)
        if cached is None:
            raise
        value, ts = cached
        return RepoDetailResult(
            detail=value,
            cached_at=datetime.fromtimestamp(ts),
            from_cache=True,
        )


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
    # Invalidate repo list cache (both layers)
    prefix = f"repos:{client.name}"
    client.cache.invalidate_prefix(prefix)
    client.persistent_cache.invalidate_prefix(prefix)

    return _build_repo_info(r)


# ---------------------------------------------------------------------------
# Report inclusion / exclusion helpers
# ---------------------------------------------------------------------------


def get_excluded_repos(client: GitHubClient) -> set[str]:
    """Return the set of repo names excluded from reports."""
    cache_key = f"excluded_repos:{client.name}"
    cached = client.persistent_cache.get(cache_key)
    if cached is None:
        return set()
    value, _ts = cached
    return value if isinstance(value, set) else set()


def set_excluded_repos(client: GitHubClient, excluded: set[str]) -> None:
    """Persist the set of repo names excluded from reports."""
    cache_key = f"excluded_repos:{client.name}"
    client.persistent_cache.set(cache_key, excluded)


def toggle_repo_excluded(client: GitHubClient, repo_name: str) -> bool:
    """Toggle a repo's excluded status. Returns True if now excluded."""
    excluded = get_excluded_repos(client)
    if repo_name in excluded:
        excluded.discard(repo_name)
        result = False
    else:
        excluded.add(repo_name)
        result = True
    set_excluded_repos(client, excluded)
    return result


def get_report_repo_names(client: GitHubClient) -> list[str] | None:
    """Return names of repos included in reports (not excluded).

    Uses the persistent cache's repo list.  Returns ``None`` when
    no repo list has been cached yet so callers can fall back to
    fetching all repos.
    """
    cache_key = f"repos:{client.name}:updated"
    cached = client.persistent_cache.get(cache_key)
    if cached is None:
        return None
    repos, _ts = cached
    excluded = get_excluded_repos(client)
    return [r.name for r in repos if r.name not in excluded]
