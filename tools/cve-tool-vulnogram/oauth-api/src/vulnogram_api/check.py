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
"""Probe the stored Vulnogram session and report status.

Used by the agentic skills (``security-cve-allocate``,
``security-issue-sync``) to decide whether to propose the API path or
fall back to the copy-paste flow. Also useful as a manual sanity
check before walking through the release-manager checklist.

Exit codes:

- 0 — ``valid`` (cookie still works)
- 1 — ``expired`` (server bounced the request to ASF OAuth login)
- 2 — ``not-configured`` (no session JSON found at any candidate path)
- 3 — ``error`` (network failure or unexpected HTTP status)
"""

from __future__ import annotations

import argparse
import os
import pathlib
import sys

from vulnogram_api.client import probe
from vulnogram_api.credentials import (
    DEFAULT_CREDENTIALS_PATH,
    Session,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description=(__doc__ or "").split("\n\n", 1)[0],
    )
    ap.add_argument(
        "--credentials",
        default=None,
        help=(
            "Path to the session JSON. Defaults to "
            "$VULNOGRAM_SESSION, else "
            "~/.config/apache-steward/vulnogram-session.json."
        ),
    )
    ap.add_argument(
        "--section",
        default="cve5",
        help="Vulnogram section to probe. Default: cve5.",
    )
    ap.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress stdout; rely on exit code only (useful from skill probes).",
    )
    return ap.parse_args(argv)


def _resolve_path(explicit: str | None) -> pathlib.Path | None:
    """Like :func:`vulnogram_api.credentials.locate_session` but returns
    ``None`` instead of raising — callers map this to the
    ``not-configured`` exit code rather than a stack trace."""
    candidates: list[str | None] = [
        explicit,
        os.environ.get("VULNOGRAM_SESSION"),
        str(DEFAULT_CREDENTIALS_PATH),
    ]
    for c in candidates:
        if not c:
            continue
        p = pathlib.Path(c).expanduser()
        if p.is_file():
            return p
    return None


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    creds_path = _resolve_path(args.credentials)
    if creds_path is None:
        if not args.quiet:
            print("not-configured")
        return 2

    session = Session.load(creds_path)
    result = probe(session, section=args.section)
    if result in ("valid", "expired"):
        if not args.quiet:
            # Keep the first line a bare `valid` / `expired` so callers
            # that exact-match the result token still parse cleanly
            # (per the parse rules in
            # `.claude/skills/security-issue-sync/SKILL.md` Step 5b).
            # When a from-address is on file, surface it on a second
            # line for audit-trail visibility — *"did I capture the
            # cookie from the right @apache.org login?"*.
            print(result)
            if result == "valid" and session.from_address:
                print(f"logged in as {session.from_address}")
        return 0 if result == "valid" else 1

    # Anything else — network errors, unexpected HTTP status, etc.
    # Errors always go to stderr regardless of `--quiet` so callers
    # that pipe `2>/dev/null` get a clean channel and `--quiet`
    # invocations still see *why* the exit code is 3.
    print(result, file=sys.stderr)
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
