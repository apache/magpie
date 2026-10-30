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

"""The isolated (secure agent) setup: has it changed, and is a re-check due?

The secure setup is installed per machine, from framework files: the
sandbox wrapper and helper scripts, the agent-guard engine, the container
gateway, and the dogfooded `.claude/settings.json`.  When a framework
upgrade changes any of those, the user's installed copy can be behind
without anything saying so.  `setup-isolated-setup-update` is the skill
that finds that drift, so the pre-flight proposes it:

* **once per change** — the fingerprint of those files moved since the
  update skill last ran on this machine; and
* **on a timer** — the update was last run or last suggested longer ago
  than the configured interval (a week by default), because the pinned
  tools and harness move upstream whatever this repository does.

Only when the setup is **used here**: an `isolated_setup` block in the
local stamp (written by the install and update skills), or a project
`.claude/settings*.json` that enables the sandbox.  Anyone else is never
told about it.

The fingerprint is computed from the framework source when this checkout
has it — the framework's own tree, or a pinned snapshot under
`.apache-magpie/` — and otherwise taken from the constant generated into
`isolated_fingerprint.py`.  The constant is what a marketplace install
sees: the copy of this package in the personal config layer (see
`layers.py`) is refreshed by `/magpie-setup upgrade`, which is exactly the
moment the constant moves.

Run as a module it also records what happened, so nothing hand-writes a
fingerprint into the stamp:

    python3 -m setup_preflight.isolated record-update     # the update skill ran
    python3 -m setup_preflight.isolated record-reminder   # the suggestion was shown
    python3 -m setup_preflight.isolated fingerprint       # print the current value
    python3 -m setup_preflight.isolated configured        # {"configured": true|false}
    python3 -m setup_preflight.isolated session-start     # the SessionStart hook's output
    python3 -m setup_preflight.isolated write-constant    # framework repo only (prek)
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import re
import secrets
import stat
import subprocess
import sys
from datetime import date
from pathlib import Path

from .layers import OVERRIDES_DIR, adopted, config_layers, personal_dir, personal_layers

#: The files a secure-setup install copies or mirrors, relative to the
#: framework root.  Documentation is left out on purpose: a reworded
#: paragraph changes nothing on the user's machine and must not send them
#: to re-run the update.
SOURCES: tuple[str, ...] = (
    ".claude/settings.json",
    "tools/agent-guard/src",
    "tools/agent-isolation",
    "tools/container-gateway/src",
)
_SKIP_DIRS = frozenset({"__pycache__", "tests", ".pytest_cache", ".mypy_cache", ".ruff_cache"})
_SKIP_SUFFIXES = (".md", ".pyc")
_SKIP_NAMES = frozenset({".DS_Store"})

#: The directory whose presence marks a tree as carrying the framework source.
_MARKER = "tools/agent-isolation"
SNAPSHOT_DIR = ".apache-magpie"

STAMP_NAME = "reconciled.json"
BLOCK = "isolated_setup"

DEFAULT_INTERVAL_DAYS = 7
INTERVAL_KEY = "isolated_setup_update_interval_days"
_INTERVAL_RE = re.compile(rf"^\s*{INTERVAL_KEY}\s*:\s*(\d+)\b", re.M)


def _files(base: Path) -> list[Path]:
    found: list[Path] = []
    for source in SOURCES:
        path = base / source
        if path.is_file():
            found.append(path)
            continue
        if not path.is_dir():
            continue
        for candidate in path.rglob("*"):
            relative = candidate.relative_to(base)
            if not candidate.is_file() or _SKIP_DIRS.intersection(relative.parts):
                continue
            if candidate.name in _SKIP_NAMES or candidate.name.endswith(_SKIP_SUFFIXES):
                continue
            found.append(candidate)
    return sorted(found, key=lambda p: p.relative_to(base).as_posix())


def compute(base: Path) -> str | None:
    """The fingerprint of `SOURCES` under `base`, or `None` if none exist."""
    files = _files(base)
    if not files:
        return None
    digest = hashlib.sha256()
    for path in files:
        digest.update(path.relative_to(base).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()[:16]


def shipped() -> str | None:
    """The fingerprint generated into this package, if the constant exists."""
    try:
        from .isolated_fingerprint import FRAMEWORK_FINGERPRINT
    except ImportError:
        return None
    return FRAMEWORK_FINGERPRINT


def current(root: Path) -> str | None:
    """The framework's current fingerprint, as seen from this checkout."""
    for base in (root, root / SNAPSHOT_DIR):
        if (base / _MARKER).is_dir():
            return compute(base)
    return shipped()


