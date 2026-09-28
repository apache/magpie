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
The ``procedure`` backend: fixed read-modify-write sequences on the tracker.

Some tracker updates cannot be one ``gh`` call, because the write depends on
what a read returned: appending to the status rollup means finding the rollup
comment first, and replacing one ``### Field`` of an issue body means reading
the body. Doing that in the agent would pull the rollup or the body into its
context, which is what ``tools/github-rollup`` and ``tools/github-body-field``
exist to avoid. Doing it through those tools does not work under the secure
setup, because their ``gh`` runs from a ``uv run`` subprocess inside the sandbox.

So the sequences live here, as reviewed code, and every ``gh`` call they make
goes through :class:`Runner`, which checks it before it runs:

- the argv starts with ``gh`` and is executed without a shell;
- it is one of ``gh issue view|comment|edit <number> --repo <tracker>`` or
  ``gh api repos/<tracker>/…`` — the tracker is the policy-pinned one, and a
  ``gh api`` path outside ``repos/<tracker>/`` is refused (the single exception
  is the fixed ``gh api user --jq .login`` read that names the entry author);
- a read is a read: a call shaped like a write is refused on the read path, and
  an operation declared read-only cannot reach the write path at all;
- in a dry run, reads execute (the plan depends on them) and writes are printed
  instead of run, with any body reported by size, never by content.

The parsing and composing is done by modules vendored byte-for-byte from the two
tools (``rollup_format``, ``body_field_format``), so the shapes stay identical;
a test fails if a vendored copy drifts from its source.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TextIO

from .body_field_format import FieldNotFoundError, extract_field, replace_field
from .rollup_format import (
    build_entry,
    build_new_rollup_body,
    is_rollup_body,
    iter_entries,
    left_trim_lines,
    rebuild_with_appended_entry,
    replace_latest_entry,
)


class ProcedureRefused(RuntimeError):
    """The procedure declined to write: the tracker state does not allow it."""


class RunnerRefused(RuntimeError):
    """A procedure tried to run a ``gh`` call the runner does not permit."""


class CommandFailed(RuntimeError):
    """A ``gh`` call exited non-zero."""

    def __init__(self, argv: list[str], returncode: int, stderr: str) -> None:
        super().__init__(f"{' '.join(argv[:3])} … exited {returncode}")
        self.returncode = returncode
        self.stderr = stderr


#: Executes one argv with optional stdin; returns (returncode, stdout, stderr).
ExecFn = Callable[[list[str], bytes | None], tuple[int, bytes, bytes]]


def subprocess_exec(argv: list[str], stdin: bytes | None) -> tuple[int, bytes, bytes]:
    """The real executor: no shell, argv passed verbatim, output captured."""
    completed = subprocess.run(argv, input=stdin, capture_output=True, check=False)
    return completed.returncode, completed.stdout, completed.stderr


#: The one ``gh api`` call outside ``repos/<tracker>/`` a procedure may make:
#: the authenticated login, which a new rollup entry is attributed to.
_VIEWER_ARGV = ("gh", "api", "user", "--jq", ".login")

_ISSUE_SUBCOMMANDS = {"view": False, "comment": True, "edit": True}
_NUMBER = re.compile(r"^[0-9]{1,10}$")
_API_FIELD_FLAGS = {"-f", "-F", "--field", "--raw-field", "--input"}
_API_METHODS = {"GET", "PATCH", "DELETE"}
_API_FIELD = re.compile(r"^[a-z_]{1,40}=")
_FORBIDDEN_FLAGS = {"-R", "--repo", "--hostname"}


