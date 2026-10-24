# SPDX-License-Identifier: Apache-2.0
# https://www.apache.org/licenses/LICENSE-2.0

"""Command line interface: the security-tracker contract over a private Jira project.

See ``tools/security-tracker/contract.md`` for the operations, their JSON
output and the exit codes.  Every write on an existing issue first checks that
the issue carries an issue-security level and refuses (exit 4) otherwise.

Every request goes through `jira_bridge.rest.JiraRest`, so credentials follow its
rules: `JIRA_API_TOKEN` or the token file, bound to a host the user confirmed
(`JIRA_API_HOST` or a `host=` line), never sent elsewhere, and no write without it.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jira_bridge import markup
from jira_bridge.rest import JiraRest, JiraRestConfigError
from jira_bridge.tracker_client import (
    BackendError,
    JiraClient,
    NotFoundError,
    RefusedError,
    TrackerError,
    Transport,
    UsageError,
)

_KEY_RE = re.compile(r"^[A-Z][A-Z0-9_]*-\d+$")
_RAW = object()  # an operation that already wrote its own (non-JSON) output
_VIEW_FIELDS = "summary,status,resolution,labels,assignee,fixVersions,reporter,created,updated,description,security"
_LIST_FIELDS = "summary,status,resolution,labels,updated"
_LABEL_SCAN_CAP = 5000
_RESOLUTIONS = {"completed": "Fixed", "not-planned": "Won't Fix"}


@dataclass
class Config:
    url: str
    project: str
    security_level: str
    issue_type: str
    cloud: bool


# -- helpers -----------------------------------------------------------------


def _emit(data: Any) -> None:
    print(json.dumps(data, indent=2, ensure_ascii=False))


def _read_text(path: str, what: str) -> str:
    if path == "-":
        return sys.stdin.read()
    try:
        return Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        raise UsageError(f"cannot read {what} file {path}: {exc.strerror}") from exc


def jql_quote(value: str) -> str:
    """Quote ``value`` as a JQL string literal."""
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def expand_id(raw: str, project: str) -> str:
    """Expand a bare number with the project key and validate the key form."""
    value = raw.strip().upper()
    if value.isdigit():
        if not project:
            raise UsageError(
                f"bare id {raw!r} needs a project key (--project / SECURITY_TRACKER_PROJECT)"
            )
        value = f"{project}-{int(value)}"
    if not _KEY_RE.match(value):
        raise UsageError(f"invalid issue id {raw!r}: expected KEY-123 or a bare number")
    if project and value.rsplit("-", 1)[0] != project:
        raise UsageError(
            f"issue {value} is not in the configured security project {project}"
        )
    return value


def _person(person: Any) -> str | None:
    if not isinstance(person, dict):
        return None
    for key in ("name", "accountId", "displayName"):
        if person.get(key):
            return str(person[key])
    return None


def _state(fields: Mapping[str, Any]) -> str:
    if fields.get("resolution"):
        return "closed"
    status = fields.get("status") or {}
    category = (status.get("statusCategory") or {}).get("key")
    return "closed" if category == "done" else "open"


def _security_name(fields: Mapping[str, Any]) -> str | None:
    security = fields.get("security")
    if not isinstance(security, dict):
        return None
    return str(security.get("name") or security.get("id") or "") or None


def _date(now: str | None) -> str:
    if not now:
        return dt.datetime.now(dt.UTC).date().isoformat()
    try:
        return dt.datetime.fromisoformat(now.replace("Z", "+00:00")).date().isoformat()
    except ValueError as exc:
        raise UsageError(f"--now is not an ISO 8601 date/time: {now!r}") from exc


def _single_line(value: str, what: str) -> str:
    if "\n" in value or "\r" in value:
        raise UsageError(f"{what} must be a single line")
    return value.strip()


# -- the guard ---------------------------------------------------------------


def guarded_issue(
    client: JiraClient, key: str, extra_fields: str = "", *, level: str
) -> dict[str, Any]:
    """Fetch ``key`` and refuse unless it carries exactly the configured
    issue-security level.

    Any level is not enough: a scheme can define levels open to every logged-in
    user, and an issue created under one of those must not receive embargoed
    content.
    """
    if not level:
        raise RefusedError(
            f"refusing to write to {key}: no issue-security level is configured "
            "(--security-level / SECURITY_TRACKER_SECURITY_LEVEL / tracker.jira.security_level)"
        )
    fields = "security" + ("," + extra_fields if extra_fields else "")
    issue = client.issue(key, fields)
    actual = _security_name(issue.get("fields") or {})
    if actual is None:
        raise RefusedError(
            f"refusing to write to {key}: the issue has no issue-security level, so it is not "
            "access-restricted, and this backend will not write embargoed content to it. "
            "Ask a Jira project admin to set the security level; the backend never sets it on an existing issue."
        )
    if actual.strip().casefold() != level.strip().casefold():
        raise RefusedError(
            f"refusing to write to {key}: its issue-security level is {actual!r}, not the configured "
            f"{level!r}; a different level may be visible to people outside the security team"
        )
    return issue


# -- operations --------------------------------------------------------------


def op_view(client: JiraClient, cfg: Config, args: argparse.Namespace) -> Any:
    key = expand_id(args.id, cfg.project)
    issue = client.issue(key, _VIEW_FIELDS + (",comment" if args.comments else ""))
    fields = issue.get("fields") or {}
    level = _security_name(fields)
    warnings = []
    if level is None:
        warnings.append(
            f"{key} has no issue-security level: it is not access-restricted; writes are refused"
        )
    assignee = _person(fields.get("assignee"))
    versions = fields.get("fixVersions") or []
    result: dict[str, Any] = {
        "id": issue.get("key", key),
        "title": fields.get("summary") or "",
        "state": _state(fields),
        "labels": list(fields.get("labels") or []),
        "assignees": [assignee] if assignee else [],
        "milestone": versions[0].get("name") if versions else None,
        "author": _person(fields.get("reporter")),
        "created": fields.get("created"),
        "updated": fields.get("updated"),
        "body": fields.get("description") or "",
        "url": client.browse_url(issue.get("key", key)),
        "security_level": level,
        "warnings": warnings,
    }
    if args.comments:
        result["comments"] = [
            {
                "id": str(c.get("id")),
                "author": _person(c.get("author")),
                "created": c.get("created"),
                "body": c.get("body") or "",
            }
            for c in client.comments(key)
        ]
    return result


def op_list(client: JiraClient, cfg: Config, args: argparse.Namespace) -> Any:
    clauses = [f"project = {jql_quote(cfg.project)}"]
    # The same definition as _state(): closed is resolved *or* in the Done category.
    if args.state == "open":
        clauses.append("resolution is EMPTY AND statusCategory != Done")
    elif args.state == "closed":
        clauses.append("(resolution is not EMPTY OR statusCategory = Done)")
    clauses.extend(f"labels = {jql_quote(label)}" for label in args.label or [])
    if args.search:
        clauses.append(f"text ~ {jql_quote(args.search)}")
    jql = " AND ".join(clauses) + " ORDER BY updated DESC"
    if args.limit < 1:
        raise UsageError("--limit must be at least 1")
    return [
        {
            "id": issue.get("key"),
            "title": (issue.get("fields") or {}).get("summary") or "",
            "state": _state(issue.get("fields") or {}),
            "labels": list((issue.get("fields") or {}).get("labels") or []),
            "updated": (issue.get("fields") or {}).get("updated"),
            "url": client.browse_url(str(issue.get("key"))),
        }
        for issue in client.search(jql, _LIST_FIELDS, args.limit)
    ]


def op_labels(client: JiraClient, cfg: Config, args: argparse.Namespace) -> Any:
    jql = f"project = {jql_quote(cfg.project)} AND labels is not EMPTY ORDER BY updated DESC"
    found: set[str] = set()
    for issue in client.search(jql, "labels", _LABEL_SCAN_CAP):
        found.update((issue.get("fields") or {}).get("labels") or [])
    return sorted(found)


def op_field_get(client: JiraClient, cfg: Config, args: argparse.Namespace) -> Any:
    key = expand_id(args.id, cfg.project)
    fields = client.issue(key, "description").get("fields") or {}
    try:
        value = markup.get_field(fields.get("description") or "", args.heading)
    except markup.FieldNotFoundError as exc:  # a duplicate or disputed field
        raise RefusedError(str(exc)) from None
    return {"id": key, "heading": args.heading, "value": value}


def op_field_set(client: JiraClient, cfg: Config, args: argparse.Namespace) -> Any:
    key = expand_id(args.id, cfg.project)
    heading = _single_line(args.heading, "heading")
    value = _read_text(args.value_file, "value")
    issue = guarded_issue(client, key, "description", level=cfg.security_level)
    body = (issue.get("fields") or {}).get("description") or ""
    try:
        new_body, created = markup.set_field(body, heading, value)
    except markup.FieldNotFoundError as exc:  # a duplicate, disputed or unsafe rewrite
        raise RefusedError(str(exc)) from None
    client.call(
        "PUT", f"/rest/api/2/issue/{key}", payload={"fields": {"description": new_body}}
    )
    return {"id": key, "heading": heading, "created": created}


def _check_labels(labels: Sequence[str]) -> list[str]:
    for label in labels:
        if not label or any(ch.isspace() for ch in label):
            raise UsageError(
                f"invalid Jira label {label!r}: labels cannot be empty or contain whitespace"
            )
    return list(labels)


def _title_arg(args: argparse.Namespace) -> str | None:
    """The title from ``--title`` (argv, never a shell) or ``--title-file``."""
    if getattr(args, "title", None) is not None and args.title_file:
        raise UsageError("--title and --title-file are mutually exclusive")
    if getattr(args, "title", None) is not None:
        raw = str(args.title)
    elif args.title_file:
        raw = _read_text(args.title_file, "title")
    else:
        return None
    title = " ".join(raw.split())
    if not title:
        raise UsageError("title is empty")
    return title


def op_create(client: JiraClient, cfg: Config, args: argparse.Namespace) -> Any:
    if not cfg.security_level:
        raise RefusedError(
            "refusing to create: no issue-security level configured "
            "(--security-level / SECURITY_TRACKER_SECURITY_LEVEL / tracker.jira.security_level); "
            "an issue without one is not access-restricted"
        )
    title = _title_arg(args)
    if title is None:
        raise UsageError("create needs --title or --title-file")
    body = markup.escape_quoted_fields(_read_text(args.body_file, "body"))
    fields: dict[str, Any] = {
        "project": {"key": cfg.project},
        "summary": title,
        "description": body,
        "issuetype": {"name": cfg.issue_type},
        "security": {"name": cfg.security_level},
        "labels": _check_labels(args.label or []),
    }
    data = client.call("POST", "/rest/api/2/issue", payload={"fields": fields})
    key = str((data or {}).get("key") or "")
    if not key:
        raise BackendError("Jira did not return the created issue key")
    return {"id": key, "url": client.browse_url(key)}


def _assignee_ref(cfg: Config, user: str) -> dict[str, str]:
    return {"accountId": user} if cfg.cloud else {"name": user}


def op_edit(client: JiraClient, cfg: Config, args: argparse.Namespace) -> Any:
    key = expand_id(args.id, cfg.project)
    if args.milestone is not None and args.clear_milestone:
        raise UsageError("--milestone and --clear-milestone are mutually exclusive")
    adds = args.add_assignee or []
    if len(adds) > 1:
        raise UsageError(
            "a Jira issue has a single assignee: pass --add-assignee at most once"
        )
    fields: dict[str, Any] = {}
    update: dict[str, Any] = {}
    label_ops = [{"add": lb} for lb in _check_labels(args.add_label or [])]
    label_ops += [{"remove": lb} for lb in _check_labels(args.remove_label or [])]
    if label_ops:
        update["labels"] = label_ops
    if args.milestone is not None:
        fields["fixVersions"] = [{"name": args.milestone}]
    elif args.clear_milestone:
        fields["fixVersions"] = []
    title = _title_arg(args)
    if title is not None:
        fields["summary"] = title
    if args.body_file:
        fields["description"] = markup.escape_quoted_fields(_read_text(args.body_file, "body"))
    removes = args.remove_assignee or []
    if not (fields or update or adds or removes):
        raise UsageError("edit: nothing to change")
    issue = guarded_issue(client, key, "assignee", level=cfg.security_level)
    current = _person((issue.get("fields") or {}).get("assignee"))
    if adds:
        fields["assignee"] = _assignee_ref(cfg, adds[0])
    elif removes and current is not None and current in removes:
        fields["assignee"] = None
    payload: dict[str, Any] = {}
    if fields:
        payload["fields"] = fields
    if update:
        payload["update"] = update
    if payload:
        client.call("PUT", f"/rest/api/2/issue/{key}", payload=payload)
    return {"id": key, "url": client.browse_url(key)}


def op_comment(client: JiraClient, cfg: Config, args: argparse.Namespace) -> Any:
    key = expand_id(args.id, cfg.project)
    body = markup.neutralize(_read_text(args.body_file, "body"))
    guarded_issue(client, key, level=cfg.security_level)
    data = client.call(
        "POST", f"/rest/api/2/issue/{key}/comment", payload={"body": body}
    )
    comment_id = str((data or {}).get("id") or "")
    result: dict[str, Any] = {
        "id": key,
        "comment_id": comment_id,
        "url": client.comment_url(key, comment_id),
    }
    if args.author:
        # Jira records the authenticated user as the author; --author is informational only.
        result["author"] = args.author
        result["author_ignored"] = True
    return result


def _transitions(client: JiraClient, key: str) -> list[dict[str, Any]]:
    data = client.call(
        "GET",
        f"/rest/api/2/issue/{key}/transitions",
        params={"expand": "transitions.fields"},
    )
    return list((data or {}).get("transitions") or [])


def _target_category(transition: Mapping[str, Any]) -> str | None:
    return ((transition.get("to") or {}).get("statusCategory") or {}).get("key")


def op_close(client: JiraClient, cfg: Config, args: argparse.Namespace) -> Any:
    key = expand_id(args.id, cfg.project)
    issue = guarded_issue(client, key, "status,resolution", level=cfg.security_level)
    if _state(issue.get("fields") or {}) == "closed":
        return {"id": key, "state": "closed"}
    done = [t for t in _transitions(client, key) if _target_category(t) == "done"]
    if not done:
        raise BackendError(
            f"no transition to a done status is available on {key} for this user"
        )
    transition = done[0]
    path = f"/rest/api/2/issue/{key}/transitions"
    screen = transition.get("fields")
    with_resolution = not isinstance(screen, dict) or "resolution" in screen
    base: dict[str, Any] = {"transition": {"id": str(transition.get("id"))}}
    if with_resolution:
        payload = {
            **base,
            "fields": {"resolution": {"name": _RESOLUTIONS[args.reason]}},
        }
        try:
            client.call("POST", path, payload=payload)
            return {"id": key, "state": "closed"}
        except BackendError as exc:
            if exc.status != 400:
                raise
    client.call("POST", path, payload=base)
    return {"id": key, "state": "closed"}


def op_reopen(client: JiraClient, cfg: Config, args: argparse.Namespace) -> Any:
    key = expand_id(args.id, cfg.project)
    issue = guarded_issue(client, key, "status,resolution", level=cfg.security_level)
    if _state(issue.get("fields") or {}) == "open":
        return {"id": key, "state": "open"}
    candidates = [
        t
        for t in _transitions(client, key)
        if _target_category(t) not in (None, "done")
    ]
    if not candidates:
        raise BackendError(
            f"no transition to an open status is available on {key} for this user"
        )
    named = [t for t in candidates if "reopen" in str(t.get("name", "")).lower()]
    transition = (named or candidates)[0]
    client.call(
        "POST",
        f"/rest/api/2/issue/{key}/transitions",
        payload={"transition": {"id": str(transition.get("id"))}},
    )
    return {"id": key, "state": "open"}


def _find_rollup(client: JiraClient, key: str) -> dict[str, Any] | None:
    for comment in client.comments(key):
        if markup.is_rollup(str(comment.get("body") or "")):
            return comment
    return None


def _rollup_user(client: JiraClient, user: str | None) -> str:
    if user:
        return _single_line(user, "--user").lstrip("@")
    me = client.myself()
    name = me.get("name") or me.get("displayName")
    if not name:
        raise BackendError("cannot determine the authenticated Jira user; pass --user")
    return str(name)


def op_rollup_append(client: JiraClient, cfg: Config, args: argparse.Namespace) -> Any:
    key = expand_id(args.id, cfg.project)
    action = _single_line(args.action, "--action")
    entry_body = markup.neutralize(_read_text(args.entry_body_file, "entry body"))
    date = _date(args.now)
    guarded_issue(client, key, level=cfg.security_level)
    user = _rollup_user(client, args.user)
    existing = _find_rollup(client, key)
    entry = markup.RollupEntry(date, user, action, entry_body)
    if existing is None:
        data = client.call(
            "POST",
            f"/rest/api/2/issue/{key}/comment",
            payload={"body": markup.render_rollup([entry])},
        )
        comment_id = str((data or {}).get("id") or "")
    else:
        comment_id = str(existing.get("id"))
        entries = [*markup.parse_rollup(str(existing.get("body") or "")), entry]
        client.call(
            "PUT",
            f"/rest/api/2/issue/{key}/comment/{comment_id}",
            payload={"body": markup.render_rollup(entries)},
        )
    return {"id": key, "url": client.comment_url(key, comment_id)}


def op_rollup_amend_latest(
    client: JiraClient, cfg: Config, args: argparse.Namespace
) -> Any:
    key = expand_id(args.id, cfg.project)
    action = _single_line(args.action, "--action")
    entry_body = markup.neutralize(_read_text(args.entry_body_file, "entry body"))
    guarded_issue(client, key, level=cfg.security_level)
    existing = _find_rollup(client, key)
    entries = markup.parse_rollup(str(existing.get("body") or "")) if existing else []
    if existing is None or not entries:
        raise NotFoundError(f"{key} has no status rollup to amend")
    latest = entries[-1]
    if latest.action.strip() != action:
        raise RefusedError(
            f"latest rollup entry on {key} is {latest.action.strip()!r}, not {action!r}; not amending"
        )
    latest.body = entry_body
    comment_id = str(existing.get("id"))
    client.call(
        "PUT",
        f"/rest/api/2/issue/{key}/comment/{comment_id}",
        payload={"body": markup.render_rollup(entries)},
    )
    return {"id": key, "url": client.comment_url(key, comment_id)}


def op_body(client: JiraClient, cfg: Config, args: argparse.Namespace) -> Any:
    """The description as markdown `### Field` sections, for generate-cve-json --stdin."""
    key = expand_id(args.id, cfg.project)
    data = client.issue(key, "description")
    description = str((data.get("fields") or {}).get("description") or "")
    sys.stdout.write(markup.to_markdown_headings(description).strip("\n") + "\n")
    return _RAW


def op_attach(client: JiraClient, cfg: Config, args: argparse.Namespace) -> Any:
    key = expand_id(args.id, cfg.project)
    if args.file == "-":
        if not args.name:
            raise UsageError("attaching from stdin needs --name")
        content, name = sys.stdin.buffer.read(), Path(args.name).name
    else:
        path = Path(args.file)
        if not path.is_file():
            raise UsageError(f"attachment {args.file} is not a readable file")
        name = Path(args.name).name if args.name else path.name
        content = path.read_bytes()
    if not name:
        raise UsageError("attachment name is empty")
    guarded_issue(client, key, level=cfg.security_level)
    data = client.attach(key, name, content)
    first = data[0] if isinstance(data, list) and data else {}
    url = (
        first.get("content") if isinstance(first, dict) else None
    ) or client.browse_url(key)
    return {
        "id": key,
        "name": (first.get("filename") if isinstance(first, dict) else None) or name,
        "url": url,
    }


def op_pending(client: JiraClient | None, cfg: Config, args: argparse.Namespace) -> Any:
    return {"backend": "jira", "changes": [], "needs_publish": False}


def op_publish(client: JiraClient | None, cfg: Config, args: argparse.Namespace) -> Any:
    return {
        "committed": False,
        "pushed": False,
        "revision": None,
        "note": "jira writes are immediate",
    }


def op_doctor(client: JiraClient | None, cfg: Config, args: argparse.Namespace) -> Any:
    checks: list[dict[str, Any]] = []

    def check(name: str, ok: bool, detail: str) -> None:
        checks.append({"name": name, "ok": ok, "detail": detail})

    check("url", bool(cfg.url), cfg.url or "ISSUE_TRACKER_URL / --url not set")
    check(
        "project",
        bool(cfg.project),
        cfg.project or "SECURITY_TRACKER_PROJECT / --project not set",
    )
    rest = client.rest if client is not None else None
    if rest is not None:
        check(
            "token",
            rest.authenticated,
            f"token confirmed for {rest.host} ({rest.auth_scheme})"
            if rest.authenticated
            else rest.auth_note
            or "no JIRA_API_TOKEN or token file; writes are refused",
        )
    check(
        "security_level",
        bool(cfg.security_level),
        cfg.security_level
        or "SECURITY_TRACKER_SECURITY_LEVEL / --security-level not set; create is refused",
    )
    if client is not None and cfg.url:
        try:
            me = client.myself()
            check(
                "auth",
                True,
                f"authenticated as {me.get('name') or me.get('displayName') or 'unknown'}",
            )
        except TrackerError as exc:
            check("auth", False, str(exc))
        if cfg.project:
            try:
                project = client.call("GET", f"/rest/api/2/project/{cfg.project}")
                check(
                    "project_reachable",
                    True,
                    str((project or {}).get("name") or cfg.project),
                )
            except TrackerError as exc:
                check("project_reachable", False, str(exc))
            if cfg.security_level:
                check(*_security_level_check(client, cfg))
    ok = all(c["ok"] for c in checks)
    return {"backend": "jira", "ok": ok, "checks": checks}


def _security_level_check(client: JiraClient, cfg: Config) -> tuple[str, bool, str]:
    name = "security_level_exists"
    try:
        data = client.call("GET", f"/rest/api/2/project/{cfg.project}/securitylevel")
    except NotFoundError:
        return name, True, "unverified: the security-level endpoint is not available"
    except BackendError as exc:
        if exc.status in (401, 403):
            return name, True, "unverified: not permitted to list security levels"
        return name, False, str(exc)
    levels = [str(level.get("name")) for level in (data or {}).get("levels") or []]
    if cfg.security_level in levels:
        return (
            name,
            True,
            f"{cfg.security_level!r} is a security level of {cfg.project}",
        )
    return (
        name,
        False,
        f"{cfg.security_level!r} not among the levels visible to this user: {levels}",
    )


# -- parser ------------------------------------------------------------------

_Op = Callable[[Any, Config, argparse.Namespace], Any]
_OFFLINE = {"pending", "publish", "doctor"}


def _common(parser: argparse.ArgumentParser, default: Any) -> None:
    parser.add_argument(
        "--url", default=default, help="Jira base URL (ISSUE_TRACKER_URL)."
    )
    parser.add_argument(
        "--project", default=default, help="Project key (SECURITY_TRACKER_PROJECT)."
    )
    parser.add_argument(
        "--security-level",
        default=default,
        help="Issue-security level name set on create (SECURITY_TRACKER_SECURITY_LEVEL).",
    )
    parser.add_argument(
        "--issue-type",
        default=default,
        help="Issue type for create (default Bug; SECURITY_TRACKER_ISSUE_TYPE).",
    )
    parser.add_argument(
        "--jira-cloud",
        action="store_true",
        default=default,
        help="Jira Cloud deployment: assignees are accountIds (JIRA_DEPLOYMENT=cloud).",
    )
    parser.add_argument(
        "--deployment",
        choices=["server", "cloud"],
        default=default,
        help="Jira deployment; when given, wins over JIRA_DEPLOYMENT and --jira-cloud.",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="magpie-jira-tracker",
        description="Security-tracker contract over a private Jira project (issue-security level required).",
    )
    _common(parser, None)
    common = argparse.ArgumentParser(add_help=False)
    _common(common, argparse.SUPPRESS)
    sub = parser.add_subparsers(dest="op", required=True)

    def add(name: str, func: _Op, help_text: str) -> argparse.ArgumentParser:
        p = sub.add_parser(name, parents=[common], help=help_text)
        p.set_defaults(func=func)
        return p

    p = add("view", op_view, "Show one tracker.")
    p.add_argument("id")
    p.add_argument("--comments", action="store_true")

    p = add("list", op_list, "List trackers.")
    p.add_argument("--state", choices=["open", "closed", "all"], default="open")
    p.add_argument("--label", action="append")
    p.add_argument("--search")
    p.add_argument("--limit", type=int, default=30)

    add("labels", op_labels, "Labels in use in the project.")

    p = add("field-get", op_field_get, "Read a body-field section.")
    p.add_argument("id")
    p.add_argument("heading")

    p = add("field-set", op_field_set, "Replace or append a body-field section.")
    p.add_argument("id")
    p.add_argument("heading")
    p.add_argument("--value-file", required=True)

    p = add("create", op_create, "Create a tracker with the configured security level.")
    p.add_argument("--title-file")
    p.add_argument(
        "--title", help="title as one argv value (callers that never use a shell)"
    )
    p.add_argument("--body-file", required=True)
    p.add_argument("--label", action="append")

    p = add("edit", op_edit, "Edit labels, assignee, milestone, title or body.")
    p.add_argument("id")
    p.add_argument("--add-label", action="append")
    p.add_argument("--remove-label", action="append")
    p.add_argument("--add-assignee", action="append")
    p.add_argument("--remove-assignee", action="append")
    p.add_argument("--milestone")
    p.add_argument("--clear-milestone", action="store_true")
    p.add_argument("--title-file")
    p.add_argument(
        "--title", help="title as one argv value (callers that never use a shell)"
    )
    p.add_argument("--body-file")

    p = add("comment", op_comment, "Add a comment.")
    p.add_argument("id")
    p.add_argument("--body-file", required=True)
    p.add_argument("--author")

    p = add("close", op_close, "Close via a transition to a done status.")
    p.add_argument("id")
    p.add_argument("--reason", choices=sorted(_RESOLUTIONS), default="completed")

    p = add("reopen", op_reopen, "Reopen via a transition to a not-done status.")
    p.add_argument("id")

    p = add("rollup-append", op_rollup_append, "Append a status-rollup entry.")
    p.add_argument("id")
    p.add_argument("--action", required=True)
    p.add_argument("--entry-body-file", required=True)
    p.add_argument("--user")
    p.add_argument("--now")

    p = add(
        "rollup-amend-latest",
        op_rollup_amend_latest,
        "Replace the latest rollup entry's body.",
    )
    p.add_argument("id")
    p.add_argument("--action", required=True)
    p.add_argument("--entry-body-file", required=True)

    p = add(
        "body",
        op_body,
        "Print the description as markdown sections (for generate-cve-json --stdin).",
    )
    p.add_argument("id")

    p = add("attach", op_attach, "Attach a file.")
    p.add_argument("id")
    p.add_argument("file")
    p.add_argument("--name")

    add("pending", op_pending, "Unpublished changes (always none for Jira).")

    p = add("publish", op_publish, "No-op: Jira writes are immediate.")
    p.add_argument("--message-file")
    p.add_argument("--trailer", action="append")
    p.add_argument("--push", action="store_true")

    add("doctor", op_doctor, "Check configuration, credentials and the security level.")
    return parser


def resolve_config(args: argparse.Namespace, env: Mapping[str, str]) -> Config:
    explicit = getattr(args, "deployment", None)
    if explicit:
        cloud = explicit == "cloud"
    else:
        cloud = (
            bool(args.jira_cloud)
            or env.get("JIRA_DEPLOYMENT", "").strip().lower() == "cloud"
        )
    return Config(
        url=(args.url or env.get("ISSUE_TRACKER_URL", "")).strip().rstrip("/"),
        project=(args.project or env.get("SECURITY_TRACKER_PROJECT", ""))
        .strip()
        .upper(),
        security_level=(
            args.security_level or env.get("SECURITY_TRACKER_SECURITY_LEVEL", "")
        ).strip(),
        issue_type=(
            args.issue_type or env.get("SECURITY_TRACKER_ISSUE_TYPE", "")
        ).strip()
        or "Bug",
        cloud=cloud,
    )


def main(
    argv: Sequence[str] | None = None,
    *,
    transport: Transport | None = None,
    env: Mapping[str, str] | None = None,
) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code or 0)
    cfg = resolve_config(args, os.environ if env is None else env)
    try:
        client: JiraClient | None = None
        if cfg.url:
            rest = None
            if transport is None:
                try:
                    rest = JiraRest(cfg.url)
                except JiraRestConfigError as exc:
                    raise UsageError(str(exc)) from exc
            client = JiraClient(
                base_url=cfg.url,
                project=cfg.project,
                cloud=cfg.cloud,
                rest=rest,
                transport=transport,
            )
        elif args.op not in _OFFLINE:
            raise UsageError(
                "Jira URL not configured: set ISSUE_TRACKER_URL or pass --url"
            )
        if args.op not in _OFFLINE and not cfg.project:
            raise UsageError(
                "project key not configured: set SECURITY_TRACKER_PROJECT or pass --project"
            )
        result = args.func(client, cfg, args)
        if result is not _RAW:
            _emit(result)
        return 0
    except TrackerError as exc:
        print(f"magpie-jira-tracker: error: {exc}", file=sys.stderr)
        return exc.exit_code