def _sandbox_enabled(paths: list[Path]) -> bool:
    for path in paths:
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        sandbox = loaded.get("sandbox") if isinstance(loaded, dict) else None
        if isinstance(sandbox, dict) and sandbox.get("enabled") is True:
            return True
    return False


def sandbox_enabled_in_project(root: Path) -> bool:
    return _sandbox_enabled([root / ".claude" / name for name in ("settings.json", "settings.local.json")])


def configured(root: Path, home: Path | None = None) -> bool:
    """Whether the isolated setup is in place for this project on this machine.

    The stamp the install and update skills write, or a sandbox the project's
    or the user's Claude Code settings enable. The install offers a whole-user
    scope, which leaves no trace in the project, hence the user settings,
    `settings.local.json` included as `sandbox-status-line.sh` reads it. A
    file that cannot be read counts as not configured: inside the sandbox the
    user's settings are read-denied, so callers that run there see `False` and
    must treat it as "not known to be configured", never as proof of absence.
    """
    block = _load_stamp(root).get(BLOCK)
    if isinstance(block, dict) and block:
        return block.get("enabled") is not False
    user = (home if home is not None else Path.home()) / ".claude"
    return sandbox_enabled_in_project(root) or _sandbox_enabled(
        [user / name for name in ("settings.json", "settings.local.json")]
    )


#: Shown to the user once per session, at session start, while the isolated
#: setup is not configured. Not a blocker: trying Magpie out does not need it.
UNCONFIGURED_WARNING = """\
Apache Magpie: the isolated setup is not configured on this machine.

You do not need it to try Magpie out. If you plan to use Magpie for longer, \
enable it: run /magpie-setup:isolated-setup-install.

Why it matters: Magpie skills read text written by other people - pull \
requests, issues, comments, mailing-list threads, attachments. Any of it can \
hide instructions aimed at your agent (prompt injection). Without the isolated \
setup the agent runs with your full access: it can read your credentials (SSH \
keys, GitHub and cloud tokens, .env files), reach any host on the network, and \
act in your name. An injected instruction could leak those secrets or private \
content such as unreleased security reports, or push, comment, close or merge \
as you.

Until it is enabled, do not use Magpie on untrusted content - pull requests, \
issues, comments or mail from people you do not know - and read every command \
before you approve it."""

#: What the model is told alongside the warning, so it neither repeats the
#: warning on every turn nor forgets it at the moment it matters.
UNCONFIGURED_CONTEXT = (
    "The Apache Magpie isolated setup is not configured on this machine. The user was shown a "
    "warning about it at session start; do not repeat it unprompted. Before a Magpie skill reads "
    "pull requests, issues, comments, mail or other content written by people outside the project, "
    "remind the user once in this session that the isolated setup is off, and suggest "
    "/magpie-setup:isolated-setup-install."
)


WARNING_KEY = "isolation_warning"
_WARNING_OFF_RE = re.compile(rf"^\s*{WARNING_KEY}\s*:\s*off\b", re.M)


def warning_opted_out(root: Path) -> bool:
    """Whether the project turned the warning off when it adopted Magpie.

    Read from the committed `.apache-magpie-overrides/project.md` only: it is
    the project's choice, made at adoption, not one a personal layer makes.
    """
    try:
        text = (root / OVERRIDES_DIR / "project.md").read_text(encoding="utf-8")
    except OSError:
        return False
    return _WARNING_OFF_RE.search(text) is not None


def _adopted_root(start: Path) -> Path | None:
    """The adopted repository `start` sits in: up to the first `.git`, never past it."""
    for directory in (start, *start.parents):
        if adopted(directory):
            return directory
        if (directory / ".git").exists():
            return None
    return None


