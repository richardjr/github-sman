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
    max_results: int = 500,
    max_workers: int = 5,
) -> list[IssueActivity]:
    """Fetch issue activity across all repos for the org."""
    cache_key = f"issues:{client.name}:{since.date()}:{until.date()}"
    cached = client.cache.get(cache_key)
    if cached is not None:
        return cached

    org = client.get_org()
    repos = list(org.get_repos(sort="updated"))

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
    return all_issues
