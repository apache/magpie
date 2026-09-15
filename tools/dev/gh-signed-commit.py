#!/usr/bin/env python3
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
Commit the working tree's changes through GitHub's `createCommitOnBranch`.

Why not `git commit` + `git push`: a commit made by a workflow with `git` is
unsigned, and a branch that requires signatures rejects it. Commits created
through this mutation are signed by GitHub itself and show as **Verified**,
with no key material anywhere in CI.

The mutation takes file *contents*, not a diff, so this collects the changed
paths from `git status --porcelain` and sends each one base64-encoded.
Deletions are sent as deletions. Nothing is staged and nothing is pushed —
the commit is created server-side on a branch that must already exist.

Usage:

    gh-signed-commit.py --branch <name> --message-file <path> [--repo owner/name]

`--repo` defaults to `GITHUB_REPOSITORY`. The branch's current tip is read
back from the remote and sent as `expectedHeadOid`, so a concurrent push
makes the mutation fail rather than silently clobber.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import subprocess
import sys
from pathlib import Path

#: The mutation. `fileChanges` carries whole file contents; GitHub computes the
#: tree, and signs the commit with its own key.
MUTATION = """
mutation ($input: CreateCommitOnBranchInput!) {
  createCommitOnBranch(input: $input) {
    commit {
      oid
      url
    }
  }
}
"""


class CommitError(RuntimeError):
    """Raised when the working tree or the arguments cannot produce a commit."""


def split_message(text: str) -> tuple[str, str]:
    """
    Split a commit message into its headline and body.

    The headline is the first line; the body is everything after the blank
    line that follows it. A message with no body yields an empty body, which
    the mutation accepts.
    """
    stripped = text.strip("\n")
    if not stripped.strip():
        raise CommitError("commit message is empty")
    headline, _, body = stripped.partition("\n")
    return headline.strip(), body.lstrip("\n")


def collect_changes(root: Path, porcelain: str) -> tuple[list[str], list[str]]:
    """
    Split `git status --porcelain=v1 -z` output into changed and deleted paths.

    Renames are reported by git as a rename record carrying both paths; they
    are decomposed into a deletion of the old path and an addition of the new
    one, because the mutation has no rename concept.
    """
    fields = [f for f in porcelain.split("\0") if f]
    changed: list[str] = []
    deleted: list[str] = []
    index = 0
    while index < len(fields):
        entry = fields[index]
        index += 1
        if len(entry) < 4:
            raise CommitError(f"unparsable git status entry: {entry!r}")
        status, path = entry[:2], entry[3:]
        if status[0] in ("R", "C"):
            # A rename/copy record is followed by its source path.
            if index >= len(fields):
                raise CommitError(f"rename entry {entry!r} has no source path")
            source = fields[index]
            index += 1
            if status[0] == "R":
                deleted.append(source)
            changed.append(path)
            continue
        if "D" in status:
            deleted.append(path)
        else:
            changed.append(path)
    return sorted(set(changed)), sorted(set(deleted))


def build_payload(
    *,
    repo: str,
    branch: str,
    expected_head_oid: str,
    headline: str,
    body: str,
    additions: list[tuple[str, bytes]],
    deletions: list[str],
) -> dict:
    """Build the `gh api graphql --input` document for the mutation."""
    if not additions and not deletions:
        raise CommitError("nothing to commit")
    file_changes: dict[str, list[dict[str, str]]] = {}
    if additions:
        file_changes["additions"] = [
            {"path": path, "contents": base64.b64encode(content).decode("ascii")}
            for path, content in additions
        ]
    if deletions:
        file_changes["deletions"] = [{"path": path} for path in deletions]
    return {
        "query": MUTATION,
        "variables": {
            "input": {
                "branch": {
                    "repositoryNameWithOwner": repo,
                    "branchName": branch,
                },
                "expectedHeadOid": expected_head_oid,
                "message": {"headline": headline, "body": body},
                "fileChanges": file_changes,
            }
        },
    }


def _run(args: list[str], *, cwd: Path | None = None, stdin: str | None = None) -> str:
    result = subprocess.run(args, cwd=cwd, input=stdin, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise CommitError(f"{' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--branch", required=True, help="branch to commit onto; must already exist")
    parser.add_argument("--message-file", required=True, type=Path, help="commit message file")
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY"), help="owner/name")
    parser.add_argument(
        "--expected-head-oid",
        help=(
            "commit the branch must still point at; the mutation fails if it has moved. "
            "Defaults to whatever the branch points at right now, which is a weaker "
            "guarantee — pass the sha the work was based on where you have it."
        ),
    )
    args = parser.parse_args(argv)

    if not args.repo:
        parser.error("--repo is required when GITHUB_REPOSITORY is unset")

    root = Path(_run(["git", "rev-parse", "--show-toplevel"]).strip())
    headline, body = split_message(args.message_file.read_text(encoding="utf-8"))
    changed, deleted = collect_changes(root, _run(["git", "status", "--porcelain=v1", "-z"], cwd=root))
    if not changed and not deleted:
        print("gh-signed-commit: working tree is clean; nothing to commit")
        return 0

    additions = [(path, (root / path).read_bytes()) for path in changed]
    head = args.expected_head_oid or _run(
        ["gh", "api", f"repos/{args.repo}/git/ref/heads/{args.branch}", "--jq", ".object.sha"]
    )
    payload = build_payload(
        repo=args.repo,
        branch=args.branch,
        expected_head_oid=head.strip(),
        headline=headline,
        body=body,
        additions=additions,
        deletions=deleted,
    )
    out = _run(
        ["gh", "api", "graphql", "--input", "-", "--jq", ".data.createCommitOnBranch.commit.url"],
        stdin=json.dumps(payload),
    )
    print(out.strip())
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except CommitError as exc:
        print(f"gh-signed-commit: {exc}", file=sys.stderr)
        sys.exit(1)
