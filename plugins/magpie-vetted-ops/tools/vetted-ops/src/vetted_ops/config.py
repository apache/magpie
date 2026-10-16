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

from .tracker_backends import BACKEND_SCRIPTS, PLATFORMS, TrackerBackend

#: `owner/name`, conservative on both halves.
_REPO = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,100}/[A-Za-z0-9][A-Za-z0-9._-]{0,100}$")
#: A Jira project key.
_JIRA_KEY = re.compile(r"^[A-Z][A-Z0-9_]{0,30}$")

DEFAULT_RELATIVE_PATH = Path(".apache-magpie-overrides/tools/vetted-ops/config.toml")


class ConfigError(RuntimeError):
    """Raised when the configuration is missing, malformed, or unsafe."""


@dataclass(frozen=True)
class Config:
    """Resolved, validated policy."""

    #: The private tracker, when the policy declares one. Optional: an adopter
    #: whose skills only touch public work has no tracker to name, and requiring
    #: one would make every operation — including upstream-only reads — fail at
    #: load time over a value they never use. Operations that address the tracker
    #: refuse individually instead; see `_tracker` in ops.py.
    tracker_repo: str | None
    upstream_repo: str
    workspace: Path
    #: Enum name -> permitted values. Board columns map name -> option id.
    values: dict[str, object]
    #: Endpoint name -> URL. Defaults are provided for canonical OSV/CVE APIs.
    endpoints: dict[str, str]
    #: Caller name -> permitted operation names.
    callers: dict[str, frozenset[str]]
    #: The non-GitHub security tracker, when ``[tracker] platform`` selects one.
    #: ``None`` means GitHub: tracker operations run their ``gh`` builders.
    tracker_backend: TrackerBackend | None = None

    def as_mapping(self) -> dict[str, object]:
        """The mapping handed to an operation's ``build`` callable."""
        merged: dict[str, object] = dict(self.values)
        merged.update(self.endpoints)
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


def _optional_repo(raw: dict[str, object], key: str) -> str | None:
    """Validate a repo that the policy may legitimately omit.

    Absent is allowed; present-but-malformed is not. Silently ignoring a
    typo'd repo would point operations somewhere unintended, which is the one
    outcome this dispatcher exists to prevent.
    """
    if key not in raw:
        return None
    return _require_repo(raw, key)


def _absolute_dir(raw: dict[str, object], key: str) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value:
        raise ConfigError(f"[tracker] needs {key!r} (an absolute path)")
    path = Path(value).expanduser()
    if not path.is_absolute():
        raise ConfigError(f"[tracker] {key!r} must be absolute, got {value!r}")
    return str(path)


def _one_line(raw: dict[str, object], key: str) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value.strip() or "\n" in value or value.startswith("-"):
        raise ConfigError(f"[tracker] needs {key!r} as one line not starting with '-', got {value!r}")
    return value.strip()


def _tracker_backend(raw: object) -> TrackerBackend | None:
    """
    Validate the optional ``[tracker]`` table.

    Only data comes from the policy — the backend's tool directory and its
    pinned target. The command that runs is fixed in tracker_backends.py, and
    the tool directory must be the one the platform names, so the policy cannot
    smuggle in a different program.
    """
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise ConfigError("[tracker] must be a table")
    platform = raw.get("platform", "github")
    if platform not in PLATFORMS:
        raise ConfigError(f"[tracker] platform must be one of {', '.join(PLATFORMS)}, got {platform!r}")
    if platform == "github":
        return None
    project = _absolute_dir(raw, "project")
    expected_dir, _ = BACKEND_SCRIPTS[platform]
    if Path(project).name != expected_dir:
        raise ConfigError(
            f"[tracker] project for {platform} must be the tools/{expected_dir} directory, got {project!r}"
        )
    if platform == "local-files":
        return TrackerBackend(platform=platform, project=project, root=_absolute_dir(raw, "root"))
    url = _one_line(raw, "jira_url")
    if not url.startswith("https://"):
        raise ConfigError(f"[tracker] jira_url must use https://, got {url!r}")
    key = _one_line(raw, "jira_project")
    if not _JIRA_KEY.match(key):
        raise ConfigError(f"[tracker] jira_project must be a Jira project key, got {key!r}")
    deployment = raw.get("jira_deployment", "server")
    if deployment not in ("server", "cloud"):
        raise ConfigError(f"[tracker] jira_deployment must be server or cloud, got {deployment!r}")
    return TrackerBackend(
        platform=platform,
        project=project,
        jira_url=url.rstrip("/"),
        jira_project=key,
        jira_security_level=_one_line(raw, "jira_security_level"),
        jira_cloud=deployment == "cloud",
    )


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
        raise ConfigError("config needs a [repos] table declaring at least 'upstream'")

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

    endpoints_raw = raw.get("endpoints", {})
    if not isinstance(endpoints_raw, dict):
        raise ConfigError("[endpoints] must be a table")

    endpoints = {
        "osv_api": "https://api.osv.dev/v1",
        "cve_services_api": "https://cveawg.mitre.org/api",
    }
    for name, url in endpoints_raw.items():
        if not isinstance(url, str):
            raise ConfigError(f"endpoints.{name} must be a URL string")
        if not url.startswith("https://"):
            raise ConfigError(f"endpoints.{name} must use the https:// scheme (got {url!r})")
        endpoints[name] = url.rstrip("/")

    return Config(
        tracker_repo=_optional_repo(repos, "tracker"),
        upstream_repo=_require_repo(repos, "upstream"),
        workspace=workspace,
        values=dict(values_raw),
        endpoints=endpoints,
        callers=callers,
        tracker_backend=_tracker_backend(raw.get("tracker")),
    )


def describe(config: Config) -> str:
    """A stable, machine-readable summary — used by `vetted-op policy`."""
    return json.dumps(
        {
            "tracker_repo": config.tracker_repo,
            "upstream_repo": config.upstream_repo,
            "workspace": str(config.workspace),
            "values": {k: (sorted(v) if isinstance(v, dict) else v) for k, v in config.values.items()},
            "endpoints": dict(sorted(config.endpoints.items())),
            "callers": {k: sorted(v) for k, v in sorted(config.callers.items())},
            "tracker_backend": (dict(vars(config.tracker_backend)) if config.tracker_backend else "github"),
        },
        indent=2,
        sort_keys=True,
    )