class Runner:
    """
    The only way a procedure reaches ``gh``.

    ``allow_writes`` comes from the operation's ``writes`` flag, so a read
    operation — reachable through ``vetted-op-read`` — cannot write even if its
    procedure tried to.
    """

    def __init__(
        self,
        tracker: str,
        *,
        allow_writes: bool,
        dry_run: bool = False,
        exec_fn: ExecFn | None = None,
        out: TextIO | None = None,
    ) -> None:
        self.tracker = tracker
        self.allow_writes = allow_writes
        self.dry_run = dry_run
        self._exec = exec_fn or subprocess_exec
        self._out = out
        #: Every call that passed the checks, in order, as (kind, argv).
        self.calls: list[tuple[str, list[str]]] = []

    # ---- checks ---------------------------------------------------------

    def _is_write(self, argv: list[str]) -> bool:
        """Classify a (checked) argv. Only called after :meth:`_check`."""
        if argv[1] == "issue":
            return _ISSUE_SUBCOMMANDS[argv[2]]
        if "-X" in argv and argv[argv.index("-X") + 1] != "GET":
            return True
        return any(a in _API_FIELD_FLAGS for a in argv)

    def _check(self, argv: list[str]) -> None:
        if not isinstance(argv, list) or not all(isinstance(a, str) for a in argv):
            raise RunnerRefused("argv must be a list of strings")
        if len(argv) < 3 or argv[0] != "gh":
            raise RunnerRefused(f"only gh may run, got {argv[:1]!r}")
        if any(a in _FORBIDDEN_FLAGS for a in argv[2:] if argv[1] == "api"):
            raise RunnerRefused("a gh api call may not name a repo or host of its own")
        if any("\x00" in a for a in argv):
            raise RunnerRefused("argv may not contain NUL")

        if argv[1] == "issue":
            if argv[2] not in _ISSUE_SUBCOMMANDS:
                raise RunnerRefused(f"gh issue {argv[2]!r} is not a procedure call")
            if len(argv) < 4 or not _NUMBER.match(argv[3]):
                raise RunnerRefused("gh issue call must name an issue number")
            repo_flags = [i for i, a in enumerate(argv) if a in ("--repo", "-R")]
            if len(repo_flags) != 1 or repo_flags[0] + 1 >= len(argv):
                raise RunnerRefused("gh issue call must name --repo exactly once")
            if argv[repo_flags[0] + 1] != self.tracker:
                raise RunnerRefused(f"gh issue call targets {argv[repo_flags[0] + 1]!r}, not the tracker")
            i = 4
            while i < len(argv):
                a = argv[i]
                if a not in {"--repo", "--json", "--jq", "--body-file"} or i + 1 >= len(argv):
                    raise RunnerRefused(f"unexpected gh issue argument {a!r}")
                # A path would make gh read a local file; the body comes on stdin.
                if a == "--body-file" and argv[i + 1] != "-":
                    raise RunnerRefused("gh issue --body-file must be '-' (stdin)")
                i += 2
            return

        if argv[1] == "api":
            if tuple(argv) == _VIEWER_ARGV:
                return
            path = argv[2]
            if not path.startswith(f"repos/{self.tracker}/"):
                raise RunnerRefused(f"gh api path {path!r} is outside repos/{self.tracker}/")
            if ".." in path or "//" in path[len("repos/") :]:
                raise RunnerRefused(f"gh api path {path!r} may not traverse")
            # Exactly one path: nothing after it may be another positional.
            i = 3
            while i < len(argv):
                a = argv[i]
                if a in {"-X", "--jq", "-f", "-F"}:
                    if i + 1 >= len(argv):
                        raise RunnerRefused(f"gh api flag {a} has no value")
                    value = argv[i + 1]
                    if a == "-X" and value not in _API_METHODS:
                        raise RunnerRefused(f"gh api method {value!r} is not permitted")
                    # `-F key=@path` makes gh read a local file. The only file a
                    # procedure may hand gh is its own stdin.
                    if a in {"-f", "-F"} and (
                        not _API_FIELD.match(value) or ("@" in value and value != "body=@-")
                    ):
                        raise RunnerRefused(f"gh api field {value!r} is not permitted")
                    i += 2
                    continue
                if a == "--paginate":
                    i += 1
                    continue
                raise RunnerRefused(f"unexpected gh api argument {a!r}")
            return

        raise RunnerRefused(f"gh {argv[1]!r} is not a procedure call")

    def _render(self, argv: list[str], stdin: bytes | None) -> str:
        rendered = " ".join(argv)
        if stdin is not None:
            rendered += f"  (stdin: {len(stdin)} bytes)"
        return rendered

    def _run(self, argv: list[str], stdin: bytes | None) -> str:
        code, stdout, stderr = self._exec(argv, stdin)
        if code != 0:
            raise CommandFailed(argv, code, stderr.decode("utf-8", "replace"))
        return stdout.decode("utf-8")

    # ---- the two doors --------------------------------------------------

    def read(self, argv: list[str]) -> str:
        self._check(argv)
        if self._is_write(argv):
            raise RunnerRefused(f"{' '.join(argv[:3])} writes; it cannot run as a read")
        self.calls.append(("read", list(argv)))
        return self._run(argv, None)

    def write(self, argv: list[str], stdin: str | None = None) -> None:
        self._check(argv)
        if not self.allow_writes:
            raise RunnerRefused("this operation is read-only; it may not write")
        if not self._is_write(argv):
            raise RunnerRefused(f"{' '.join(argv[:3])} is not a write")
        data = stdin.encode("utf-8") if stdin is not None else None
        self.calls.append(("write", list(argv)))
        if self.dry_run:
            print(f"dry-run: would run: {self._render(argv, data)}", file=self._out or sys.stdout)
            return
        self._run(argv, data)