#: The sandbox write grant earlier versions of `sandbox-add-project-root.sh`
#: added. `~/.local/share/uv` holds the interpreters and tool venvs that hooks,
#: MCP servers and the excluded `uvx` / `uv run` commands run outside the
#: sandbox, so a sandboxed command able to write there plants code that runs
#: unsandboxed (apache/magpie#1785). The helper removes it whenever it runs;
#: the session start removes it from a project the helper has not run in since.
_UV_DATA_DIR = ".local/share/uv"


def _list_at(loaded: object, *keys: str) -> list[object]:
    """`loaded[k1][k2]...` when every step is an object and the end a list, else `[]`."""
    for key in keys:
        if not isinstance(loaded, dict):
            return []
        loaded = loaded.get(key)
    return loaded if isinstance(loaded, list) else []


def _stale_uv_writes(home: Path) -> frozenset[str]:
    absolute = str(home / _UV_DATA_DIR)
    return frozenset({absolute, absolute + "/", "~/" + _UV_DATA_DIR, "~/" + _UV_DATA_DIR + "/"})


def _covers_uv_data_dir(entry: str, home: Path, base: Path) -> bool:
    """Whether a write-grant entry makes `~/.local/share/uv` (or a part of it) writable."""
    text = entry.strip()
    if text.startswith("//"):
        text = text[1:]
    if text == "~" or text.startswith("~/"):
        text = str(home) + text[1:]
    path = Path(text) if text.startswith("/") else base / text
    target = home / _UV_DATA_DIR
    for candidate in (path, target):
        other = target if candidate is path else path
        if candidate == other or other in candidate.parents:
            return True
    return False


def _checkout(root: Path) -> Path:
    """The session's own checkout: the nearest directory holding a `.git`.

    Never the main checkout a linked worktree's `.git` file names: that file is
    as writable from the sandbox as the worktree, so following it would let
    sandboxed code pick the directory this unsandboxed hook rewrites. The main
    checkout is cleaned when a session opens there.
    """
    for directory in (root, *root.parents):
        if (directory / ".git").exists():
            return directory
    return root


_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)
_DIRECTORY = getattr(os, "O_DIRECTORY", 0)


def _drop_from_local_settings(local: Path, stale: frozenset[str]) -> str | None:
    """Remove `stale` from `local`'s allowWrite; `"removed"`, `"refused"`, or None if absent.

    The project tree is sandbox-writable and this runs outside the sandbox, so
    everything goes through one descriptor for `.claude`, opened without
    following a symlink: the read, a fresh temporary file (O_EXCL, random name)
    and the rename all stay in that directory, whatever happens to its path
    meanwhile. `.claude` or the file being a symlink refuses the rewrite.
    """
    try:
        dfd = os.open(local.parent, os.O_RDONLY | _DIRECTORY | _NOFOLLOW)
    except OSError:
        return None if not local.parent.is_symlink() else "refused"
    try:
        try:
            fd = os.open(local.name, os.O_RDONLY | _NOFOLLOW, dir_fd=dfd)
        except OSError:
            return "refused" if os.path.islink(local) else None
        with os.fdopen(fd, encoding="utf-8") as handle:
            try:
                loaded = json.load(handle)
            except (json.JSONDecodeError, UnicodeDecodeError):
                return None
        writes = _list_at(loaded, "sandbox", "filesystem", "allowWrite")
        if not isinstance(loaded, dict) or not any(w in stale for w in writes if isinstance(w, str)):
            return None
        loaded["sandbox"]["filesystem"]["allowWrite"] = [w for w in writes if w not in stale]
        tmp_name = f".settings.local.{secrets.token_hex(8)}.tmp"
        try:
            tfd = os.open(tmp_name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | _NOFOLLOW, 0o600, dir_fd=dfd)
        except OSError:
            return "refused"
        try:
            with os.fdopen(tfd, "w", encoding="utf-8") as handle:
                handle.write(json.dumps(loaded, indent=2) + "\n")
            os.replace(tmp_name, local.name, src_dir_fd=dfd, dst_dir_fd=dfd)
        except OSError:
            # Best effort: a temporary file left behind is inert, and the
            # refusal is reported either way.
            with contextlib.suppress(OSError):
                os.unlink(tmp_name, dir_fd=dfd)
            return "refused"
        return "removed"
    finally:
        os.close(dfd)


