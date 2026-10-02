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
"""CLI front-end for the rollup-comment append helper.

Operates on GitHub issue comments via the ``gh`` CLI. Like the
sibling `github-body-field` tool, this never streams the rollup
body to the agent's stdout — the read / append / push happens in
the subprocess and only a one-line summary lands on the agent
side.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from github_rollup.rollup import (
    build_entry,
    build_new_rollup_body,
    is_rollup_body,
    iter_entries,
    left_trim_lines,
    rebuild_with_appended_entry,
    replace_latest_entry,
)


def _gh_list_comments(issue: str, repo: str | None) -> list[dict]:
    cmd = ["gh", "issue", "view", issue, "--json", "comments"]
    if repo:
        cmd.extend(["--repo", repo])
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        sys.stderr.write(result.stderr)
        raise SystemExit(result.returncode or 1)
    return json.loads(result.stdout).get("comments", [])


def _gh_auth_user() -> str:
    """Return the currently-authenticated `gh` user's login."""
    cmd = ["gh", "api", "user", "--jq", ".login"]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        sys.stderr.write(result.stderr)
        raise SystemExit(result.returncode or 1)
    return result.stdout.strip()


def _rest_id(comment: dict, repo: str) -> str:
    """REST id of a comment from `gh issue view --json comments`.

    The listing carries GraphQL node ids; the REST id is the number in
    the comment's `#issuecomment-<id>` URL. Fall back to scanning the
    repository's comments only when the URL does not carry it.
    """
    match = re.search(r"#issuecomment-(\d+)$", comment.get("url") or "")
    if match:
        return match.group(1)
    node_id = comment.get("id")
    rest_id_cmd = [
        "gh",
        "api",
        f"repos/{repo}/issues/comments?per_page=100",
        "--paginate",
        "--jq",
        f'.[] | select(.node_id == "{node_id}") | .id',
    ]
    result = subprocess.run(rest_id_cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        sys.stderr.write(result.stderr)
        raise SystemExit(result.returncode or 1)
    rest_id = result.stdout.strip().splitlines()
    if not rest_id:
        sys.stderr.write(f"error: could not map node_id {node_id!r} to REST id\n")
        raise SystemExit(1)
    return rest_id[0]


def _gh_patch_comment(comment: dict, repo: str, body: str) -> None:
    """PATCH an existing rollup comment with the rebuilt body."""
    patch_cmd = [
        "gh",
        "api",
        "-X",
        "PATCH",
        f"repos/{repo}/issues/comments/{_rest_id(comment, repo)}",
        "-f",
        f"body={body}",
    ]
    result = subprocess.run(patch_cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        sys.stderr.write(result.stderr)
        raise SystemExit(result.returncode or 1)


def _gh_get_comment(comment_id: str, repo: str) -> dict:
    cmd = ["gh", "api", f"repos/{repo}/issues/comments/{comment_id}"]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        sys.stderr.write(result.stderr)
        raise SystemExit(result.returncode or 1)
    return dict(json.loads(result.stdout))


def _gh_delete_comment(comment_id: str, repo: str) -> None:
    cmd = ["gh", "api", "-X", "DELETE", f"repos/{repo}/issues/comments/{comment_id}"]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        sys.stderr.write(result.stderr)
        raise SystemExit(result.returncode or 1)


def _gh_post_comment(issue: str, repo: str | None, body: str) -> str:
    """Post a comment; return its URL (``gh issue comment`` prints it)."""
    cmd = ["gh", "issue", "comment", issue, "--body-file", "-"]
    if repo:
        cmd.extend(["--repo", repo])
    result = subprocess.run(cmd, input=body, text=True, capture_output=True, check=False)
    if result.returncode != 0:
        sys.stderr.write(result.stderr)
        raise SystemExit(result.returncode or 1)
    return (result.stdout or "").strip()


def _print_url(url: str) -> None:
    """The rollup comment URL is the only stdout, so a caller can link to it
    without reading the rollup body."""
    if url:
        sys.stdout.write(f"{url}\n")


def _find_rollup(comments: list[dict]) -> dict | None:
    """Return the first comment whose body begins with the rollup
    marker, or None if no rollup exists on the issue."""
    for c in comments:
        body = c.get("body") or ""
        if is_rollup_body(body):
            return c
    return None


def _read_entry_body(args: argparse.Namespace) -> str:
    if args.entry_body is not None and args.entry_body_file is not None:
        sys.stderr.write("error: pass --entry-body OR --entry-body-file, not both\n")
        raise SystemExit(2)
    if args.entry_body is not None:
        return args.entry_body
    if args.entry_body_file is not None:
        if args.entry_body_file == "-":
            return sys.stdin.read()
        return Path(args.entry_body_file).read_text(encoding="utf-8")
    sys.stderr.write("error: one of --entry-body / --entry-body-file is required\n")
    raise SystemExit(2)


def _resolve_repo(args: argparse.Namespace) -> str:
    """`gh` defaults the repo to the cwd's tracking remote when
    `--repo` is omitted — but our PATCH path needs the repo string
    explicitly to build the REST URL. Look it up if not given.
    """
    if args.repo:
        return str(args.repo)
    cmd = ["gh", "repo", "view", "--json", "nameWithOwner", "--jq", ".nameWithOwner"]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        sys.stderr.write(result.stderr)
        raise SystemExit(result.returncode or 1)
    return result.stdout.strip()


def _format_date(now_iso: str | None) -> str:
    if now_iso is None:
        return datetime.now(UTC).strftime("%Y-%m-%d")
    return datetime.fromisoformat(now_iso.replace("Z", "+00:00")).strftime("%Y-%m-%d")


def _write_entry(issue: str, repo: str, entry: str, action: str, date: str, dry_run: bool) -> bool:
    """Append ``entry`` to the rollup on ``issue``, creating the rollup
    when none exists. Returns True when something was (or, in a dry run,
    would be) written."""
    rollup = _find_rollup(_gh_list_comments(issue, repo))
    if dry_run:
        if rollup is None:
            sys.stderr.write("dry-run: would CREATE a new rollup comment\n")
        else:
            sys.stderr.write(f"dry-run: would APPEND to existing rollup comment {rollup.get('url')}\n")
        return True
    if rollup is None:
        url = _gh_post_comment(issue, repo, build_new_rollup_body(entry, repo.split("/")[-1]))
        sys.stderr.write(f"created rollup on {repo}#{issue} ({action!r}, date={date})\n")
        _print_url(url)
        return True
    _gh_patch_comment(rollup, repo, rebuild_with_appended_entry(rollup["body"], entry))
    sys.stderr.write(f"appended to rollup on {repo}#{issue} ({action!r}, date={date})\n")
    _print_url(str(rollup.get("url") or ""))
    return True


def _cmd_append(args: argparse.Namespace) -> int:
    body = _read_entry_body(args)
    date = _format_date(args.now)
    user = args.user or _gh_auth_user()
    entry = build_entry(date=date, user=user, action=args.action, body=body)
    repo = _resolve_repo(args)
    if args.dry_run:
        sys.stderr.write(f"action={args.action!r} date={date} user=@{user.lstrip('@')}\n")
    _write_entry(args.issue, repo, entry, args.action, date, args.dry_run)
    return 0


def _cmd_amend_latest(args: argparse.Namespace) -> int:
    """Replace the body of the most recent entry, keeping its date and
    user. Refuses unless the latest entry's action is ``--action``, so a
    concurrent append by someone else is never overwritten."""
    body = _read_entry_body(args)
    repo = _resolve_repo(args)
    rollup = _find_rollup(_gh_list_comments(args.issue, repo))
    if rollup is None:
        sys.stderr.write(f"no rollup on {repo}#{args.issue}\n")
        return 3
    entries = iter_entries(rollup["body"])
    if not entries:
        sys.stderr.write(f"rollup on {repo}#{args.issue} has no entries\n")
        return 3
    latest = entries[-1]
    if latest.action != args.action:
        sys.stderr.write(f"latest entry is {latest.action!r}, not {args.action!r}; refusing to amend\n")
        return 4
    entry = build_entry(date=latest.date, user=latest.user, action=latest.action, body=body)
    if args.dry_run:
        sys.stderr.write(f"dry-run: would AMEND latest entry ({latest.action!r}, {latest.date})\n")
        return 0
    _gh_patch_comment(rollup, repo, replace_latest_entry(rollup["body"], entry))
    sys.stderr.write(f"amended latest entry on {repo}#{args.issue} ({latest.action!r})\n")
    _print_url(str(rollup.get("url") or ""))
    return 0


def _cmd_fold(args: argparse.Namespace) -> int:
    """Fold one legacy bot comment into the rollup: append its body
    (left-trimmed) as an entry dated and attributed to the original
    comment, then delete the legacy comment. The delete only runs after
    the append succeeded."""
    repo = _resolve_repo(args)
    legacy = _gh_get_comment(args.comment_id, repo)
    legacy_body = legacy.get("body") or ""
    if is_rollup_body(legacy_body):
        sys.stderr.write(f"comment {args.comment_id} is the rollup itself; refusing to fold\n")
        return 4
    login = (legacy.get("user") or {}).get("login") or ""
    date = (legacy.get("created_at") or "")[:10]
    entry = build_entry(date=date, user=login, action=args.action, body=left_trim_lines(legacy_body))
    if args.dry_run:
        sys.stderr.write(
            f"dry-run: would FOLD comment {args.comment_id} ({date} · @{login} · {args.action!r})\n"
        )
        _write_entry(args.issue, repo, entry, args.action, date, True)
        return 0
    _write_entry(args.issue, repo, entry, args.action, date, False)
    _gh_delete_comment(args.comment_id, repo)
    sys.stderr.write(f"deleted legacy comment {args.comment_id}\n")
    return 0


def _cmd_list(args: argparse.Namespace) -> int:
    repo = _resolve_repo(args)
    comments = _gh_list_comments(args.issue, repo)
    rollup = _find_rollup(comments)
    if rollup is None:
        sys.stderr.write(f"no rollup comment on {repo}#{args.issue}\n")
        return 3
    entries = iter_entries(rollup["body"])
    if args.json:
        sys.stdout.write(
            json.dumps(
                [{"date": e.date, "user": e.user, "action": e.action} for e in entries],
                indent=2,
            )
        )
        sys.stdout.write("\n")
    else:
        for e in entries:
            sys.stdout.write(f"{e.date} · {e.user} · {e.action}\n")
    return 0


def _cmd_latest(args: argparse.Namespace) -> int:
    repo = _resolve_repo(args)
    comments = _gh_list_comments(args.issue, repo)
    rollup = _find_rollup(comments)
    if rollup is None:
        sys.stderr.write(f"no rollup comment on {repo}#{args.issue}\n")
        return 3
    entries = iter_entries(rollup["body"])
    if not entries:
        sys.stderr.write(f"rollup on {repo}#{args.issue} has no entries\n")
        return 3
    last = entries[-1]
    sys.stdout.write(last.body)
    if not last.body.endswith("\n"):
        sys.stdout.write("\n")
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="github-rollup",
        description=(
            "Append to (or create) the status-rollup comment on a "
            "GitHub issue without bringing the rollup body into "
            "agent context."
        ),
    )
    parser.add_argument(
        "--repo",
        help="owner/repo. Defaults to the current working directory's tracked remote.",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    p_append = sub.add_parser("append", help="append (or create) a rollup entry")
    p_append.add_argument("issue", help="issue number")
    p_append.add_argument("--action", required=True, help="action label (e.g. 'CVE allocated')")
    p_append.add_argument("--entry-body", help="entry body text (use --entry-body-file for multi-line)")
    p_append.add_argument(
        "--entry-body-file",
        help="path to a file with the entry body; pass '-' to read stdin",
    )
    p_append.add_argument(
        "--user",
        help="@handle to record in the summary. Defaults to the authenticated gh user.",
    )
    p_append.add_argument(
        "--now",
        help="ISO-8601 timestamp; the date field is derived from this. Default: real now.",
    )
    p_append.add_argument(
        "--dry-run",
        action="store_true",
        help="print what would happen and exit without writing.",
    )
    p_append.set_defaults(func=_cmd_append)

    p_amend = sub.add_parser(
        "amend-latest", help="replace the body of the most recent entry, keeping its date and user"
    )
    p_amend.add_argument("issue", help="issue number")
    p_amend.add_argument("--action", required=True, help="action label the latest entry must carry")
    p_amend.add_argument("--entry-body", help="new entry body text")
    p_amend.add_argument("--entry-body-file", help="path to the new entry body; '-' reads stdin")
    p_amend.add_argument("--dry-run", action="store_true", help="print what would happen and exit")
    p_amend.set_defaults(func=_cmd_amend_latest)

    p_fold = sub.add_parser("fold", help="fold a legacy bot comment into the rollup, then delete it")
    p_fold.add_argument("issue", help="issue number")
    p_fold.add_argument("--comment-id", required=True, help="REST id of the legacy comment")
    p_fold.add_argument("--action", required=True, help="action label for the folded entry")
    p_fold.add_argument("--dry-run", action="store_true", help="print what would happen and exit")
    p_fold.set_defaults(func=_cmd_fold)

    p_list = sub.add_parser("list", help="list every entry in the rollup")
    p_list.add_argument("issue", help="issue number")
    p_list.add_argument("--json", action="store_true", help="JSON array instead of one line per entry")
    p_list.set_defaults(func=_cmd_list)

    p_latest = sub.add_parser("latest", help="print the most recent entry's body")
    p_latest.add_argument("issue", help="issue number")
    p_latest.set_defaults(func=_cmd_latest)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