@dataclass(frozen=True)
class Plan:
    """What a ``procedure`` builder returns: a fixed procedure bound to its parameters."""

    op: str
    tracker: str
    run: Callable[..., int]
    params: dict[str, str] = field(default_factory=dict)

    def execute(self, runner: Runner, body: bytes | None) -> int:
        kwargs: dict[str, object] = dict(self.params)
        if body is not None:
            try:
                kwargs["text"] = body.decode("utf-8")
            except UnicodeDecodeError:
                raise ProcedureRefused("body file is not valid UTF-8") from None
        return self.run(runner, **kwargs)

    def describe(self) -> str:
        shown = " ".join(f"{k}={v!r}" for k, v in self.params.items())
        return f"procedure {self.op} on {self.tracker} {shown}".rstrip()


def _say(message: str) -> None:
    sys.stderr.write(f"{message}\n")


# ---- rollup ---------------------------------------------------------------


def _list_comments(r: Runner, number: str) -> list[dict[str, object]]:
    out = r.read(["gh", "issue", "view", number, "--repo", r.tracker, "--json", "comments"])
    comments = json.loads(out).get("comments", [])
    return [c for c in comments if isinstance(c, dict)]


def _find_rollup(comments: list[dict[str, object]]) -> dict[str, object] | None:
    for c in comments:
        if is_rollup_body(str(c.get("body") or "")):
            return c
    return None


_NODE_ID = re.compile(r"^[A-Za-z0-9_-]{1,120}$")


def _rest_id(r: Runner, comment: dict[str, object]) -> str:
    """REST id from the comment's ``#issuecomment-<id>`` URL, else by node id."""
    match = re.search(r"#issuecomment-(\d+)$", str(comment.get("url") or ""))
    if match:
        return match.group(1)
    node_id = str(comment.get("id") or "")
    if not _NODE_ID.match(node_id):
        raise ProcedureRefused(f"rollup comment has neither a URL id nor a usable node id: {node_id!r}")
    out = r.read(
        [
            "gh",
            "api",
            f"repos/{r.tracker}/issues/comments?per_page=100",
            "--paginate",
            "--jq",
            f'.[] | select(.node_id == "{node_id}") | .id',
        ]
    )
    ids = out.strip().splitlines()
    if not ids or not _NUMBER.match(ids[0]):
        raise ProcedureRefused(f"could not map node id {node_id!r} to a REST id")
    return ids[0]


def _patch_comment(r: Runner, comment_id: str, body: str) -> None:
    r.write(
        ["gh", "api", f"repos/{r.tracker}/issues/comments/{comment_id}", "-X", "PATCH", "-F", "body=@-"],
        stdin=body,
    )


def _write_entry(r: Runner, number: str, entry: str) -> str:
    """Append ``entry`` to the rollup, creating it when absent. Returns a summary."""
    rollup = _find_rollup(_list_comments(r, number))
    if rollup is None:
        r.write(
            ["gh", "issue", "comment", number, "--repo", r.tracker, "--body-file", "-"],
            stdin=build_new_rollup_body(entry, r.tracker.split("/")[-1]),
        )
        return f"created rollup on {r.tracker}#{number}"
    _patch_comment(r, _rest_id(r, rollup), rebuild_with_appended_entry(str(rollup.get("body") or ""), entry))
    return f"appended to rollup on {r.tracker}#{number}"


def _today() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d")


