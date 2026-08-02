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

"""Render GitHub pull-request references for terminal output."""

from __future__ import annotations

import argparse
import os
import re
from collections.abc import Mapping, Sequence

_SHORT_REFERENCE = re.compile(
    r"(?P<owner>[A-Za-z0-9_.-]+)/(?P<repo>[A-Za-z0-9_.-]+)#(?P<number>[1-9][0-9]*)\Z"
)
_URL_REFERENCE = re.compile(
    r"https://github\.com/(?P<owner>[A-Za-z0-9_.-]+)/"
    r"(?P<repo>[A-Za-z0-9_.-]+)/pull/(?P<number>[1-9][0-9]*)/?\Z"
)
_NUMBER_REFERENCE = re.compile(r"#(?P<number>[1-9][0-9]*)\Z")
_REPOSITORY = re.compile(r"(?P<owner>[A-Za-z0-9_.-]+)/(?P<repo>[A-Za-z0-9_.-]+)\Z")


def parse_pr_reference(
    reference: str, repository: str | None = None
) -> tuple[str, str]:
    """Return the display text and canonical URL for a GitHub PR reference."""
    short_match = _SHORT_REFERENCE.fullmatch(reference)
    if short_match is not None:
        display = reference
        owner = short_match.group("owner")
        repo = short_match.group("repo")
        number = short_match.group("number")
    else:
        url_match = _URL_REFERENCE.fullmatch(reference)
        if url_match is not None:
            display = (
                f"https://github.com/{url_match.group('owner')}/"
                f"{url_match.group('repo')}/pull/{url_match.group('number')}"
            )
            owner = url_match.group("owner")
            repo = url_match.group("repo")
            number = url_match.group("number")
        else:
            number_match = _NUMBER_REFERENCE.fullmatch(reference)
            repository_match = (
                _REPOSITORY.fullmatch(repository) if repository is not None else None
            )
            if number_match is None or repository_match is None:
                raise ValueError(
                    "expected OWNER/REPO#NUMBER, "
                    "https://github.com/OWNER/REPO/pull/NUMBER, or "
                    "#NUMBER with --repo OWNER/REPO"
                )
            display = reference
            owner = repository_match.group("owner")
            repo = repository_match.group("repo")
            number = number_match.group("number")

    url = f"https://github.com/{owner}/{repo}/pull/{number}"
    return display, url


def terminal_supports_hyperlinks(environ: Mapping[str, str] | None = None) -> bool:
    """Return whether the environment indicates OSC 8 support."""
    env = os.environ if environ is None else environ
    if "NO_COLOR" in env:
        return False
    term = env.get("TERM", "")
    return bool(term) and term.lower() != "dumb"


def format_pr_reference(
    reference: str,
    environ: Mapping[str, str] | None = None,
    *,
    repository: str | None = None,
) -> str:
    """Format a PR reference as an OSC 8 link or a plain-text fallback."""
    display, url = parse_pr_reference(reference, repository)
    if terminal_supports_hyperlinks(environ):
        return f"\033]8;;{url}\033\\{display}\033]8;;\033\\"
    if display == url:
        return url
    return f"{display}  {url}"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Render GitHub pull-request references for terminal output."
    )
    parser.add_argument(
        "references",
        nargs="+",
        metavar="PR",
        help="OWNER/REPO#NUMBER or a canonical GitHub pull-request URL",
    )
    parser.add_argument(
        "--repo",
        metavar="OWNER/REPO",
        help="repository context required for references in #NUMBER form",
    )
    args = parser.parse_args(argv)

    try:
        rendered = [
            format_pr_reference(reference, repository=args.repo)
            for reference in args.references
        ]
    except ValueError as error:
        parser.error(str(error))

    print("\n".join(rendered))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
