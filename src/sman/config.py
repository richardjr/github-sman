"""Configuration management for sman.

Config is stored at ~/.config/sman/config.toml (respects XDG_CONFIG_HOME).
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

import tomli_w


def _config_dir() -> Path:
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg) if xdg else Path.home() / ".config"
    return base / "sman"


def _config_path() -> Path:
    return _config_dir() / "config.toml"


@dataclass
class OrgConfig:
    """A single GitHub org/account configuration."""

    name: str
    token: str = ""
    token_env: str = ""
    type: str = "org"  # "org" or "user"

    def resolve_token(self) -> str:
        """Return the token, reading from env var if token_env is set."""
        if self.token_env:
            val = os.environ.get(self.token_env, "")
            if val:
                return val
        return self.token


@dataclass
class Config:
    """Application configuration."""

    default_org: str = ""
    cache_ttl_seconds: int = 300
    work_dir: str = ""
    terminal: str = ""
    orgs: list[OrgConfig] = field(default_factory=list)

    @property
    def resolved_work_dir(self) -> Path | None:
        """Return the work_dir as an expanded Path, or None if not set."""
        if not self.work_dir:
            return None
        return Path(self.work_dir).expanduser()

    @classmethod
    def load(cls, path: Path | None = None) -> Config:
        """Load config from TOML file. Returns default config if file doesn't exist."""
        path = path or _config_path()
        if not path.exists():
            return cls()

        with open(path, "rb") as f:
            data = tomllib.load(f)

        general = data.get("general", {})
        orgs_data = data.get("orgs", [])

        orgs = [
            OrgConfig(
                name=o["name"],
                token=o.get("token", ""),
                token_env=o.get("token_env", ""),
                type=o.get("type", "org"),
            )
            for o in orgs_data
        ]

        return cls(
            default_org=general.get("default_org", ""),
            cache_ttl_seconds=general.get("cache_ttl_seconds", 300),
            work_dir=general.get("work_dir", ""),
            terminal=general.get("terminal", ""),
            orgs=orgs,
        )

    def save(self, path: Path | None = None) -> None:
        """Save config to TOML file."""
        path = path or _config_path()
        path.parent.mkdir(parents=True, exist_ok=True)

        data: dict = {
            "general": {
                "default_org": self.default_org,
                "cache_ttl_seconds": self.cache_ttl_seconds,
                "work_dir": self.work_dir,
                "terminal": self.terminal,
            },
            "orgs": [],
        }

        for org in self.orgs:
            org_dict: dict[str, str] = {"name": org.name, "type": org.type}
            if org.token_env:
                org_dict["token_env"] = org.token_env
            elif org.token:
                org_dict["token"] = org.token
            data["orgs"].append(org_dict)

        with open(path, "wb") as f:
            tomli_w.dump(data, f)

        # Restrict permissions to owner only
        path.chmod(0o600)

    def get_org(self, name: str) -> OrgConfig | None:
        """Get org config by name."""
        for org in self.orgs:
            if org.name == name:
                return org
        return None

    def get_default_org(self) -> OrgConfig | None:
        """Get the default org, or first org if no default set."""
        if self.default_org:
            org = self.get_org(self.default_org)
            if org:
                return org
        if self.orgs:
            return self.orgs[0]
        return None

    def add_org(self, org: OrgConfig) -> None:
        """Add or update an org config."""
        for i, existing in enumerate(self.orgs):
            if existing.name == org.name:
                self.orgs[i] = org
                return
        self.orgs.append(org)
        if not self.default_org:
            self.default_org = org.name

    def remove_org(self, name: str) -> bool:
        """Remove an org config. Returns True if found and removed."""
        for i, org in enumerate(self.orgs):
            if org.name == name:
                self.orgs.pop(i)
                if self.default_org == name:
                    self.default_org = self.orgs[0].name if self.orgs else ""
                return True
        return False
