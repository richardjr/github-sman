"""Issue tracking queries."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime

from github.Repository import Repository

from sman.github.client import GitHubClient


@dataclass
class IssueActivity:
    """Issue activity record."""

    author: str
    assignee: str
    repo: str
    number: int
    title: str
    state: str  # open, closed
    labels: list[str]
    created_at: datetime
    closed_at: datetime | None


@dataclass
class IssueResult:
    issues: list[IssueActivity]
    cached_at: datetime
    from_cache: bool


def _fetch_repo_issues(
    repo: Repository, since: datetime, until: datetime, max_results: int
) -> list[IssueActivity]:
    issues = []
    for issue in repo.get_issues(
        state="all", sort="updated", direction="desc", since=since
    ):
        if issue.pull_request:
            continue  # Skip PRs (GitHub treats them as issues too)
        if issue.created_at > until:
            continue
        if issue.updated_at < since:
            break
        if len(issues) >= max_results:
            break
        issues.append(
            IssueActivity(
                author=issue.user.login if issue.user else "unknown",
                assignee=issue.assignee.login if issue.assignee else "",
                repo=repo.name,
                number=issue.number,
                title=issue.title[:80],
                state=issue.state,
                labels=[label.name for label in issue.labels],
                created_at=issue.created_at,
                closed_at=issue.closed_at,
            )
        )
    return issues


def fetch_issues(
    client: GitHubClient,
    since: datetime,
    until: datetime,
    repo_names: list[str] | None = None,
    max_results: int = 500,
    max_workers: int = 5,
    force_refresh: bool = False,
) -> IssueResult:
    """Fetch issue activity across repos for the org."""
    cache_key = f"issues:{client.name}:{since.date()}:{until.date()}"

    if not force_refresh:
        pcached = client.persistent_cache.get(cache_key)
        if pcached is not None:
            value, ts = pcached
            return IssueResult(
                issues=value,
                cached_at=datetime.fromtimestamp(ts),
                from_cache=True,
            )
        mcached = client.cache.get(cache_key)
        if mcached is not None:
            return IssueResult(
                issues=mcached, cached_at=datetime.now(), from_cache=True
            )

    org = client.get_org()
    all_repos = list(org.get_repos(sort="updated"))
    if repo_names is not None:
        name_set = set(repo_names)
        repos = [r for r in all_repos if r.name in name_set]
    else:
        repos = all_repos

    all_issues: list[IssueActivity] = []
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {
            pool.submit(_fetch_repo_issues, repo, since, until, max_results): repo
            for repo in repos
        }
        for future in as_completed(futures):
            try:
                all_issues.extend(future.result())
            except Exception:
                pass

    all_issues.sort(key=lambda i: i.created_at, reverse=True)
    all_issues = all_issues[:max_results]
    client.cache.set(cache_key, all_issues)
    client.persistent_cache.set(cache_key, all_issues)
    return IssueResult(
        issues=all_issues, cached_at=datetime.now(), from_cache=False
    )


def get_cached_issues(
    client: GitHubClient, since: datetime, until: datetime
) -> IssueResult | None:
    """Return cached issues without network calls, or None."""
    cache_key = f"issues:{client.name}:{since.date()}:{until.date()}"
    cached = client.persistent_cache.get(cache_key)
    if cached is None:
        return None
    value, ts = cached
    return IssueResult(
        issues=value,
        cached_at=datetime.fromtimestamp(ts),
        from_cache=True,
    )