def drop_stale_uv_writes(root: Path, home: Path | None = None) -> list[str]:
    """Remove the old `~/.local/share/uv` write grant; report what was removed or must be.

    Only from the session checkout's `.claude/settings.local.json`, the
    per-machine file the project-root helper maintains, and only the exact
    entries it once added. Removing them only narrows the sandbox, so a tracked
    copy of the file is safe to rewrite too: the change shows in `git diff`.
    No git command runs here: the repository's own config is sandbox-writable.
    A broader grant, or one in user-scope or committed settings, is reported for
    the user to remove: those files are theirs, not the helper's. Hooks run
    outside the sandbox, so every file here is readable.
    """
    home = home if home is not None else Path.home()
    stale = _stale_uv_writes(home)
    messages: list[str] = []
    directory = _checkout(root)
    local = directory / ".claude" / "settings.local.json"
    outcome = _drop_from_local_settings(local, stale)
    if outcome == "removed":
        messages.append(f"removed the ~/.local/share/uv sandbox write grant from {local}")
    elif outcome == "refused" and any(_covers_uv_data_dir(e, home, directory) for e in _grants_in(local)):
        messages.append(
            f"{local} grants sandbox writes to ~/.local/share/uv and could not be rewritten safely; remove it by hand"
        )
    for settings in (directory / ".claude" / "settings.json", local):
        messages.extend(_report_covering_grants(settings, directory, home, stale))
    user = home / ".claude"
    for name in ("settings.json", "settings.local.json"):
        messages.extend(_report_covering_grants(user / name, user, home, frozenset()))
    return messages