def rollup_append(r: Runner, *, number: str, action: str, text: str, date: str | None = None) -> int:
    login = r.read(list(_VIEWER_ARGV)).strip()
    if not login:
        raise ProcedureRefused("could not determine the authenticated gh login")
    day = date or _today()
    entry = build_entry(date=day, user=login, action=action, body=text)
    summary = _write_entry(r, number, entry)
    _say(f"{'dry-run: ' if r.dry_run else ''}{summary} ({action!r}, date={day})")
    return 0


def rollup_amend_latest(r: Runner, *, number: str, action: str, text: str) -> int:
    rollup = _find_rollup(_list_comments(r, number))
    if rollup is None:
        raise ProcedureRefused(f"no rollup on {r.tracker}#{number}")
    existing = str(rollup.get("body") or "")
    entries = iter_entries(existing)
    if not entries:
        raise ProcedureRefused(f"rollup on {r.tracker}#{number} has no entries")
    latest = entries[-1]
    if latest.action != action:
        raise ProcedureRefused(f"latest entry is {latest.action!r}, not {action!r}; refusing to amend")
    entry = build_entry(date=latest.date, user=latest.user, action=latest.action, body=text)
    _patch_comment(r, _rest_id(r, rollup), replace_latest_entry(existing, entry))
    _say(f"{'dry-run: ' if r.dry_run else ''}amended latest entry on {r.tracker}#{number} ({action!r})")
    return 0


def rollup_fold(r: Runner, *, number: str, comment_id: str, action: str) -> int:
    legacy = json.loads(r.read(["gh", "api", f"repos/{r.tracker}/issues/comments/{comment_id}"]))
    legacy_body = str(legacy.get("body") or "")
    if is_rollup_body(legacy_body):
        raise ProcedureRefused(f"comment {comment_id} is the rollup itself; refusing to fold")
    # A comment id is repo-wide, so pin it to the issue being folded into:
    # folding (and then deleting) a comment from a different tracker issue is
    # never the intent.
    if not str(legacy.get("issue_url") or "").endswith(f"/issues/{number}"):
        raise ProcedureRefused(f"comment {comment_id} does not belong to {r.tracker}#{number}")
    login = str((legacy.get("user") or {}).get("login") or "")
    date = str(legacy.get("created_at") or "")[:10]
    if not login or not date:
        raise ProcedureRefused(f"comment {comment_id} has no author or creation date")
    entry = build_entry(date=date, user=login, action=action, body=left_trim_lines(legacy_body))
    summary = _write_entry(r, number, entry)
    # Only reached when the append succeeded: a failed write raises first.
    r.write(["gh", "api", f"repos/{r.tracker}/issues/comments/{comment_id}", "-X", "DELETE"])
    prefix = "dry-run: " if r.dry_run else ""
    _say(f"{prefix}{summary} ({date} · @{login} · {action!r}); deleted legacy comment {comment_id}")
    return 0


# ---- body fields ------------------------------------------------------------


def _get_body(r: Runner, number: str) -> str:
    body = r.read(["gh", "issue", "view", number, "--repo", r.tracker, "--json", "body", "--jq", ".body"])
    # `--jq .body` appends one newline; strip exactly one for a byte-exact round trip.
    return body[:-1] if body.endswith("\n") else body


def body_field_get(r: Runner, *, number: str, field: str) -> int:
    try:
        value = extract_field(_get_body(r, number), field)
    except FieldNotFoundError as exc:
        raise ProcedureRefused(str(exc)) from None
    sys.stdout.write(value if value.endswith("\n") else f"{value}\n")
    return 0


def body_field_set(r: Runner, *, number: str, field: str, text: str) -> int:
    body = _get_body(r, number)
    try:
        old_value = extract_field(body, field)
        new_body = replace_field(body, field, text)
    except FieldNotFoundError as exc:
        raise ProcedureRefused(str(exc)) from None
    if new_body == body:
        _say(f"unchanged: {field!r} already matches the new value")
        return 0
    _say(f"field={field!r} old_len={len(old_value)} new_len={len(text)}")
    r.write(["gh", "issue", "edit", number, "--repo", r.tracker, "--body-file", "-"], stdin=new_body)
    if not r.dry_run:
        _say(f"updated {field!r} on {r.tracker}#{number}")
    return 0
