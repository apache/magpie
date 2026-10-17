# SPDX-License-Identifier: Apache-2.0
# https://www.apache.org/licenses/LICENSE-2.0
"""``magpie-local-tracker`` — the security-tracker contract over local files.

The subcommands, arguments, JSON outputs and exit codes are the ones in
``tools/security-tracker/contract.md``; ``detect`` and ``init`` are this
backend's own setup commands.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import getpass
import json
import os
import subprocess
import sys
from pathlib import Path

from . import detect as detect_mod
from .descriptor import DESCRIPTOR_NAME, Descriptor, load, save
from .store import Tracker, TrackerError
from .vcs import VcsError, VcsRefused
from .vcs import detect as detect_vcs


def _emit(payload: object) -> None:
    json.dump(payload, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")


def _read_file(path: str) -> str:
    if path == "-":
        return sys.stdin.read()
    try:
        return Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        raise TrackerError(f"cannot read {path}: {exc}", 2) from exc


def _default_user() -> str:
    for args in (["git", "config", "user.name"],):
        try:
            out = subprocess.run(args, capture_output=True, text=True, check=False).stdout.strip()
        except FileNotFoundError:
            out = ""
        if out:
            return out
    return os.environ.get("USER") or getpass.getuser()


def _root(args: argparse.Namespace) -> Path:
    raw = args.root or os.environ.get("MAGPIE_LOCAL_TRACKER_ROOT")
    if not raw:
        raise TrackerError("--root (or MAGPIE_LOCAL_TRACKER_ROOT) is required", 2)
    return Path(raw)


def _tracker(args: argparse.Namespace) -> Tracker:
    root = _root(args)
    try:
        desc = load(root)
    except FileNotFoundError as exc:
        raise TrackerError(str(exc), 3) from exc
    except ValueError as exc:
        raise TrackerError(f"invalid tracker descriptor: {exc}", 5) from exc
    return Tracker(root, desc)


def _github_visibility(remote: str) -> str | None:
    """Visibility of a GitHub remote via `gh`, or None when it cannot be told."""
    if "github.com" not in remote:
        return None
    slug = remote.rstrip("/").removesuffix(".git").split("github.com")[-1].lstrip(":/")
    try:
        proc = subprocess.run(
            ["gh", "repo", "view", slug, "--json", "visibility", "--jq", ".visibility"],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return None
    return proc.stdout.strip().lower() or None if proc.returncode == 0 else None


# ---------------------------------------------------------------- commands


def cmd_detect(args: argparse.Namespace) -> int:
    root = _root(args)
    desc, evidence = detect_mod.detect(root)
    existing = root / DESCRIPTOR_NAME
    if existing.is_file() and not args.force:
        evidence["decisions"].insert(0, f"{existing} already exists; showing what detection would write")  # type: ignore[attr-defined]
    _apply_setup_flags(desc, args)
    out: dict[str, object] = {"descriptor": json.loads(desc.to_json()), "summary": detect_mod.describe(desc)}
    out.update(evidence)
    if args.write:
        if existing.is_file() and not args.force:
            raise TrackerError(f"{existing} exists; pass --force to replace it", 4)
        root.mkdir(parents=True, exist_ok=True)
        out["written"] = str(save(root, desc))
    _emit(out)
    return 0


def _apply_setup_flags(desc: Descriptor, args: argparse.Namespace) -> None:
    if getattr(args, "prefix", None):
        desc.id.prefix = args.prefix
    if getattr(args, "url_template", None):
        desc.url_template = args.url_template
    if getattr(args, "access_restricted", False):
        desc.access_restricted = True
        desc.access_note = args.access_note or (
            f"confirmed access-restricted by {_default_user()} on {_dt.date.today().isoformat()}"
        )


def cmd_init(args: argparse.Namespace) -> int:
    root = _root(args)
    existing = root / DESCRIPTOR_NAME
    if existing.is_file() and not args.force:
        raise TrackerError(f"{existing} exists; pass --force to replace it", 4)
    desc = Descriptor()
    _apply_setup_flags(desc, args)
    root.mkdir(parents=True, exist_ok=True)
    path = save(root, desc)
    _emit({"written": str(path), "summary": detect_mod.describe(desc)})
    return 0


def cmd_view(args: argparse.Namespace) -> int:
    _emit(_tracker(args).view(args.id, with_comments=args.comments))
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    _emit(_tracker(args).list_issues(args.state, args.label, args.search or "", args.limit))
    return 0


def cmd_labels(args: argparse.Namespace) -> int:
    _emit(_tracker(args).labels())
    return 0


def cmd_field_get(args: argparse.Namespace) -> int:
    _emit(_tracker(args).field_get(args.id, args.heading))
    return 0


def _title_arg(args: argparse.Namespace) -> str | None:
    """The title from ``--title`` (argv, never a shell) or ``--title-file``."""
    if args.title is not None and args.title_file:
        raise TrackerError("--title and --title-file are mutually exclusive", 2)
    if args.title is not None:
        return str(args.title)
    return _read_file(args.title_file) if args.title_file else None


def cmd_create(args: argparse.Namespace) -> int:
    tracker = _tracker(args)
    title = _title_arg(args)
    if title is None:
        raise TrackerError("create needs --title or --title-file", 2)
    _emit(tracker.create(title, _read_file(args.body_file), args.label, args.author or ""))
    return 0


def cmd_edit(args: argparse.Namespace) -> int:
    _emit(
        _tracker(args).edit(
            args.id,
            args.add_label,
            args.remove_label,
            args.add_assignee,
            args.remove_assignee,
            args.milestone,
            args.clear_milestone,
            _title_arg(args),
            _read_file(args.body_file) if args.body_file else None,
        )
    )
    return 0


def cmd_field_set(args: argparse.Namespace) -> int:
    _emit(_tracker(args).field_set(args.id, args.heading, _read_file(args.value_file)))
    return 0


def cmd_comment(args: argparse.Namespace) -> int:
    _emit(_tracker(args).comment(args.id, _read_file(args.body_file), args.author or _default_user()))
    return 0


def cmd_close(args: argparse.Namespace) -> int:
    _emit(_tracker(args).set_state(args.id, True, args.reason))
    return 0


def cmd_reopen(args: argparse.Namespace) -> int:
    _emit(_tracker(args).set_state(args.id, False))
    return 0


def _now(args: argparse.Namespace) -> str:
    return args.now or _dt.datetime.now(_dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _user(args: argparse.Namespace) -> str:
    user = args.user or _default_user()
    return user if user.startswith("@") else f"@{user}"


def cmd_rollup_append(args: argparse.Namespace) -> int:
    body = _read_file(args.entry_body_file)
    _emit(_tracker(args).rollup_append(args.id, args.action, body, _user(args), _now(args)))
    return 0


def cmd_rollup_amend_latest(args: argparse.Namespace) -> int:
    _emit(_tracker(args).rollup_amend_latest(args.id, args.action, _read_file(args.entry_body_file)))
    return 0


def cmd_attach(args: argparse.Namespace) -> int:
    if args.file == "-":
        if not args.name:
            raise TrackerError("attaching from stdin needs --name", 2)
        content, name = sys.stdin.buffer.read(), args.name
    else:
        source = Path(args.file)
        if not source.is_file():
            raise TrackerError(f"{source} is not a file", 3)
        content, name = source.read_bytes(), args.name or source.name
    _emit(_tracker(args).attach(args.id, content, name))
    return 0


def cmd_body(args: argparse.Namespace) -> int:
    # Raw markdown, not JSON: it is piped straight into generate-cve-json --stdin.
    sys.stdout.write(_tracker(args).body(args.id))
    return 0


def cmd_pending(args: argparse.Namespace) -> int:
    root = _root(args)
    wc = detect_vcs(root)
    changes = wc.status(root) if root.exists() else []
    unpushed = wc.unpushed()
    _emit(
        {
            "backend": "local-files",
            "vcs": wc.kind,
            "changes": changes,
            "unpushed_commits": unpushed,
            "push_destination": wc.push_destination(),
            "needs_publish": bool(changes) or bool(unpushed),
        }
    )
    return 0


def cmd_publish(args: argparse.Namespace) -> int:
    tracker = _tracker(args)
    tracker.require_writable()
    message = _read_file(args.message_file)
    if not message.strip():
        raise TrackerError("the commit message file is empty", 2)
    result = tracker.wc.publish(tracker.root, message, args.trailer, args.push)
    result["vcs"] = tracker.wc.kind
    _emit(result)
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    root = _root(args)
    checks: list[dict[str, object]] = []
    checks.append({"name": "root exists", "ok": root.is_dir(), "detail": str(root)})
    desc: Descriptor | None = None
    try:
        desc = load(root)
        checks.append({"name": "descriptor", "ok": True, "detail": detect_mod.describe(desc)})
    except (FileNotFoundError, ValueError) as exc:
        checks.append({"name": "descriptor", "ok": False, "detail": str(exc)})
    wc = detect_vcs(root) if root.exists() else None
    checks.append(
        {
            "name": "working copy",
            "ok": bool(wc and wc.kind != "none"),
            "detail": f"{wc.kind} at {wc.top}" if wc else "root missing",
        }
    )
    remotes = wc.remotes() if wc else []
    checks.append({"name": "remotes", "ok": bool(remotes), "detail": remotes})
    for remote in remotes:
        visibility = _github_visibility(remote)
        if visibility:
            checks.append(
                {"name": f"visibility {remote}", "ok": visibility != "public", "detail": visibility}
            )
    checks.append(
        {
            "name": "access restricted (human-confirmed)",
            "ok": bool(desc and desc.access_restricted),
            "detail": desc.access_note if desc else "",
        }
    )
    _emit({"backend": "local-files", "ok": all(bool(c["ok"]) for c in checks), "checks": checks})
    return 0


# ---------------------------------------------------------------- parser


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="magpie-local-tracker", description=__doc__)
    parser.add_argument("--root", help="tracker folder (or MAGPIE_LOCAL_TRACKER_ROOT)")
    sub = parser.add_subparsers(dest="command", required=True)

    def add(name: str, func: object, help_text: str) -> argparse.ArgumentParser:
        p = sub.add_parser(name, help=help_text)
        p.set_defaults(func=func)
        return p

    for name, func, help_text in (
        ("detect", cmd_detect, "infer the format from existing reports"),
        ("init", cmd_init, "write the default format descriptor"),
    ):
        p = add(name, func, help_text)
        if name == "detect":
            p.add_argument("--write", action="store_true", help="write the descriptor")
        p.add_argument("--force", action="store_true", help="replace an existing descriptor")
        p.add_argument("--prefix", help="ID prefix for new reports")
        p.add_argument("--url-template", help="browse URL with {path}")
        p.add_argument("--access-restricted", action="store_true", help="record the human access check")
        p.add_argument("--access-note", help="who checked the access control, and how")

    p = add("view", cmd_view, "show one report")
    p.add_argument("id")
    p.add_argument("--comments", action="store_true")

    p = add("list", cmd_list, "list reports")
    p.add_argument("--state", choices=["open", "closed", "all"], default="open")
    p.add_argument("--label", action="append", default=[])
    p.add_argument("--search")
    p.add_argument("--limit", type=int, default=100)

    add("labels", cmd_labels, "labels in use")

    p = add("field-get", cmd_field_get, "read one body field")
    p.add_argument("id")
    p.add_argument("heading")

    p = add("create", cmd_create, "create a report")
    p.add_argument("--title-file")
    p.add_argument("--title", help="title as one argv value (callers that never use a shell)")
    p.add_argument("--body-file", required=True)
    p.add_argument("--label", action="append", default=[])
    p.add_argument("--author")

    p = add("edit", cmd_edit, "edit labels, assignees, milestone, title or body")
    p.add_argument("id")
    for flag in ("--add-label", "--remove-label", "--add-assignee", "--remove-assignee"):
        p.add_argument(flag, action="append", default=[])
    p.add_argument("--milestone")
    p.add_argument("--clear-milestone", action="store_true")
    p.add_argument("--title-file")
    p.add_argument("--title", help="title as one argv value (callers that never use a shell)")
    p.add_argument("--body-file")

    p = add("field-set", cmd_field_set, "replace one body field")
    p.add_argument("id")
    p.add_argument("heading")
    p.add_argument("--value-file", required=True)

    p = add("comment", cmd_comment, "add a comment")
    p.add_argument("id")
    p.add_argument("--body-file", required=True)
    p.add_argument("--author")

    p = add("close", cmd_close, "close a report")
    p.add_argument("id")
    p.add_argument("--reason", choices=["completed", "not-planned"], default="completed")

    p = add("reopen", cmd_reopen, "reopen a report")
    p.add_argument("id")

    for name, func in (
        ("rollup-append", cmd_rollup_append),
        ("rollup-amend-latest", cmd_rollup_amend_latest),
    ):
        p = add(name, func, "status rollup")
        p.add_argument("id")
        p.add_argument("--action", required=True)
        p.add_argument("--entry-body-file", required=True)
        p.add_argument("--user")
        p.add_argument("--now")

    p = add("body", cmd_body, "print the report body as markdown (for generate-cve-json --stdin)")
    p.add_argument("id")

    p = add("attach", cmd_attach, "attach a file")
    p.add_argument("id")
    p.add_argument("file")
    p.add_argument("--name")

    add("pending", cmd_pending, "uncommitted tracker changes")

    p = add("publish", cmd_publish, "commit (and push) the tracker changes")
    p.add_argument("--message-file", required=True)
    p.add_argument("--trailer", action="append", default=[])
    p.add_argument("--push", action="store_true")

    add("doctor", cmd_doctor, "check the tracker setup")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except TrackerError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return exc.code
    except VcsRefused as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 4
    except VcsError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 5
    except OSError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 5
