"""GitHub client wrapper around PyGitHub."""

from __future__ import annotations

from dataclasses import dataclass, field

from github import Auth, Github
from github.AuthenticatedUser import AuthenticatedUser
from github.Organization import Organization

from sman.config import OrgConfig
from sman.github.cache import Cache


@dataclass
class GitHubClient:
    """Authenticated GitHub client bound to a specific org/account."""

    name: str
    org_type: str
    _github: Github = field(repr=False)
    _cache: Cache = field(repr=False)

    @classmethod
    def from_config(cls, org_config: OrgConfig, cache_ttl: int = 300) -> GitHubClient:
        token = org_config.resolve_token()
        if not token:
            raise ValueError(f"No token configured for org '{org_config.name}'")
        gh = Github(auth=Auth.Token(token), per_page=100)
        return cls(
            name=org_config.name,
            org_type=org_config.type,
            _github=gh,
            _cache=Cache(default_ttl=cache_ttl),
        )

    def get_org(self) -> Organization | AuthenticatedUser:
        """Return the GitHub organization or authenticated user."""
        if self.org_type == "org":
            return self._github.get_organization(self.name)
        return self._github.get_user()

    @property
    def github(self) -> Github:
        return self._github

    @property
    def cache(self) -> Cache:
        return self._cache

    def rate_limit_remaining(self) -> int:
        """Return remaining API calls before rate limit."""
        return self._github.get_rate_limit().core.remaining

    def rate_limit_reset(self) -> int:
        """Return unix timestamp when rate limit resets."""
        import calendar

        reset_time = self._github.get_rate_limit().core.reset
        return calendar.timegm(reset_time.timetuple())

    def close(self) -> None:
        self._github.close()
