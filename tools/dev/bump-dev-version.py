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
Move the dev stamp in ``pyproject.toml``.

``project.version`` is the single authority every manifest mirrors, so a bump
is one edit here followed by ``check-family-plugins.py --fix`` and ``uv lock``.
This script is only the edit; it deliberately does not run the other two, so
the same three steps read the same whether a human or the workflow performs
them.

The suffix is a UTC timestamp at minute resolution. It has to *move* for
adopters to pick anything up: the marketplace is served from ``main`` and
``claude plugin update`` compares version strings, so a frozen suffix is a
silent no-op. See ``docs/setup/marketplace.md``.

Usage:

    bump-dev-version.py --print              # the current version, unchanged
    bump-dev-version.py                      # stamp with "now", in UTC
    bump-dev-version.py --stamp 202609151058 # stamp with a given value
"""

from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
from pathlib import Path

#: ``version = "..."`` in the ``[project]`` table. Anchored to the line start so
#: a dependency pin elsewhere in the file cannot match.
VERSION_RE = re.compile(r'^version = "(?P<version>.+?)"', re.MULTILINE)

#: A dev suffix: ``.dev`` plus a UTC ``YYYYMMDDHHMM`` stamp.
STAMP_RE = re.compile(r"^[0-9]{12}$")


class BumpError(RuntimeError):
    """Raised when the version cannot be read or rewritten."""


def read_version(text: str) -> str:
    """Return ``project.version`` from a ``pyproject.toml`` body."""
    match = VERSION_RE.search(text)
    if not match:
        raise BumpError('no `version = "..."` line found in pyproject.toml')
    return match.group("version")


def next_version(current: str, stamp: str) -> str:
    """
    Return *current* with its dev suffix replaced by *stamp*.

    A released version carries no suffix, and stamping one would advertise a dev
    build of a version that is already out; that is refused rather than guessed
    at, because the release flow sets the next base version deliberately.
    """
    if not STAMP_RE.match(stamp):
        raise BumpError(f"stamp must be 12 digits of UTC YYYYMMDDHHMM, got {stamp!r}")
    base, separator, _ = current.partition(".dev")
    if not separator:
        raise BumpError(
            f"version {current!r} carries no .dev suffix — it looks like a release. "
            "Set the next base version first; this script only moves an existing stamp."
        )
    return f"{base}.dev{stamp}"


def replace_version(text: str, current: str, new: str) -> str:
    """Rewrite the single ``version =`` line, leaving the rest of the file byte-identical."""
    updated, count = VERSION_RE.subn(f'version = "{new}"', text, count=1)
    if count != 1:
        raise BumpError(f"could not rewrite version {current!r} in pyproject.toml")
    return updated


def utc_stamp(now: dt.datetime | None = None) -> str:
    """The UTC ``YYYYMMDDHHMM`` stamp for *now*."""
    moment = now or dt.datetime.now(dt.UTC)
    return moment.strftime("%Y%m%d%H%M")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--pyproject", type=Path, default=Path("pyproject.toml"), help="path to pyproject.toml"
    )
    parser.add_argument("--stamp", help="UTC YYYYMMDDHHMM stamp; defaults to now")
    parser.add_argument(
        "--print", dest="print_only", action="store_true", help="print the current version and exit"
    )
    args = parser.parse_args(argv)

    text = args.pyproject.read_text(encoding="utf-8")
    current = read_version(text)
    if args.print_only:
        print(current)
        return 0

    new = next_version(current, args.stamp or utc_stamp())
    if new == current:
        print(f"bump-dev-version: already at {current}")
        return 0
    args.pyproject.write_text(replace_version(text, current, new), encoding="utf-8")
    print(f"bump-dev-version: {current} -> {new}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except BumpError as exc:
        print(f"bump-dev-version: {exc}", file=sys.stderr)
        sys.exit(1)
