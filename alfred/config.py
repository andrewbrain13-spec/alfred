"""Load and validate the YAML configuration.

The config has two parts:

* ``source``   – which mailbox to watch and how to connect.
* ``rules``    – a list of trigger -> workflow bindings.

Secrets should never live in the YAML. Any string of the form ``${ENV_VAR}``
is replaced with the corresponding environment variable at load time, so the
committed config stays free of passwords and tokens.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Any

import yaml

_ENV_PATTERN = re.compile(r"\$\{([A-Z0-9_]+)\}")


def _expand_env(value: Any) -> Any:
    """Recursively replace ``${VAR}`` markers with environment values."""
    if isinstance(value, str):
        def repl(match: re.Match) -> str:
            name = match.group(1)
            if name not in os.environ:
                raise ConfigError(f"Environment variable {name!r} referenced in config is not set")
            return os.environ[name]

        return _ENV_PATTERN.sub(repl, value)
    if isinstance(value, list):
        return [_expand_env(v) for v in value]
    if isinstance(value, dict):
        return {k: _expand_env(v) for k, v in value.items()}
    return value


class ConfigError(Exception):
    """Raised when the configuration is missing or malformed."""


@dataclass
class RuleConfig:
    name: str
    match: dict[str, Any]
    workflows: list[dict[str, Any]]
    stop_on_match: bool = False
    """If true, later rules are skipped once this one matches a message."""


@dataclass
class TaskConfig:
    """A periodic command run inside the engine (e.g. a folder watcher)."""
    name: str
    command: list[str]
    every_seconds: int = 300
    env: dict[str, str] = field(default_factory=dict)


@dataclass
class Config:
    source: dict[str, Any]
    rules: list[RuleConfig]
    poll_seconds: int = 60
    state_file: str = "alfred_state.json"
    log_file: str = field(default="alfred.log")
    tasks: list[TaskConfig] = field(default_factory=list)

    @classmethod
    def load(cls, path: str) -> "Config":
        if not os.path.exists(path):
            raise ConfigError(f"Config file not found: {path}")
        with open(path, "r", encoding="utf-8") as fh:
            raw = yaml.safe_load(fh) or {}
        raw = _expand_env(raw)

        if "source" not in raw:
            raise ConfigError("Config must define a 'source' section")

        rules = []
        for i, r in enumerate(raw.get("rules", [])):
            if "name" not in r:
                raise ConfigError(f"Rule #{i} is missing a 'name'")
            rules.append(
                RuleConfig(
                    name=r["name"],
                    match=r.get("match", {}),
                    workflows=r.get("workflows", []),
                    stop_on_match=bool(r.get("stop_on_match", False)),
                )
            )

        tasks = []
        for i, t in enumerate(raw.get("tasks", [])):
            if "name" not in t or "command" not in t:
                raise ConfigError(f"Task #{i} needs a 'name' and 'command'")
            cmd = t["command"]
            if not isinstance(cmd, list):
                raise ConfigError(f"Task {t['name']!r} command must be a list")
            tasks.append(
                TaskConfig(
                    name=t["name"],
                    command=[str(c) for c in cmd],
                    every_seconds=int(t.get("every_seconds", 300)),
                    env={str(k): str(v) for k, v in t.get("env", {}).items()},
                )
            )

        return cls(
            source=raw["source"],
            rules=rules,
            poll_seconds=int(raw.get("poll_seconds", 60)),
            state_file=raw.get("state_file", "alfred_state.json"),
            log_file=raw.get("log_file", "alfred.log"),
            tasks=tasks,
        )
