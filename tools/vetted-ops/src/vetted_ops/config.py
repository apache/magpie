#
# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
"""
Configuration loading for the vetted-op surface.

The config is the *policy*: which repositories the operations act on, which
label / milestone / column values are permitted, and which caller may invoke
which operation. It is adopter-owned data, read from the adopter repo, and is
never supplied on the command line — a caller cannot widen its own policy.
"""

from __future__ import annotations

import json
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

#: `owner/name`, conservative on both halves.
_REPO = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,100}/[A-Za-z0-9][A-Za-z0-9._-]{0,100}$")

DEFAULT_RELATIVE_PATH = Path(".apache-magpie-overrides/tools/vetted-ops/config.toml")


class ConfigError(RuntimeError):
    """Raised when the configuration is missing, malformed, or unsafe."""


@dataclass(frozen=True)
class Config:
    """Resolved, validated policy."""

    tracker_repo: str
    upstream_repo: str
    workspace: Path
    #: Enum name -> permitted values. Board columns map name -> option id.
    values: dict[str, object]
    #: Caller name -> permitted operation names.
    callers: dict[str, frozenset[str]]

    def as_mapping(self) -> dict[str, object]:
        """The mapping handed to an operation's ``build`` callable."""
        merged: dict[str, object] = dict(self.values)
        merged["tracker_repo"] = self.tracker_repo
        merged["upstream_repo"] = self.upstream_repo
        return merged

    def enum_values(self, key: str) -> list[str]:
        raw = self.values.get(key)
        if raw is None:
            raise ConfigError(f"config declares no {key!r} list, so no operation may use it")
        if isinstance(raw, dict):
            return sorted(raw)
        if isinstance(raw, list) and all(isinstance(v, str) for v in raw):
            return list(raw)
        raise ConfigError(f"config key {key!r} must be a list of strings or a table")

    def ops_for(self, caller: str) -> frozenset[str]:
        try:
            return self.callers[caller]
        except KeyError:
            known = ", ".join(sorted(self.callers)) or "(none)"
            raise ConfigError(
                f"caller {caller!r} is not declared in the config; declared callers: {known}"
            ) from None


def _require_repo(raw: dict[str, object], key: str) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not _REPO.match(value):
        raise ConfigError(f"{key!r} must be an 'owner/name' string, got {value!r}")
    return value


def load(path: Path | None = None, *, cwd: Path | None = None) -> Config:
    """Load and validate the policy."""
    base = (cwd or Path.cwd()).resolve()
    resolved = path if path is not None else base / DEFAULT_RELATIVE_PATH
    if not resolved.is_file():
        raise ConfigError(f"no vetted-ops config at {resolved}")

    with resolved.open("rb") as handle:
        raw = tomllib.load(handle)

    repos = raw.get("repos")
    if not isinstance(repos, dict):
        raise ConfigError("config needs a [repos] table with tracker and upstream")

    workspace_raw = raw.get("workspace")
    if not isinstance(workspace_raw, str) or not workspace_raw:
        raise ConfigError("config needs a top-level 'workspace' path for body files")
    workspace = Path(workspace_raw).expanduser()
    if not workspace.is_absolute():
        workspace = (base / workspace).resolve()

    values_raw = raw.get("values", {})
    if not isinstance(values_raw, dict):
        raise ConfigError("[values] must be a table")

    callers_raw = raw.get("callers", {})
    if not isinstance(callers_raw, dict):
        raise ConfigError("[callers] must be a table of caller -> list of operation names")

    callers: dict[str, frozenset[str]] = {}
    for name, ops in callers_raw.items():
        if not isinstance(ops, list) or not all(isinstance(o, str) for o in ops):
            raise ConfigError(f"callers.{name} must be a list of operation names")
        callers[name] = frozenset(ops)

    return Config(
        tracker_repo=_require_repo(repos, "tracker"),
        upstream_repo=_require_repo(repos, "upstream"),
        workspace=workspace,
        values=dict(values_raw),
        callers=callers,
    )


def describe(config: Config) -> str:
    """A stable, machine-readable summary — used by `vetted-op policy`."""
    return json.dumps(
        {
            "tracker_repo": config.tracker_repo,
            "upstream_repo": config.upstream_repo,
            "workspace": str(config.workspace),
            "values": {k: (sorted(v) if isinstance(v, dict) else v) for k, v in config.values.items()},
            "callers": {k: sorted(v) for k, v in sorted(config.callers.items())},
        },
        indent=2,
        sort_keys=True,
    )
