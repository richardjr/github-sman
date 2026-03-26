"""Commit, PR, and code review activity queries."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime

from github.Repository import Repository

from sman.github.client import GitHubClient


@dataclass
class CommitActivity:
    """Commit activity for a developer."""

    author: str
    repo: str
    sha: str
    message: str
    date: datetime
    additions: int
    deletions: int


@dataclass
class PullRequestActivity:
    """PR activity record."""

    author: str
    repo: str
    number: int
    title: str
    state: str  # open, closed, merged
    created_at: datetime
    closed_at: datetime | None
    merged_at: datetime | None


@dataclass
class ReviewActivity:
    """Code review record."""

    reviewer: str
    repo: str
    pr_number: int
    pr_title: str
    state: str  # APPROVED, CHANGES_REQUESTED, COMMENTED
    submitted_at: datetime


def _fetch_repo_commits(
    repo: Repository, since: datetime, until: datetime, max_results: int
) -> list[CommitActivity]:
    commits = []
    for c in repo.get_commits(since=since, until=until):
        if len(commits) >= max_results:
            break
        if c.author:
            author = c.author.login
        elif c.commit.author:
            author = c.commit.author.name
        else:
            author = "unknown"
        commits.append(
            CommitActivity(
                author=author,
                repo=repo.name,
                sha=c.sha[:7],
                message=c.commit.message.split("\n")[0][:80],
                date=c.commit.author.date if c.commit.author else since,
                additions=c.stats.additions if c.stats else 0,
                deletions=c.stats.deletions if c.stats else 0,
            )
        )
    return commits


def _fetch_repo_prs(
    repo: Repository, since: datetime, until: datetime, max_results: int
) -> list[PullRequestActivity]:
    prs = []
    for pr in repo.get_pulls(state="all", sort="updated", direction="desc"):
        if pr.created_at < since:
            break
        if pr.created_at > until:
            continue
        if len(prs) >= max_results:
            break
        prs.append(
            PullRequestActivity(
                author=pr.user.login if pr.user else "unknown",
                repo=repo.name,
                number=pr.number,
                title=pr.title[:80],
                state="merged" if pr.merged else pr.state,
                created_at=pr.created_at,
                closed_at=pr.closed_at,
                merged_at=pr.merged_at,
            )
        )
    return prs


def _fetch_repo_reviews(
    repo: Repository, since: datetime, until: datetime, max_results: int
) -> list[ReviewActivity]:
    reviews = []
    for pr in repo.get_pulls(state="all", sort="updated", direction="desc"):
        if pr.created_at < since:
            break
        if pr.created_at > until:
            continue
        for review in pr.get_reviews():
            if review.submitted_at and since <= review.submitted_at <= until:
                reviews.append(
                    ReviewActivity(
                        reviewer=review.user.login if review.user else "unknown",
                        repo=repo.name,
                        pr_number=pr.number,
                        pr_title=pr.title[:80],
                        state=review.state,
                        submitted_at=review.submitted_at,
                    )
                )
                if len(reviews) >= max_results:
                    return reviews
    return reviews


def fetch_commits(
    client: GitHubClient,
    since: datetime,
    until: datetime,
    max_results: int = 500,
    max_workers: int = 5,
) -> list[CommitActivity]:
    """Fetch commits across all repos for the org within a date range."""
    cache_key = f"commits:{client.name}:{since.date()}:{until.date()}"
    cached = client.cache.get(cache_key)
    if cached is not None:
        return cached

    org = client.get_org()
    repos = list(org.get_repos(sort="updated"))

    all_commits: list[CommitActivity] = []
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {
            pool.submit(_fetch_repo_commits, repo, since, until, max_results): repo
            for repo in repos
        }
        for future in as_completed(futures):
            try:
                all_commits.extend(future.result())
            except Exception:
                pass  # Skip repos that error (e.g., empty repos)

    all_commits.sort(key=lambda c: c.date, reverse=True)
    all_commits = all_commits[:max_results]
    client.cache.set(cache_key, all_commits)
    return all_commits


def fetch_pull_requests(
    client: GitHubClient,
    since: datetime,
    until: datetime,
    max_results: int = 500,
    max_workers: int = 5,
) -> list[PullRequestActivity]:
    """Fetch PR activity across all repos."""
    cache_key = f"prs:{client.name}:{since.date()}:{until.date()}"
    cached = client.cache.get(cache_key)
    if cached is not None:
        return cached

    org = client.get_org()
    repos = list(org.get_repos(sort="updated"))

    all_prs: list[PullRequestActivity] = []
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {
            pool.submit(_fetch_repo_prs, repo, since, until, max_results): repo
            for repo in repos
        }
        for future in as_completed(futures):
            try:
                all_prs.extend(future.result())
            except Exception:
                pass

    all_prs.sort(key=lambda p: p.created_at, reverse=True)
    all_prs = all_prs[:max_results]
    client.cache.set(cache_key, all_prs)
    return all_prs


def fetch_reviews(
    client: GitHubClient,
    since: datetime,
    until: datetime,
    max_results: int = 500,
    max_workers: int = 5,
) -> list[ReviewActivity]:
    """Fetch code review activity across all repos."""
    cache_key = f"reviews:{client.name}:{since.date()}:{until.date()}"
    cached = client.cache.get(cache_key)
    if cached is not None:
        return cached

    org = client.get_org()
    repos = list(org.get_repos(sort="updated"))

    all_reviews: list[ReviewActivity] = []
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {
            pool.submit(_fetch_repo_reviews, repo, since, until, max_results): repo
            for repo in repos
        }
        for future in as_completed(futures):
            try:
                all_reviews.extend(future.result())
            except Exception:
                pass

    all_reviews.sort(key=lambda r: r.submitted_at, reverse=True)
    all_reviews = all_reviews[:max_results]
    client.cache.set(cache_key, all_reviews)
    return all_reviews
