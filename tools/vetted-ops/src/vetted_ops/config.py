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

import errno
import json
import os
import pwd
import re
import stat
import tomllib
from dataclasses import dataclass
from pathlib import Path

from . import layers
from .tracker_backends import PLATFORMS, TrackerBackend, backend_dir

#: `owner/name`, conservative on both halves.
_REPO = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,100}/[A-Za-z0-9][A-Za-z0-9._-]{0,100}$")
#: A Jira project key.
_JIRA_KEY = re.compile(r"^[A-Z][A-Z0-9_]{0,30}$")

DEFAULT_RELATIVE_PATH = Path(".apache-magpie-overrides/tools/vetted-ops/config.toml")
#: The same policy in a personal layer, for a maintainer whose project has not
#: adopted Magpie. It grants nothing `--config` does not: the policy supplies
#: data only, never code (see `tracker_backends`).
PERSONAL_RELATIVE_PATH = Path("tools/vetted-ops/config.toml")
#: Where the user keeps the policies the write entry points may act on, under
#: the account's home directory. Outside every sandbox-writable root, and
#: `Edit`-denied, so neither a sandboxed command nor the agent's file tools can
#: put a policy there; a renamed directory or a symlink elsewhere cannot either.
APPROVED_RELATIVE_DIR = Path(".config/apache-magpie/vetted-ops")


def account_home() -> Path:
    """The account's home directory from the password database, never `$HOME`,
    which whoever runs the command can set."""
    return Path(pwd.getpwuid(os.getuid()).pw_dir)


def approved_dir() -> Path:
    """The directory of approved policies for the write entry points."""
    return account_home() / APPROVED_RELATIVE_DIR


class TamperedPath(RuntimeError):
    """A symlink on the path, or something other than a regular file at its end."""


def read_regular_file(path: Path) -> bytes | None:
    """The bytes of the regular file at ``path``, or None if it does not exist.

    Every component is opened relative to the previous one with ``O_NOFOLLOW``,
    so a symlink anywhere on the path is refused and the file read is the very
    one checked: no window between a check and an open for a swap to land in.
    Raises `TamperedPath` for a symlink or a non-regular file.
    """
    parts = Path(os.path.abspath(path)).parts
    dir_fd = os.open(parts[0], os.O_RDONLY | os.O_DIRECTORY)
    try:
        for name in parts[1:-1]:
            try:
                next_fd = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=dir_fd)
            except FileNotFoundError:
                return None
            except OSError as exc:
                if exc.errno in (errno.ELOOP, errno.ENOTDIR):
                    raise TamperedPath(
                        f"{path}: {name!r} on its path is a symlink or not a directory"
                    ) from None
                raise
            os.close(dir_fd)
            dir_fd = next_fd
        try:
            fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=dir_fd)
        except FileNotFoundError:
            return None
        except OSError as exc:
            if exc.errno == errno.ELOOP:
                raise TamperedPath(f"{path} is a symlink") from None
            raise
    finally:
        os.close(dir_fd)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise TamperedPath(f"{path} is not a regular file")
        with os.fdopen(fd, "rb", closefd=False) as handle:
            return handle.read()
    finally:
        os.close(fd)


def _approved(data: bytes) -> bool:
    """Whether ``data`` is byte-for-byte one of the policies in `approved_dir`."""
    root = approved_dir()
    try:
        names = sorted(os.listdir(root))
    except OSError:
        return False
    for name in names:
        if not name.endswith(".toml"):
            continue
        try:
            if read_regular_file(root / name) == data:
                return True
        except (TamperedPath, OSError):
            continue
    return False


def _expand_home(raw: str) -> Path:
    """`~` and `~/…` against `account_home`, not `$HOME`."""
    if raw == "~":
        return account_home()
    if raw.startswith("~/"):
        return account_home() / raw[2:]
    return Path(raw)


