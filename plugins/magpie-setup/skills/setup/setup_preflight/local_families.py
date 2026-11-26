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

"""Families enabled for this user everywhere, but not adopted by this project.

A family enabled in the user-scope Claude Code settings
(`~/.claude/settings.json` → `enabledPlugins`) loads its skills in every
project, including an adopted one whose committed `.apache-magpie.lock`
floor does not list it.  That is not always wrong: `adopt.md` recommends
keeping `magpie-contributor-growth` off the floor and installing it per
maintainer at user scope.  So absence from the floor never means
*disable*; it means *ask once*.

Only a marketplace floor (`method: marketplace`) is compared: a pinned
snapshot lock lists no plugins, and the framework checkout's own
`method: local` lock has its skills in the working tree.

`setup update` → *Reconcile the local agent settings* asks, per family,
whether to keep it here or hide it in this worktree with
`"enabledPlugins": {"<plugin>@apache-magpie": false}` in
`.claude/settings.local.json`.  In a main checkout the hide also covers its
linked worktrees, which load the main checkout's settings first
(`layers.project_settings`).  The answer is kept under `local_families` in
`reconciled.json` in this checkout's own layer (`layers.stamp_dir`), and
read merged across the personal layers, so a linked worktree also sees its
main checkout's without copying them:

    "local_families": {
      "magpie-contributor-growth": {"choice": "keep", "at": "2026-11-25"},
      "magpie-pr-management": {"choice": "disable", "at": "2026-11-25",
                               "worktrees": ["/path/to/worktree"]},
      "magpie-repo-health": {"choice": "hinted", "at": "2026-11-25"}
    }

`keep` is never asked again.  `disable` is not asked again either; a
worktree it was not yet applied in gets it as a ready answer to apply
(`.claude/settings.local.json` is per worktree, the personal layer is
not).  `hinted` only records that the pre-flight's one-line hint was
shown, so it does not repeat; the question itself is still open.  Once
the project adopts a hidden family, `restore` proposes removing the hide
Magpie applied, and `restored` records it; should the floor drop the
family again, the question is asked anew.

Nothing here writes a settings file: Claude Code does not let an agent
write its own settings, so the caller stages the merged file and hands
the user the copy command.  An `enabledPlugins` entry for the plugin in
any project settings file is the user's own unless it is the `false`
Magpie proposed, and is never proposed for change.

Inside a sandbox that denies the user-scope settings, `candidates` answers
`user-settings-unreadable` with the path; the caller reads that file with
its own file-read tool and passes only its `enabledPlugins` block back on
stdin (`--user-settings -`), never writing the file anywhere.

Run as a module:

    python3 -m setup_preflight.local_families candidates --project-root <worktree> [--user-settings <file>|-]
    python3 -m setup_preflight.local_families record --project-root <worktree> \\
        --plugin magpie-pr-management --choice keep|disable|hinted|restored
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Iterable, Mapping
from datetime import date
from pathlib import Path
from typing import Any

from .gateway import SUPPORTED, _read_regular
from .layers import LOCAL_DIR, LOCK_NAME, personal_layers, project_settings, stamp_dir, write_stamp
from .lockfile import MalformedLock, load

MARKETPLACE = "apache-magpie"
BLOCK = "local_families"
STAMP_NAME = "reconciled.json"
CHOICES = ("keep", "disable", "hinted", "restored")
#: Answers a later `hinted` never replaces and that win the merge across
#: layers.  `restored` (a hide removed once the family was adopted) closes
#: the `disable` without closing the question: should the floor drop the
#: family again, it is asked anew, never re-hidden in silence.
DECIDED = frozenset({"keep", "disable", "restored"})
#: Families that are always on the floor of an adopted project.
ALWAYS_ADOPTED = frozenset({"setup"})
#: The only lock method whose `plugins:` list is a floor to compare with.
FLOOR_METHOD = "marketplace"
#: The harness whose settings files this module reads and proposes.
HARNESS = "claude"
#: The only settings file Magpie proposes a hide in.
LOCAL_SETTINGS_NAME = "settings.local.json"


def family_plugins() -> frozenset[str]:
    """Every family's plugin name, `magpie-<family>`, from the generated family map.

    Only skill families: substrate plugins (`magpie-agent-guard`,
    `magpie-vetted-ops`, `magpie-security-tools`, …) are not in the map,
    so they can never be offered for hiding.
    """
    try:
        from .families import SKILL_FAMILIES
    except ImportError:
        return frozenset()
    return frozenset(f"magpie-{family}" for family in SKILL_FAMILIES.values() if family not in ALWAYS_ADOPTED)


def user_settings_path(env: Mapping[str, str] | None = None) -> Path | None:
    """The user-scope Claude Code settings file, honouring `CLAUDE_CONFIG_DIR`.

    `None` when no absolute location can be found: an empty or relative
    `HOME` would otherwise resolve inside the repository under review and
    read its `.claude/settings.json` as the user's.
    """
    environ = os.environ if env is None else env
    configured = environ.get("CLAUDE_CONFIG_DIR", "")
    if configured and Path(configured).is_absolute():
        return Path(configured) / "settings.json"
    home = environ.get("HOME", "")
    if not home and env is None:
        try:
            home = str(Path.home())
        except RuntimeError:
            return None
    if not home or not Path(home).is_absolute():
        return None
    return Path(home) / ".claude" / "settings.json"


def parse_enabled(text: str) -> dict[str, object] | None:
    """`enabledPlugins` from a settings file's text, `{}` when it has none.

    `None` when the text is not a settings object or its `enabledPlugins`
    is not an object: unknown, never nothing enabled.
    """
    try:
        loaded = json.loads(text)
    except ValueError:
        return None
    if not isinstance(loaded, dict):
        return None
    block = loaded.get("enabledPlugins", {})
    return block if isinstance(block, dict) else None


def _read_file(path: Path) -> bytes:
    """The file's bytes, refusing anything but a regular file.

    Non-blocking on POSIX (`gateway._read_regular`), so a FIFO cannot hang
    the pre-flight; elsewhere `os.O_NONBLOCK` does not exist, and a
    regular-file check before the read stands in for it.
    """
    if SUPPORTED:
        return _read_regular(path)
    if path.exists() and not path.is_file():
        raise OSError(f"{path} is not a regular file")
    return path.read_bytes()


def _enabled_plugins(path: Path | None, *, missing_is_unknown: bool = False) -> dict[str, object] | None:
    """`enabledPlugins` from one settings file; `None` when it cannot be read.

    Read as a regular file only, non-blocking: a FIFO planted at a project
    settings path must not hang every skill's pre-flight.  Bytes that are
    not UTF-8 are unknown, never a crash.  A missing file is nothing
    enabled, or unknown with `missing_is_unknown`.
    """
    if path is None:
        return None
    try:
        raw = _read_file(path)
    except FileNotFoundError:
        return None if missing_is_unknown else {}
    except OSError:
        return None
    try:
        return parse_enabled(raw.decode("utf-8"))
    except UnicodeDecodeError:
        return None


def _user_enabled_plugins(path: Path | None) -> dict[str, object] | None:
    """`enabledPlugins` from the user-scope file; `None` when it cannot be known.

    A missing file is unknown too: a sandbox can make it look missing
    rather than denied (bubblewrap masks it, or a symlink into a denied
    directory dangles), and a user with a family enabled at user scope
    always has the file, so the caller's own read settles it.
    """
    return _enabled_plugins(path, missing_is_unknown=True)


def _key(plugin: str) -> str:
    return f"{plugin}@{MARKETPLACE}"


def user_enabled(settings: Mapping[str, object], plugins: Iterable[str]) -> list[str]:
    """The family plugins `settings` (an `enabledPlugins` block) turns on from our marketplace."""
    return sorted(plugin for plugin in plugins if settings.get(_key(plugin)) is True)


def adopted_floor(root: Path) -> list[str] | None:
    """The committed marketplace floor of an adopted project, or `None` when there is none.

    `None` for no lock, an unreadable one, a pinned snapshot (its lock
    lists no plugins) and the framework checkout's own `method: local`.
    """
    try:
        return _floor(root)
    except LockUnreadable:
        return None


class LockUnreadable(Exception):
    """The committed lock exists but cannot be read or parsed."""


def _floor(root: Path) -> list[str] | None:
    """Like `adopted_floor`, but raising `LockUnreadable` for a lock that exists and cannot be read."""
    try:
        lock = load(root / LOCK_NAME)
    except (MalformedLock, OSError, ValueError) as exc:
        raise LockUnreadable(str(exc)) from exc
    if lock is None or lock.method != FLOOR_METHOD:
        return None
    return list(lock.plugins)


def _read_stamp(directory: Path) -> dict[str, object]:
    """The stamp in `directory` for reading; anything unreadable reads as empty."""
    try:
        return _load_stamp(directory)
    except (OSError, ValueError):
        return {}


def _load_stamp(directory: Path) -> dict[str, object]:
    """The stamp in `directory` for rewriting: `{}` when missing, `ValueError` when unreadable.

    `record` rewrites the whole file, so a stamp it cannot parse is never
    replaced by one holding only its own key.
    """
    path = directory / STAMP_NAME
    try:
        raw = _read_file(path)
    except FileNotFoundError:
        return {}
    try:
        loaded = json.loads(raw.decode("utf-8"))
    except ValueError as exc:
        raise ValueError(f"{path} is not valid JSON; not overwriting it") from exc
    if not isinstance(loaded, dict):
        raise ValueError(f"{path} is not a JSON object; not overwriting it")
    return loaded


def decisions(root: Path) -> dict[str, dict[str, object]]:
    """The recorded `local_families` entries, merged across the personal layers.

    The layer answers are written to (`layers.stamp_dir`) comes first, then
    the others; the first layer naming a plugin wins, except that a decided
    answer from any layer beats a `hinted` one.  A linked worktree with a
    stamp of its own therefore still sees the decisions recorded in its
    main checkout, and its own one-time hint never hides one.
    """
    first = stamp_dir(root)
    order = [first, *(layer for layer in personal_layers(root) if layer != first)]
    merged: dict[str, dict[str, object]] = {}
    for layer in order:
        raw = _read_stamp(layer).get(BLOCK)
        if not isinstance(raw, dict):
            continue
        for name, entry in raw.items():
            if not isinstance(entry, dict):
                continue
            held = merged.get(name)
            if held is None or (held.get("choice") not in DECIDED and entry.get("choice") in DECIDED):
                merged[name] = entry
    return merged


def _own_layer_entries(root: Path, checkout: Path) -> dict[str, dict[str, object]]:
    """The `local_families` entries recorded in `checkout`'s own stamp, as `root` sees them.

    Only that checkout writes its own layer (a linked worktree's sandbox may
    only read its main checkout's), so only these entries may vouch for a
    hide in that checkout's settings.
    """
    own = (checkout / LOCAL_DIR).resolve()
    raw = _read_stamp(own).get(BLOCK)
    if not isinstance(raw, dict) or not any(own == layer.resolve() for layer in personal_layers(root)):
        return {}
    return {name: entry for name, entry in raw.items() if isinstance(entry, dict)}


def _worktree_id(root: Path) -> str:
    return str(root.resolve())


def _applied_by_magpie(
    plugin: str,
    source: Path | None,
    records_by_checkout: Mapping[str, Mapping[str, Mapping[str, object]]],
) -> bool:
    """Whether the effective entry, read from `source`, is a hide Magpie applied there.

    Magpie writes only `.claude/settings.local.json`, and records the hide
    as a `disable` listing that checkout, in that checkout's own stamp.
    Only that stamp vouches for it: a linked worktree can write its own
    stamp but never its main checkout's settings, so a record it holds
    never authorises a change there.  A `false` from any other file, or
    not vouched for this way, is the user's.
    """
    if source is None or source.name != LOCAL_SETTINGS_NAME:
        return False
    checkout = _worktree_id(source.parent.parent)
    entry = records_by_checkout.get(checkout, {}).get(plugin, {})
    worktrees = entry.get("worktrees")
    return entry.get("choice") == "disable" and isinstance(worktrees, list) and checkout in worktrees


def classify(
    *,
    user_settings: Mapping[str, object],
    floor: Iterable[str],
    recorded: Mapping[str, Mapping[str, object]],
    project_entries: Mapping[str, object],
    worktree: str,
    plugins: Iterable[str],
    entry_sources: Mapping[str, Path] | None = None,
    records_by_checkout: Mapping[str, Mapping[str, Mapping[str, object]]] | None = None,
) -> dict[str, list[str]]:
    """Split the families into what to ask, what to apply, and what to restore.

    * `ask` — user-enabled, not adopted, no `keep` / `disable` recorded:
      put the question to the user.
    * `apply` — `disable` recorded, but not yet in this worktree: carry the
      answer over without asking again.
    * `restore` — adopted since Magpie hid it: the effective `false` comes
      from a `settings.local.json` in a checkout the recorded `disable`
      lists in its own stamp (`entry_sources` names the file each entry
      is read from, `records_by_checkout` each checkout's own records), and
      it outranks the committed floor, so propose removing it.  A `false`
      Magpie did not apply there is the user's, and stays.
    * `restore_in_main` — the same, but the hide is in the main checkout's
      file: restored by reconciling there, where the `disable` is recorded.

    A family on the floor, recorded as `keep`, or already named in a
    project settings file is in neither `ask` nor `apply`: an existing
    `false` is the hide already in place, and any other value is the
    user's own choice.
    """
    plugins = list(plugins)
    on_floor = set(floor)
    sources = entry_sources or {}
    ask: list[str] = []
    apply: list[str] = []
    restorable = sorted(
        plugin
        for plugin in plugins
        if plugin in on_floor
        and project_entries.get(_key(plugin)) is False
        and _applied_by_magpie(plugin, sources.get(_key(plugin)), records_by_checkout or {})
    )
    # Restored only where it was hidden: the `restored` record must land in the
    # stamp that holds the `disable`, which a linked worktree cannot write.
    restore = [p for p in restorable if _worktree_id(sources[_key(p)].parent.parent) == worktree]
    restore_in_main = [p for p in restorable if p not in restore]
    for plugin in user_enabled(user_settings, plugins):
        if plugin in on_floor or _key(plugin) in project_entries:
            continue
        entry = recorded.get(plugin, {})
        choice = entry.get("choice")
        if choice == "keep":
            continue
        if choice == "disable":
            worktrees = entry.get("worktrees")
            if not (isinstance(worktrees, list) and worktree in worktrees):
                apply.append(plugin)
            continue
        ask.append(plugin)
    return {"ask": ask, "apply": apply, "restore": restore, "restore_in_main": restore_in_main}


def _project_entries(root: Path) -> tuple[dict[str, object] | None, Path | None]:
    """Every project-scope `enabledPlugins` entry, highest precedence first wins.

    `(None, <path>)` names the first settings file that cannot be read.
    """
    merged, _, unreadable = _project_entries_with_sources(root)
    return merged, unreadable


def _project_entries_with_sources(
    root: Path,
) -> tuple[dict[str, object] | None, dict[str, Path], Path | None]:
    """`_project_entries`, plus the settings file each effective entry is read from."""
    merged: dict[str, object] = {}
    sources: dict[str, Path] = {}
    for path in reversed(project_settings(root)):
        block = _enabled_plugins(path)
        if block is None:
            return None, {}, path
        merged.update(block)
        sources.update(dict.fromkeys(block, path))
    return merged, sources, None


def _is_main_checkout(root: Path) -> bool:
    """Whether `root` is a main checkout, whose settings its linked worktrees also load."""
    return (root / ".git").is_dir()


def candidates(
    root: Path,
    env: Mapping[str, str] | None = None,
    user_settings: Mapping[str, object] | None = None,
) -> dict[str, Any]:
    """The `candidates` answer for the worktree `root`.

    `user_settings` is an `enabledPlugins` block the caller read itself
    (`--user-settings`), used instead of reading the user-scope file.
    `{"applicable": false}` when the project has no marketplace floor, or
    with `reason: user-settings-unreadable` / `project-settings-unreadable`
    and the file's `path` when one cannot be read — unknown is never
    reported as nothing enabled.  `main_checkout` says whether a hide here
    also covers this checkout's linked worktrees.
    """
    try:
        floor = _floor(root)
    except LockUnreadable:
        return {"applicable": False, "reason": "lock-unreadable", "path": str(root / LOCK_NAME)}
    if floor is None:
        return {"applicable": False, "reason": "not-adopted"}
    project, sources, unreadable = _project_entries_with_sources(root)
    if project is None:
        return {"applicable": False, "reason": "project-settings-unreadable", "path": str(unreadable)}
    user: Mapping[str, object] | None = user_settings
    if user is None:
        path = user_settings_path(env)
        user = _user_enabled_plugins(path)
        if user is None:
            return {
                "applicable": False,
                "reason": "user-settings-unreadable",
                "path": str(path) if path is not None else None,
            }
    split = classify(
        user_settings=user,
        floor=floor,
        recorded=decisions(root),
        project_entries=project,
        worktree=_worktree_id(root),
        plugins=family_plugins(),
        entry_sources=sources,
        records_by_checkout={
            _worktree_id(path.parent.parent): _own_layer_entries(root, path.parent.parent)
            for path in set(sources.values())
            if path.name == LOCAL_SETTINGS_NAME
        },
    )
    return {
        "applicable": True,
        "main_checkout": _is_main_checkout(root),
        **split,
        "settings_entries": {
            plugin: _key(plugin) for plugin in [*split["ask"], *split["apply"], *split["restore"]]
        },
        # The file each `restore` entry is removed from: this checkout's own.
        "restore_files": {plugin: str(sources[_key(plugin)]) for plugin in split["restore"]},
        # A hide in the main checkout: restored by running the reconcile step there.
        "restore_in_main_files": {plugin: str(sources[_key(plugin)]) for plugin in split["restore_in_main"]},
    }


def hint_due(
    root: Path,
    family: str | None,
    harness: str | None,
    env: Mapping[str, str] | None = None,
) -> str | None:
    """The plugin to hint about when a skill of `family` runs here, else `None`.

    Due once, under Claude Code only (the settings it names are Claude
    Code's): the family is enabled at user scope, the project's marketplace
    floor lacks it, no project settings file names it, and nothing — not
    even an earlier hint — is recorded for it.  Silent when the user-scope
    settings cannot be read, as inside a sandbox that denies them.
    """
    if harness != HARNESS or family is None or family in ALWAYS_ADOPTED:
        return None
    plugin = f"magpie-{family}"
    if plugin not in family_plugins():
        return None
    floor = adopted_floor(root)
    if floor is None or plugin in floor or plugin in decisions(root):
        return None
    user = _user_enabled_plugins(user_settings_path(env))
    if not user or plugin not in user_enabled(user, [plugin]):
        return None
    project, _ = _project_entries(root)
    if project is None or _key(plugin) in project:
        return None
    return plugin


def record(root: Path, plugin: str, choice: str, today: date | None = None) -> dict[str, object]:
    """Merge one answer into `local_families.<plugin>`; every other key is kept.

    Written to this checkout's own layer (`layers.stamp_dir`); the main
    checkout's is inherited, never written.  `disable` adds this worktree
    to the entry's `worktrees`; `restored`, recorded once a `restore`
    removal is copied, replaces it here.  `hinted` never replaces a
    decided answer.  A stamp that exists but cannot be parsed is left
    alone: `ValueError`, nothing written.
    """
    if choice not in CHOICES:
        raise ValueError(f"unknown choice {choice!r}; expected one of {CHOICES}")
    if plugin not in family_plugins():
        raise ValueError(f"not a Magpie family plugin: {plugin!r}")
    previous = decisions(root).get(plugin, {})
    if choice == "hinted" and previous.get("choice") in DECIDED:
        return dict(previous)
    entry: dict[str, object] = {"choice": choice, "at": (today or date.today()).isoformat()}
    if choice == "disable":
        worktrees = previous.get("worktrees") if previous.get("choice") == "disable" else None
        listed = [w for w in worktrees if isinstance(w, str)] if isinstance(worktrees, list) else []
        entry["worktrees"] = sorted({*listed, _worktree_id(root)})
    directory = stamp_dir(root)
    stamp = _load_stamp(directory)
    raw = stamp.get(BLOCK)
    block: dict[str, object] = dict(raw) if isinstance(raw, dict) else {}
    current = block.get(plugin)
    if choice == "hinted" and isinstance(current, dict) and current.get("choice") in DECIDED:
        # Decided since the check above (another session): never overwrite it with a hint.
        return dict(current)
    block[plugin] = entry
    stamp[BLOCK] = block
    write_stamp(directory, stamp)
    return entry


def _supplied_settings(source: str) -> dict[str, object]:
    """The `enabledPlugins` block the caller read (`-` for stdin, the documented way).

    The input is `{"enabledPlugins": {...}}`.  Anything else, a bare block
    included, is refused rather than read as nothing enabled.
    """
    if source == "-":
        text = sys.stdin.read()
    else:
        try:
            text = _read_file(Path(source)).decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError("--user-settings is not UTF-8") from exc
    try:
        loaded = json.loads(text)
    except ValueError as exc:
        raise ValueError("--user-settings is not JSON") from exc
    block = loaded.get("enabledPlugins") if isinstance(loaded, dict) else None
    if not isinstance(block, dict):
        raise ValueError('--user-settings must be {"enabledPlugins": {...}}')
    return block


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="setup_preflight.local_families", description=__doc__.splitlines()[0]
    )
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("candidates", "record"):
        cmd = sub.add_parser(name)
        cmd.add_argument("--project-root", type=Path, default=Path.cwd())
        if name == "candidates":
            cmd.add_argument(
                "--user-settings",
                help="the user-scope settings file's content, read by the caller ('-' for stdin)",
            )
        else:
            cmd.add_argument("--plugin", required=True)
            cmd.add_argument("--choice", required=True, choices=CHOICES)
    args = parser.parse_args(argv)
    try:
        if args.command == "candidates":
            supplied = _supplied_settings(args.user_settings) if args.user_settings else None
            answer = candidates(args.project_root, user_settings=supplied)
        else:
            answer = record(args.project_root, args.plugin, args.choice)
    except (ValueError, OSError) as exc:
        print(f"local_families: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(answer, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
