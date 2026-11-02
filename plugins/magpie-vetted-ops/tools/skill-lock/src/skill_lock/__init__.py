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

"""Per-skill write lock for the batch skills.

A batch skill's read and classify phase has no side effects and may run
concurrently with anything. Its **write phase** (posting triage comments,
stale nudges, labels, closes) must not: two sweeps of the same skill over
the same repository, overlapping, post the same comment or label twice, and
a doubled bot comment is exactly what makes contributors distrust the bot.

This tool is the lock the write phase takes. It is deliberately small:

* **Scope** is ``<skill>@<repo>``. The same skill on two repositories never
  contends; two different skills on one repository never contend either,
  because they post different things.
* **Location** is the personal config layer's run directory,
  ``<personal>/run/locks/<scope>.lock/`` (``.apache-magpie-local/run/`` in
  an adopted project, the git-directory home otherwise; see ``layers.py``).
  It is never inside the working tree of an adopted project, so it is never
  committed.
* **Mechanism** is an atomic ``mkdir`` holding one ``owner.json``. No
  ``flock`` (absent on macOS), nothing in ``.git/``.
* **Liveness is a lease, not a pid.** The process that runs ``acquire`` is
  an ``uv run`` that exits at once; the skill run that owns the lock is an
  agent session with no stable pid. So the owner records an expiry
  (``--ttl``, default two hours) and the write phase is expected to finish
  well inside it. An expired lock is stale and is taken over; ``renew``
  extends a long run. When a pid is supplied (``--owner-pid``) a dead pid on
  the same host also counts as stale, which is how a shell-script caller
  gets the sharper check.
* **Outcome is machine-readable.** Every command prints one JSON object.
  ``acquire`` exits 0 when acquired, 3 when another run holds the lock
  (``status: already_running``, with the holder), 2 on an error. The skill
  prose treats 3 as "stop, this is not a failure of the sweep".
"""

from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import socket
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

from .layers import personal_dir

DEFAULT_TTL_SECONDS = 2 * 60 * 60
LOCKS_SUBDIR = Path("run") / "locks"
OWNER_FILE = "owner.json"

EXIT_OK = 0
EXIT_ERROR = 2
EXIT_ALREADY_RUNNING = 3

_SCOPE_SAFE = re.compile(r"[^A-Za-z0-9._@-]+")


def utcnow() -> datetime:
    return datetime.now(UTC)


