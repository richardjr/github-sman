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


# ---------------------------------------------------------------------------
# Result wrappers (cache metadata)
# ---------------------------------------------------------------------------


@dataclass
class CommitResult:
    commits: list[CommitActivity]
    cached_at: datetime
    from_cache: bool


@dataclass
class PullRequestResult:
    prs: list[PullRequestActivity]
    cached_at: datetime
    from_cache: bool


@dataclass
class ReviewResult:
    reviews: list[ReviewActivity]
    cached_at: datetime
    from_cache: bool


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
    repo_names: list[str] | None = None,
    max_results: int = 500,
    max_workers: int = 5,
    force_refresh: bool = False,
) -> CommitResult:
    """Fetch commits across repos for the org within a date range."""
    cache_key = f"commits:{client.name}:{since.date()}:{until.date()}"

    if not force_refresh:
        pcached = client.persistent_cache.get(cache_key)
        if pcached is not None:
            value, ts = pcached
            return CommitResult(
                commits=value,
                cached_at=datetime.fromtimestamp(ts),
                from_cache=True,
            )
        mcached = client.cache.get(cache_key)
        if mcached is not None:
            return CommitResult(
                commits=mcached, cached_at=datetime.now(), from_cache=True
            )

    org = client.get_org()
    all_repos = list(org.get_repos(sort="updated"))
    if repo_names is not None:
        name_set = set(repo_names)
        repos = [r for r in all_repos if r.name in name_set]
    else:
        repos = all_repos

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
    client.persistent_cache.set(cache_key, all_commits)
    return CommitResult(
        commits=all_commits, cached_at=datetime.now(), from_cache=False
    )


def fetch_pull_requests(
    client: GitHubClient,
    since: datetime,
    until: datetime,
    repo_names: list[str] | None = None,
    max_results: int = 500,
    max_workers: int = 5,
    force_refresh: bool = False,
) -> PullRequestResult:
    """Fetch PR activity across repos."""
    cache_key = f"prs:{client.name}:{since.date()}:{until.date()}"

    if not force_refresh:
        pcached = client.persistent_cache.get(cache_key)
        if pcached is not None:
            value, ts = pcached
            return PullRequestResult(
                prs=value,
                cached_at=datetime.fromtimestamp(ts),
                from_cache=True,
            )
        mcached = client.cache.get(cache_key)
        if mcached is not None:
            return PullRequestResult(
                prs=mcached, cached_at=datetime.now(), from_cache=True
            )

    org = client.get_org()
    all_repos = list(org.get_repos(sort="updated"))
    if repo_names is not None:
        name_set = set(repo_names)
        repos = [r for r in all_repos if r.name in name_set]
    else:
        repos = all_repos

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
    client.persistent_cache.set(cache_key, all_prs)
    return PullRequestResult(
        prs=all_prs, cached_at=datetime.now(), from_cache=False
    )


def fetch_reviews(
    client: GitHubClient,
    since: datetime,
    until: datetime,
    repo_names: list[str] | None = None,
    max_results: int = 500,
    max_workers: int = 5,
    force_refresh: bool = False,
) -> ReviewResult:
    """Fetch code review activity across repos."""
    cache_key = f"reviews:{client.name}:{since.date()}:{until.date()}"

    if not force_refresh:
        pcached = client.persistent_cache.get(cache_key)
        if pcached is not None:
            value, ts = pcached
            return ReviewResult(
                reviews=value,
                cached_at=datetime.fromtimestamp(ts),
                from_cache=True,
            )
        mcached = client.cache.get(cache_key)
        if mcached is not None:
            return ReviewResult(
                reviews=mcached, cached_at=datetime.now(), from_cache=True
            )

    org = client.get_org()
    all_repos = list(org.get_repos(sort="updated"))
    if repo_names is not None:
        name_set = set(repo_names)
        repos = [r for r in all_repos if r.name in name_set]
    else:
        repos = all_repos

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
    client.persistent_cache.set(cache_key, all_reviews)
    return ReviewResult(
        reviews=all_reviews, cached_at=datetime.now(), from_cache=False
    )


# ---------------------------------------------------------------------------
# Read-only cache accessors (no network calls)
# ---------------------------------------------------------------------------


def get_cached_commits(
    client: GitHubClient, since: datetime, until: datetime
) -> CommitResult | None:
    """Return cached commits without network calls, or None."""
    cache_key = f"commits:{client.name}:{since.date()}:{until.date()}"
    cached = client.persistent_cache.get(cache_key)
    if cached is None:
        return None
    value, ts = cached
    return CommitResult(
        commits=value,
        cached_at=datetime.fromtimestamp(ts),
        from_cache=True,
    )


def get_cached_pull_requests(
    client: GitHubClient, since: datetime, until: datetime
) -> PullRequestResult | None:
    """Return cached PRs without network calls, or None."""
    cache_key = f"prs:{client.name}:{since.date()}:{until.date()}"
    cached = client.persistent_cache.get(cache_key)
    if cached is None:
        return None
    value, ts = cached
    return PullRequestResult(
        prs=value,
        cached_at=datetime.fromtimestamp(ts),
        from_cache=True,
    )


def get_cached_reviews(
    client: GitHubClient, since: datetime, until: datetime
) -> ReviewResult | None:
    """Return cached reviews without network calls, or None."""
    cache_key = f"reviews:{client.name}:{since.date()}:{until.date()}"
    cached = client.persistent_cache.get(cache_key)
    if cached is None:
        return None
    value, ts = cached
    return ReviewResult(
        reviews=value,
        cached_at=datetime.fromtimestamp(ts),
        from_cache=True,
    )
