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
Bump the npm packages pinned in ``.pre-commit-config.yaml`` hooks.

Dependabot's ``pre-commit`` ecosystem bumps a hook repository's ``rev`` but
never the packages a hook pins in ``additional_dependencies``, so a pin such as
``"@anthropic-ai/claude-code@2.1.292"`` would otherwise only move when someone
remembers it. This finds every ``<package>@<X.Y.Z>`` pin there, asks the npm
registry for the newest stable release that has cleared the package's
cooldown, and rewrites the pin in place.

The cooldown is the same idea as the 7 days in ``.github/dependabot.yml``: a
release gets time to be withdrawn or retagged before it reaches CI. Packages
can shorten it in ``COOLDOWN``. Claude Code gets 12 hours:

- it ships several times a day and a bad release is replaced within hours, so
  12 hours already covers the window a cooldown exists for;
- a security problem in it is fixed by the next release, so a week-long wait
  would hold CI on the known-bad version rather than protect it;
- the mods API is still moving and adopters auto-update, so the check has to
  track what they run;
- it is a dev-only tool here — CI runs it to check the mods, and nothing from
  it ships — so a bad version can at worst fail or wrongly pass that check.

Usage:

    bump-hook-npm-pins.py           # rewrite pins; print one line per bump
    bump-hook-npm-pins.py --check   # report only; exit 1 when a bump is due
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
import urllib.parse
import urllib.request
from collections.abc import Callable
from pathlib import Path

CONFIG = Path(__file__).resolve().parents[2] / ".pre-commit-config.yaml"

DEFAULT_COOLDOWN = dt.timedelta(days=7)

#: Per-package overrides of ``DEFAULT_COOLDOWN``.
COOLDOWN = {
    "@anthropic-ai/claude-code": dt.timedelta(hours=12),
}

#: A quoted ``<package>@<X.Y.Z>`` pin, scoped or not. Only exact stable
#: versions match, so a range or a ``cli:`` dependency is left alone.
PIN_RE = re.compile(r'"(?P<package>(?:@[a-z0-9._-]+/)?[a-z0-9._-]+)@(?P<version>\d+\.\d+\.\d+)"')

STABLE_RE = re.compile(r"^\d+\.\d+\.\d+$")

REGISTRY = "https://registry.npmjs.org/"


def find_pins(text: str) -> dict[str, str]:
    """Return ``{package: version}`` for every pin in ``additional_dependencies``."""
    pins: dict[str, str] = {}
    for line in text.splitlines():
        if line.strip().startswith("additional_dependencies:"):
            for match in PIN_RE.finditer(line):
                pins[match["package"]] = match["version"]
    return pins


def _key(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split("."))


def pick_version(times: dict[str, str], now: dt.datetime, cooldown: dt.timedelta) -> str | None:
    """The newest stable version published at least ``cooldown`` before ``now``.

    ``times`` is the registry's ``time`` map: version -> ISO publish time, plus
    the ``created`` and ``modified`` bookkeeping keys, which never look like a
    version and so drop out.
    """
    cutoff = now - cooldown
    eligible = [
        version
        for version, published in times.items()
        if STABLE_RE.match(version) and dt.datetime.fromisoformat(published.replace("Z", "+00:00")) <= cutoff
    ]
    return max(eligible, key=_key, default=None)


def fetch_times(package: str) -> dict[str, str]:
    url = REGISTRY + urllib.parse.quote(package, safe="@")
    with urllib.request.urlopen(url, timeout=30) as response:
        return json.load(response)["time"]


def bump(
    text: str,
    now: dt.datetime,
    fetch: Callable[[str], dict[str, str]] = fetch_times,
) -> tuple[str, list[tuple[str, str, str]]]:
    """Return the rewritten config and ``(package, old, new)`` for each bump.

    A pin already newer than anything eligible (bumped by hand onto a release
    still in its cooldown) is never moved backwards.
    """
    bumps = []
    for package, current in find_pins(text).items():
        cooldown = COOLDOWN.get(package, DEFAULT_COOLDOWN)
        target = pick_version(fetch(package), now, cooldown)
        if target is None or _key(target) <= _key(current):
            continue
        text = text.replace(f'"{package}@{current}"', f'"{package}@{target}"')
        bumps.append((package, current, target))
    return text, bumps


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--check", action="store_true", help="report only; exit 1 when a bump is due")
    args = parser.parse_args(argv)

    text = CONFIG.read_text(encoding="utf-8")
    new_text, bumps = bump(text, dt.datetime.now(dt.UTC))
    for package, old, new in bumps:
        print(f"{package}: {old} -> {new}")
    if args.check:
        return 1 if bumps else 0
    if bumps:
        CONFIG.write_text(new_text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