def _protected(layer: Path) -> bool:
    """A personal layer whose policy the sandbox profile's deny globs cover.

    `//**/.git/**/apache-magpie/…`, `//**/.svn/apache-magpie/…` and
    `//**/.apache-magpie-local/…`; a git directory elsewhere (a custom
    `gitdir:`) would leave the policy agent-writable, so it is not read.
    """
    if layer.name == layers.LOCAL_DIR:
        return True
    return layer.name == layers.GIT_HOME_NAME and (
        ".git" in layer.parent.parts or layer.parent.name == ".svn"
    )


def candidates(base: Path) -> list[Path]:
    """Where the policy is looked for, first match wins: committed, then personal."""
    personal = [layer / PERSONAL_RELATIVE_PATH for layer in layers.personal_layers(base) if _protected(layer)]
    return [base / DEFAULT_RELATIVE_PATH, *personal]


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

    Only data comes from the policy — the backend's pinned target. The program
    and the backend's code are fixed in tracker_backends.py (the tool directory
    installed beside vetted-ops), so no policy — including one an agent wrote
    and passed with --config — can choose code to run.
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
    if "project" in raw:
        raise ConfigError(
            "[tracker] no longer takes 'project': the backend runs from the tool directory "
            "installed beside vetted-ops, never from a path a policy names"
        )
    trusted = backend_dir(platform)
    if not (trusted / "pyproject.toml").is_file():
        raise ConfigError(
            f"the {platform} tracker backend is not installed beside vetted-ops (expected {trusted}); "
            "re-run the secure-setup install or update to copy it"
        )
    project = str(trusted)
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
        jira_issue_type=_one_line(raw, "jira_issue_type") if "jira_issue_type" in raw else "Bug",
        jira_cloud=deployment == "cloud",
    )


def _discover(base: Path) -> tuple[Path, bytes]:
    tried = candidates(base)
    committed, personal = tried[0], tried[1:]
    # A symlink on the committed path would redirect the read to a file the
    # agent can write. Refuse rather than fall through, so it shows.
    try:
        data = read_regular_file(committed)
    except TamperedPath as exc:
        raise ConfigError(f"refusing the vetted-ops config: {exc}") from None
    if data is not None:
        return committed, data
    for candidate in personal:
        try:
            data = read_regular_file(candidate)
        except TamperedPath:
            continue
        if data is not None:
            return candidate, data
    raise ConfigError("no vetted-ops config at " + " or ".join(str(c) for c in tried))


def load(path: Path | None = None, *, cwd: Path | None = None, approved_only: bool = False) -> Config:
    """Load and validate the policy.

    ``approved_only`` is for the write entry points, which run outside the
    sandbox: the policy found must be byte-for-byte a file the user placed in
    `approved_dir`. The working directory is the caller's choice, so whatever
    discovery finds there, a planted copy included, is only ever a policy the
    user already approved.
    """
    base = (cwd or Path.cwd()).resolve()
    if path is not None:
        if approved_only:
            raise ConfigError("an explicit config path is not accepted where only an approved policy may act")
        resolved = path
        if not resolved.is_file():
            raise ConfigError(f"no vetted-ops config at {resolved}")
        data = resolved.read_bytes()
    else:
        resolved, data = _discover(base)

    if approved_only and not _approved(data):
        raise ConfigError(
            f"the policy at {resolved} is not an approved copy in {approved_dir()}; the write entry "
            "points run outside the sandbox, so they act only on a policy you placed there yourself. "
            f"Review it, then in your own terminal: mkdir -p {approved_dir()} && "
            f"cp {resolved} {approved_dir()}/<name>.toml (repeat after every change to the policy)"
        )

    try:
        raw = tomllib.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        raise ConfigError(f"the vetted-ops config at {resolved} is not valid TOML: {exc}") from None

    repos = raw.get("repos")
    if not isinstance(repos, dict):
        raise ConfigError("config needs a [repos] table declaring at least 'upstream'")

    workspace_raw = raw.get("workspace")
    if not isinstance(workspace_raw, str) or not workspace_raw:
        raise ConfigError("config needs a top-level 'workspace' path for body files")
    workspace = _expand_home(workspace_raw)
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