def _grants_in(settings: Path) -> list[str]:
    try:
        loaded = json.loads(settings.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return []
    return [e for e in _list_at(loaded, "sandbox", "filesystem", "allowWrite") if isinstance(e, str)]


def _report_covering_grants(settings: Path, base: Path, home: Path, removable: frozenset[str]) -> list[str]:
    try:
        loaded = json.loads(settings.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(loaded, dict):
        return []
    entries = [
        *_list_at(loaded, "sandbox", "filesystem", "allowWrite"),
        *_list_at(loaded, "permissions", "additionalDirectories"),
    ]
    left = [
        e for e in entries if isinstance(e, str) and e not in removable and _covers_uv_data_dir(e, home, base)
    ]
    return [
        f"{settings} makes ~/.local/share/uv writable to the sandbox ({e!r}); remove it by hand" for e in left
    ]


def _git_config(home: Path, *args: str) -> str | None:
    """`git config <args>` for the user's own global config, run from $HOME.

    Only `--global` reads go through here; a repository's config is parsed
    directly (`_rewrite_repo_config`), never handed to git.
    """
    env = {
        k: v
        for k, v in os.environ.items()
        if k not in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_CONFIG")
    }
    try:
        done = subprocess.run(
            ["git", "config", *args],
            cwd=home,
            env=env,
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return done.stdout.strip() if done.returncode == 0 else None


def _resolved(path: str, base: Path, home: Path) -> Path:
    text = str(home) + path[1:] if path == "~" or path.startswith("~/") else path
    candidate = Path(text) if text.startswith("/") else base / text
    return Path(os.path.realpath(candidate))


_SECTION_RE = re.compile(r'^\s*\[\s*([A-Za-z0-9.-]+)\s*(?:"([^"]*)")?\s*\](.*)$')
_HOOKS_PATH_RE = re.compile(r"^\s*hookspath\s*=\s*(.*?)\s*$", re.I)


def _shown(value: str) -> str:
    """A config value fit for a message the model reads: quoted, short, no control characters."""
    cleaned = "".join(ch for ch in value if ch.isprintable())[:120]
    return repr(cleaned)


def _core_hooks_path_lines(text: str) -> tuple[list[int], list[str]] | None:
    """Indices and values of `[core] hooksPath` lines, or None when the file is not plain enough.

    Only a plain file is rewritten: an `include` directive, a continued or
    unparsable line means the value may come from elsewhere, so the caller only
    reports.
    """
    indices: list[int] = []
    values: list[str] = []
    section = ""
    for number, line in enumerate(text.splitlines()):
        stripped = line.strip()
        if not stripped or stripped[0] in "#;":
            continue
        header = _SECTION_RE.match(line)
        if header:
            rest = header.group(3).strip()
            # Git allows a key after the header on the same line; anything but a
            # comment there is not plain enough to rewrite.
            if rest and rest[0] not in "#;":
                return None
            name = header.group(1).lower()
            if name in ("include", "includeif"):
                return None
            section = name if header.group(2) is None else f"{name}.{header.group(2)}"
            continue
        if stripped.startswith("["):
            return None  # a header this parser does not understand
        if line.rstrip().endswith("\\"):
            return None
        match = _HOOKS_PATH_RE.match(line)
        if section == "core" and not line.lstrip().startswith("[") and match:
            value = match.group(1)
            if len(value) >= 2 and value[0] == value[-1] == '"':
                value = value[1:-1]
            indices.append(number)
            values.append(value)
    return indices, values


def _rewrite_repo_config(checkout: Path, home: Path, own_hooks: Path) -> list[str]:
    """Drop `core.hooksPath` from `<checkout>/.git/config` when it names `own_hooks`.

    The checkout is sandbox-writable and this runs outside the sandbox, so no
    git command touches it: `.git` and `config` are opened without following a
    symlink through one directory descriptor, and the rewrite goes to a fresh
    temporary file renamed inside that directory.
    """
    try:
        cfd = os.open(checkout, os.O_RDONLY | _DIRECTORY)
    except OSError:
        return []
    try:
        try:
            gfd = os.open(".git", os.O_RDONLY | _DIRECTORY | _NOFOLLOW, dir_fd=cfd)
        except OSError:
            return []  # a linked worktree's .git file, a symlink, or none
        try:
            try:
                fd = os.open("config", os.O_RDONLY | _NOFOLLOW, dir_fd=gfd)
            except OSError:
                return []
            original_mode = stat.S_IMODE(os.fstat(fd).st_mode)
            with os.fdopen(fd, encoding="utf-8", errors="strict") as handle:
                try:
                    text = handle.read()
                except UnicodeDecodeError:
                    text = None
            config = checkout / ".git" / "config"
            if text is None:
                return [
                    f"{config} could not be read as text; check that its core.hooksPath skips no hooks you need"
                ]
            parsed = _core_hooks_path_lines(text)
            if parsed is None:
                return [
                    f"{config} may set core.hooksPath (it uses includes); check it skips no hooks you need"
                ]
            indices, values = parsed
            if not values:
                return []
            if len(values) == 1 and _resolved(values[0], checkout, home) == own_hooks:
                lines = text.splitlines(keepends=True)
                kept = "".join(line for number, line in enumerate(lines) if number != indices[0])
                # The result must read back plain and without the key, or nothing is written.
                if _core_hooks_path_lines(kept) != ([], []):
                    return [f"{config} sets core.hooksPath={_shown(values[0])}; unset it by hand"]
                tmp_name = f".config.{secrets.token_hex(8)}.tmp"
                try:
                    tfd = os.open(
                        tmp_name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | _NOFOLLOW, 0o600, dir_fd=gfd
                    )
                except OSError:
                    return [f"{config} sets core.hooksPath={_shown(values[0])}; unset it by hand"]
                try:
                    with os.fdopen(tfd, "w", encoding="utf-8") as handle:
                        handle.write(kept)
                        # The config keeps the mode it had, whatever this process's umask.
                        os.fchmod(handle.fileno(), original_mode)
                    os.replace(tmp_name, "config", src_dir_fd=gfd, dst_dir_fd=gfd)
                except OSError:
                    with contextlib.suppress(OSError):
                        os.unlink(tmp_name, dir_fd=gfd)
                    return [f"{config} sets core.hooksPath={_shown(values[0])}; unset it by hand"]
                return [
                    f"removed core.hooksPath={_shown(values[0])} from {config}; the dispatcher chains to it anyway"
                ]
            return [
                f"{config} sets core.hooksPath={_shown(values[-1])}, which skips the whole-user dispatcher "
                "(and its host-only prek home); unset it unless you need it"
            ]
        finally:
            os.close(gfd)
    finally:
        os.close(cfd)


def drop_redundant_hooks_path(root: Path, home: Path | None = None) -> list[str]:
    """Remove a repository's own `core.hooksPath` that hides the whole-user dispatcher.

    With the whole-user dispatcher installed (global `core.hooksPath` at
    `~/.claude/git-hooks`, its `post-checkout` the dispatcher), a repository
    that sets `core.hooksPath` to its own `.git/hooks` (some `prek install`
    runs do) skips the dispatcher, and with it the host-only prek home for
    hooks run outside the sandbox. The dispatcher chains to `.git/hooks`
    anyway, so that value is redundant and is removed; any other value is only
    reported. Main checkouts only: a linked worktree's config lives in a common
    directory its sandbox-writable `.git` file names.
    """
    home = home if home is not None else Path.home()
    hooks_dir = home / ".claude" / "git-hooks"
    global_path = _git_config(home, "--global", "--get", "core.hooksPath")
    if not global_path or _resolved(global_path, home, home) != Path(os.path.realpath(hooks_dir)):
        return []
    if Path(os.path.realpath(hooks_dir / "post-checkout")).name != "git-hook-dispatcher.sh":
        return []
    checkout = _checkout(root)
    return _rewrite_repo_config(checkout, home, Path(os.path.realpath(checkout / ".git" / "hooks")))


#: Shown when the session start removed or found a repository-level hooks path.
HOOKS_PATH_HEADER = (
    "Apache Magpie: a repository-level core.hooksPath bypasses the whole-user git-hook dispatcher, "
    "so hooks run outside the sandbox would use prek environments the sandbox can write (apache/magpie#1792)."
)


#: Shown when the session start removed or found a `~/.local/share/uv` grant.
STALE_UV_HEADER = (
    "Apache Magpie: ~/.local/share/uv holds the interpreters and tools uv runs outside the sandbox, "
    "so the sandbox must not write there (apache/magpie#1785)."
)


def session_start(root: Path, notice: str = "", home: Path | None = None) -> str:
    """What the SessionStart hook prints: its own notice, plus the warning while unconfigured.

    The hook fires once per session, which is the cadence the warning wants.
    Only in a repository that has adopted Magpie, and not when that project
    opted out at adoption. Hooks run outside the sandbox, so the user's
    settings are readable here and "not configured" means what it says.
    Plain text keeps the hook's original output when there is nothing to
    warn about.

    Every session start also drops the old `~/.local/share/uv` write grant
    (`drop_stale_uv_writes`) and a repository-level `core.hooksPath` that
    only hides the whole-user dispatcher (`drop_redundant_hooks_path`),
    adopted or not, and tells the user what it did.
    """
    stale = drop_stale_uv_writes(root.resolve(), home)
    stale_message = "\n".join([STALE_UV_HEADER, *(f"- {m}" for m in stale)]) if stale else ""
    hooks = drop_redundant_hooks_path(root.resolve(), home)
    hooks_message = "\n".join([HOOKS_PATH_HEADER, *(f"- {m}" for m in hooks)]) if hooks else ""
    project = _adopted_root(root.resolve())
    messages = [m for m in (stale_message, hooks_message) if m]
    contexts = [part for part in (notice, stale_message, hooks_message) if part]
    if project is not None and not warning_opted_out(project) and not configured(project, home):
        messages.append(UNCONFIGURED_WARNING)
        contexts.append(UNCONFIGURED_CONTEXT)
    if not messages:
        return notice
    message = "\n\n".join(messages)
    context = "\n\n".join(contexts)
    return json.dumps(
        {
            "systemMessage": message,
            "hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": context},
        }
    )


def interval_days(root: Path) -> int:
    """`isolated_setup_update_interval_days`, personal config first.

    Read from `project.md` in each config layer in turn (`layers.py`:
    personal, legacy in-tree, then `.apache-magpie-overrides/`); a week when
    none sets it.  `0` turns the timed reminder off (a change is still
    reported).
    """
    for directory in config_layers(root):
        path = directory / "project.md"
        try:
            match = _INTERVAL_RE.search(path.read_text(encoding="utf-8"))
        except OSError:
            continue
        if match:
            return int(match.group(1))
    return DEFAULT_INTERVAL_DAYS


# --- recording ----------------------------------------------------------------------


def _stamp_path(root: Path) -> Path:
    return personal_dir(root) / STAMP_NAME


def _load_stamp(root: Path) -> dict[str, object]:
    """The stamp as read: personal layer first, then the legacy in-tree one."""
    for layer in personal_layers(root):
        try:
            loaded = json.loads((layer / STAMP_NAME).read_text(encoding="utf-8"))
        except FileNotFoundError:
            continue
        except (OSError, json.JSONDecodeError):
            return {}
        return loaded if isinstance(loaded, dict) else {}
    return {}


def record(root: Path, event: str, today: date | None = None) -> dict[str, object]:
    """Write what just happened into the local stamp and return the block.

    `update` — the update skill ran here: its fingerprint is now the one it
    checked against.  `reminder` — the suggestion was shown, taken or not,
    which re-arms both the timer and this particular change.

    The stamp is written to the personal layer, which this creates when it
    does not exist yet (inside the git directory for an unadopted
    repository, never the working tree).  A stamp still in the legacy
    in-tree directory is read and carried over, not deleted.
    """
    stamp = _load_stamp(root)
    raw = stamp.get(BLOCK)
    block: dict[str, object] = dict(raw) if isinstance(raw, dict) else {}
    day = (today or date.today()).isoformat()
    fingerprint = current(root)
    if event == "update":
        block["updated_at"] = day
        if fingerprint:
            block["fingerprint"] = fingerprint
    elif event == "reminder":
        block["reminded_at"] = day
    else:
        raise ValueError(f"unknown event {event!r}")
    if fingerprint:
        block["acknowledged"] = fingerprint
    stamp[BLOCK] = block
    path = _stamp_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(stamp, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)
    return block


# --- the generated constant ---------------------------------------------------------

CONSTANT_PATH = Path(__file__).with_name("isolated_fingerprint.py")
_CONSTANT_TEMPLATE = '''\
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

"""Generated by `python -m setup_preflight.isolated write-constant`. Do not edit.

The isolated-setup fingerprint of the framework this package shipped with,
for installs that do not carry the framework source (see `isolated.py`).
"""

FRAMEWORK_FINGERPRINT = "{value}"
'''


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="setup_preflight.isolated", description=__doc__.split("\n")[0])
    parser.add_argument(
        "action",
        choices=[
            "fingerprint",
            "configured",
            "session-start",
            "record-update",
            "record-reminder",
            "write-constant",
            "check-constant",
        ],
    )
    parser.add_argument("--project-root", default=".", type=Path)
    parser.add_argument("--notice", default="", help="session-start: the hook's own notice, passed through")
    args = parser.parse_args(argv)
    root: Path = args.project_root

    if args.action == "fingerprint":
        print(current(root) or "")
        return 0
    if args.action == "configured":
        print(json.dumps({"configured": configured(root)}))
        return 0
    if args.action == "session-start":
        output = session_start(root, args.notice)
        if output:
            print(output)
        return 0
    if args.action in ("record-update", "record-reminder"):
        block = record(root, args.action.removeprefix("record-"))
        print(json.dumps({BLOCK: block}, indent=2, sort_keys=True))
        return 0

    value = compute(root)
    if value is None:
        print(f"{args.action}: no isolated-setup sources under {root}", file=sys.stderr)
        return 2
    wanted = _CONSTANT_TEMPLATE.format(value=value)
    have = CONSTANT_PATH.read_text(encoding="utf-8") if CONSTANT_PATH.exists() else ""
    if have == wanted:
        return 0
    if args.action == "check-constant":
        print(f"{CONSTANT_PATH.name} is stale; run write-constant", file=sys.stderr)
        return 1
    CONSTANT_PATH.write_text(wanted, encoding="utf-8")
    print(f"{CONSTANT_PATH.name}: {value}")
    return 1  # a fixer that changed a file fails the hook, as prek expects


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
