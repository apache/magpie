#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# https://www.apache.org/licenses/LICENSE-2.0
"""List the commits on a ref that mention each open issue.

Usage: issue_refs.py [--ref REF] N [N ...]

For every issue number, prints the commits on REF (default HEAD) whose message
names `#N`, split into those that close it by keyword (`Fixes`, `Closes`,
`Resolves`) and those that only reference it.  An open issue with either kind
is a candidate for the "already resolved" review; the script decides nothing
more.  Output: one JSON object keyed by issue number.  Reads only the local
git history, so fetch the branch first.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys

CLOSING = re.compile(r"\b(?:fix(?:es|ed)?|close[sd]?|resolve[sd]?)\s*:?\s+#(\d+)\b", re.IGNORECASE)
PR_IN_SUBJECT = re.compile(r"\(#(\d+)\)\s*$")


def commits_mentioning(ref: str, number: int) -> list[dict[str, object]]:
    out = subprocess.run(
        ["git", "log", ref, "-E", f"--grep=#{number}([^0-9]|$)", "--format=%h%x1f%s%x1f%B%x1e"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    found: list[dict[str, object]] = []
    for record in out.split("\x1e"):
        record = record.strip("\n")
        if not record:
            continue
        sha, subject, body = record.split("\x1f", 2)
        pr = PR_IN_SUBJECT.search(subject)
        if pr and int(pr.group(1)) == number:
            continue  # the issue number is this commit's own PR number
        closes = any(int(m) == number for m in CLOSING.findall(body))
        found.append(
            {"sha": sha, "subject": subject, "pr": int(pr.group(1)) if pr else None, "closes": closes}
        )
    return found


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--ref", default="HEAD")
    parser.add_argument("issues", nargs="+", type=int)
    args = parser.parse_args(argv)
    result = {}
    for number in args.issues:
        commits = commits_mentioning(args.ref, number)
        result[str(number)] = {
            "closing": [c for c in commits if c["closes"]],
            "referencing": [c for c in commits if not c["closes"]],
        }
    json.dump(result, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