def _iso(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_iso(text: object) -> datetime | None:
    if not isinstance(text, str):
        return None
    try:
        return datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    except ValueError:
        return None


def scope_name(skill: str, repo: str) -> str:
    """``<skill>@<repo>`` made safe for one path component (``/`` becomes ``__``)."""
    if not skill or not repo:
        raise ValueError("skill and repo are both required")
    raw = f"{skill}@{repo.replace('/', '__')}"
    return _SCOPE_SAFE.sub("-", raw)


def locks_dir(root: Path) -> Path:
    return personal_dir(root) / LOCKS_SUBDIR


def lock_path(root: Path, skill: str, repo: str) -> Path:
    return locks_dir(root) / f"{scope_name(skill, repo)}.lock"


def hostname() -> str:
    try:
        return socket.gethostname() or "unknown-host"
    except OSError:
        return "unknown-host"


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def read_owner(lock: Path) -> dict | None:
    """The owner record, or None when the lock dir has none (racing starter)."""
    try:
        return json.loads((lock / OWNER_FILE).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def staleness(owner: dict | None, now: datetime) -> str | None:
    """Why ``owner`` is stale, or None when it must be respected.

    A lock with no readable owner is never stale: another starter may be
    between its ``mkdir`` and its write.
    """
    if owner is None:
        return None
    expires = _parse_iso(owner.get("expires"))
    if expires is not None and expires <= now:
        return f"lease expired at {_iso(expires)}"
    pid = owner.get("pid")
    host = owner.get("host")
    if isinstance(pid, int) and pid > 0 and host == hostname() and not _pid_alive(pid):
        return f"owner pid {pid} is gone on this host"
    return None


def _write_owner(lock: Path, owner: dict) -> None:
    tmp = lock / f"{OWNER_FILE}.tmp"
    tmp.write_text(json.dumps(owner, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, lock / OWNER_FILE)


def _remove_lock(lock: Path) -> None:
    for child in lock.iterdir() if lock.is_dir() else []:
        child.unlink(missing_ok=True)
    lock.rmdir()


def _take_over(lock: Path, seen: dict | None) -> bool:
    """Move a stale lock out of the way; True when this caller removed it.

    Renaming to a unique tombstone is atomic, so when two runs find the same
    stale lock only one rename succeeds. The winner deletes the tombstone
    only if it still holds the owner it judged stale; if a faster run had
    already replaced the lock, the live lock is put back.
    """
    tomb = lock.with_name(f"{lock.name}.stale-{secrets.token_hex(8)}")
    try:
        os.rename(lock, tomb)
    except OSError:
        return False
    if read_owner(tomb) == seen:
        _remove_lock(tomb)
        return True
    if not lock.exists():
        try:
            os.rename(tomb, lock)
            return False
        except OSError:
            pass
    _remove_lock(tomb)
    return False


def acquire(
    root: Path,
    skill: str,
    repo: str,
    *,
    ttl: int = DEFAULT_TTL_SECONDS,
    owner_pid: int | None = None,
    note: str = "",
    now: datetime | None = None,
) -> dict:
    """Take the lock for ``skill`` on ``repo``.

    Returns a dict with ``status`` of ``acquired`` (plus ``token``) or
    ``already_running`` (plus ``holder``). A stale holder is taken over once;
    the result then carries ``took_over_stale``.
    """
    now = now or utcnow()
    lock = lock_path(root, skill, repo)
    lock.parent.mkdir(parents=True, exist_ok=True)
    took_over: str | None = None
    for _attempt in range(2):
        try:
            lock.mkdir()
        except FileExistsError:
            if not lock.is_dir():
                return {
                    "status": "error",
                    "skill": skill,
                    "repo": repo,
                    "lock": str(lock),
                    "error": "lock path exists but is not a directory; remove it by hand",
                }
            owner = read_owner(lock)
            reason = staleness(owner, now)
            if reason is not None and took_over is None:
                took_over = reason
                if _take_over(lock, owner):
                    continue
                return {
                    "status": "already_running",
                    "skill": skill,
                    "repo": repo,
                    "lock": str(lock),
                    "holder": read_owner(lock),
                    "hint": "another run took over the stale lock first; stop here (this is not a failure of the sweep)",
                }
            return {
                "status": "already_running",
                "skill": skill,
                "repo": repo,
                "lock": str(lock),
                "holder": owner,
                "hint": (
                    "another run of this skill holds the write lock for this repository; "
                    "stop here (this is not a failure of the sweep). If that run is known "
                    f"to be dead, release it with: skill-lock release {skill} --repo {repo} --force"
                ),
            }
        token = secrets.token_hex(8)
        owner = {
            "skill": skill,
            "repo": repo,
            "token": token,
            "pid": owner_pid,
            "host": hostname(),
            "started": _iso(now),
            "expires": _iso(now + timedelta(seconds=ttl)),
            "note": note,
        }
        _write_owner(lock, owner)
        result = {"status": "acquired", "skill": skill, "repo": repo, "lock": str(lock), "token": token}
        result["expires"] = owner["expires"]
        if took_over:
            result["took_over_stale"] = took_over
        return result
    return {
        "status": "error",
        "skill": skill,
        "repo": repo,
        "lock": str(lock),
        "error": "could not acquire the lock after removing a stale one",
    }


def release(root: Path, skill: str, repo: str, *, token: str | None = None, force: bool = False) -> dict:
    """Release the lock. With a token, only the matching holder is released."""
    lock = lock_path(root, skill, repo)
    if not lock.is_dir():
        return {"status": "released", "skill": skill, "repo": repo, "lock": str(lock), "was_held": False}
    owner = read_owner(lock)
    if token is not None and not force and (owner is None or owner.get("token") != token):
        return {
            "status": "error",
            "skill": skill,
            "repo": repo,
            "lock": str(lock),
            "error": "token does not match the lock holder; pass --force to release it anyway",
            "holder": owner,
        }
    _remove_lock(lock)
    return {
        "status": "released",
        "skill": skill,
        "repo": repo,
        "lock": str(lock),
        "was_held": True,
        "holder": owner,
    }


def renew(
    root: Path,
    skill: str,
    repo: str,
    *,
    ttl: int = DEFAULT_TTL_SECONDS,
    token: str | None = None,
    now: datetime | None = None,
) -> dict:
    """Extend the lease of a held lock. With a token, only the matching holder."""
    now = now or utcnow()
    lock = lock_path(root, skill, repo)
    owner = read_owner(lock) if lock.is_dir() else None
    if owner is None:
        return {
            "status": "error",
            "skill": skill,
            "repo": repo,
            "lock": str(lock),
            "error": "lock is not held",
        }
    if token is not None and owner.get("token") != token:
        return {
            "status": "error",
            "skill": skill,
            "repo": repo,
            "lock": str(lock),
            "error": "token does not match the lock holder; this run's lease was taken over",
            "holder": owner,
        }
    owner["expires"] = _iso(now + timedelta(seconds=ttl))
    _write_owner(lock, owner)
    return {"status": "renewed", "skill": skill, "repo": repo, "lock": str(lock), "expires": owner["expires"]}


def status(root: Path, skill: str, repo: str, *, now: datetime | None = None) -> dict:
    now = now or utcnow()
    lock = lock_path(root, skill, repo)
    if not lock.is_dir():
        return {"status": "free", "skill": skill, "repo": repo, "lock": str(lock)}
    owner = read_owner(lock)
    reason = staleness(owner, now)
    return {
        "status": "stale" if reason else "held",
        "skill": skill,
        "repo": repo,
        "lock": str(lock),
        "holder": owner,
        **({"stale_reason": reason} if reason else {}),
    }


def list_locks(root: Path, *, now: datetime | None = None) -> dict:
    now = now or utcnow()
    directory = locks_dir(root)
    entries = []
    if directory.is_dir():
        for lock in sorted(directory.glob("*.lock")):
            owner = read_owner(lock)
            reason = staleness(owner, now)
            entries.append(
                {
                    "lock": str(lock),
                    "status": "stale" if reason else "held",
                    "holder": owner,
                    **({"stale_reason": reason} if reason else {}),
                }
            )
    return {"status": "ok", "locks_dir": str(directory), "locks": entries}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _find_root(start: Path) -> Path:
    """The project root: the nearest ancestor with a .git, .svn or Magpie lock file."""
    for candidate in [start.resolve(), *start.resolve().parents]:
        if (
            (candidate / ".git").exists()
            or (candidate / ".svn").is_dir()
            or (candidate / ".apache-magpie.lock").is_file()
        ):
            return candidate
    return start.resolve()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="skill-lock",
        description="Per-skill write lock for batch skills. Prints one JSON object per call.",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help="Project root whose personal config layer holds the locks (default: found from the cwd).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    def add_scope(p: argparse.ArgumentParser) -> None:
        p.add_argument("skill", help="Skill name, e.g. issue-triage.")
        p.add_argument("--repo", required=True, help="Repository the writes target, e.g. apache/example.")

    p = sub.add_parser("acquire", help="Take the write lock; exit 0 acquired, 3 already running, 2 error.")
    add_scope(p)
    p.add_argument(
        "--ttl", type=int, default=DEFAULT_TTL_SECONDS, help=f"Lease seconds (default {DEFAULT_TTL_SECONDS})."
    )
    p.add_argument("--owner-pid", type=int, default=None, help="Pid whose death also makes the lock stale.")
    p.add_argument("--note", default="", help="Free text stored with the owner record.")

    p = sub.add_parser("release", help="Release the write lock.")
    add_scope(p)
    p.add_argument("--token", default=None, help="Token printed by acquire; refuses a non-matching holder.")
    p.add_argument("--force", action="store_true", help="Release regardless of holder.")

    p = sub.add_parser("renew", help="Extend the lease of a held lock.")
    add_scope(p)
    p.add_argument("--ttl", type=int, default=DEFAULT_TTL_SECONDS)
    p.add_argument("--token", default=None, help="Token printed by acquire; refuses a non-matching holder.")

    p = sub.add_parser("status", help="Report free / held / stale.")
    add_scope(p)

    sub.add_parser("list", help="List every lock in this project's run directory.")

    args = parser.parse_args(argv)
    root = args.root if args.root is not None else _find_root(Path.cwd())

    try:
        if args.command == "acquire":
            result = acquire(
                root, args.skill, args.repo, ttl=args.ttl, owner_pid=args.owner_pid, note=args.note
            )
        elif args.command == "release":
            result = release(root, args.skill, args.repo, token=args.token, force=args.force)
        elif args.command == "renew":
            result = renew(root, args.skill, args.repo, ttl=args.ttl, token=args.token)
        elif args.command == "status":
            result = status(root, args.skill, args.repo)
        else:
            result = list_locks(root)
    except (OSError, ValueError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}))
        return EXIT_ERROR

    print(json.dumps(result, sort_keys=True))
    if result.get("status") == "already_running":
        return EXIT_ALREADY_RUNNING
    if result.get("status") == "error":
        return EXIT_ERROR
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
