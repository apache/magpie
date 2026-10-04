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
"""Apply the archive retention rule to a distribution listing.

Inputs:

- ``--listing``: a text file, one entry per line, as the backend lists it
  (``svn list`` directory names with or without the trailing ``/``, release
  tags, key prefixes). Entries that do not start with a digit (``KEYS``,
  ``README.html``, sub-directories) are reported as ``non_version_entries``.
- ``--trains``: a JSON list of the *supported* trains from
  ``release-trains.md``, each ``{"label": "2.x", "pattern": "2.x"}`` and an
  optional ``"keep": N`` (default 1). A strict pattern is a dotted numeric
  prefix ending in ``.x`` (``2.x``, ``2.11.x``). Any other pattern is loose:
  pass ``"versions": [...]`` for it instead, or its candidates come back
  ``unmapped`` for the model to place.

Rule: per train, the newest ``keep`` versions stay and every earlier version
is past retention. ``keep`` below 1 would archive the latest release of a
supported train: that is a ``retention-rule-error`` — ``past_retention`` is
emptied and nothing may be archived. Versions mapped to no train are orphans
and are never archived. All lists are in ascending version order.

Exit 0 on success, 2 on bad input.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

VERSION_RE = re.compile(r"^v?(\d+(?:\.\d+)*)(.*)$")
STRICT_PATTERN_RE = re.compile(r"^(\d+(?:\.\d+)*)\.x$")


class InputError(Exception):
    pass


def version_key(version: str) -> tuple[Any, ...]:
    match = VERSION_RE.match(version)
    if not match:
        raise InputError(f"not a version: {version!r}")
    release = [int(p) for p in match.group(1).split(".")]
    while len(release) > 1 and release[-1] == 0:
        release.pop()
    suffix = match.group(2)
    post = re.fullmatch(r"[.-]?post(\d+)", suffix)
    if not suffix:
        tail: tuple[Any, ...] = (1, 0, "")
    elif post:
        tail = (2, int(post.group(1)), "")
    else:  # pre-release (rc, beta, -M1, ...) sorts before the final release
        parts = re.findall(r"\d+|[A-Za-z]+", suffix)
        tail = (0, 0, tuple((0, int(p), "") if p.isdigit() else (1, 0, p.lower()) for p in parts))
    return (tuple(release), tail)


def is_prerelease(version: str) -> bool:
    return version_key(version)[1][0] == 0


def release_parts(version: str) -> list[int]:
    match = VERSION_RE.match(version)
    assert match
    return [int(p) for p in match.group(1).split(".")]


def parse_listing(text: str) -> tuple[list[str], list[str]]:
    versions, other = [], []
    for raw in text.splitlines():
        entry = raw.strip().rstrip("/")
        if not entry:
            continue
        (versions if VERSION_RE.match(entry) else other).append(entry)
    return versions, other


def sweep(listing: list[str], trains: list[dict[str, Any]]) -> dict[str, Any]:
    found = sorted(set(listing), key=version_key)
    members: dict[str, list[str]] = {}
    keeps: dict[str, int] = {}
    strict: list[tuple[str, list[int]]] = []
    explicit: dict[str, str] = {}
    loose: list[str] = []
    for train in trains:
        label = train.get("label")
        if not label:
            raise InputError("every train needs a 'label'")
        if label in members:
            raise InputError(f"duplicate train label {label!r}")
        members[label] = []
        keep = train.get("keep", 1)
        if not isinstance(keep, int) or isinstance(keep, bool):
            raise InputError(f"train {label!r}: 'keep' must be an integer")
        keeps[label] = keep
        if "versions" in train:
            for v in train["versions"]:
                explicit[str(v).strip().rstrip("/")] = label
            continue
        match = STRICT_PATTERN_RE.match(str(train.get("pattern", "")).strip())
        if match:
            strict.append((label, [int(p) for p in match.group(1).split(".")]))
        else:
            loose.append(label)

    orphans, unmapped = [], []
    for version in found:
        if version in explicit:
            members[explicit[version]].append(version)
            continue
        parts = release_parts(version)
        hits = [label for label, prefix in strict if parts[: len(prefix)] == prefix]
        if len(hits) == 1:
            members[hits[0]].append(version)
        elif len(hits) > 1:
            unmapped.append({"version": version, "reason": f"matches several trains: {', '.join(hits)}"})
        elif loose:
            unmapped.append({"version": version, "reason": f"may belong to loose train(s): {', '.join(loose)}"})
        else:
            orphans.append(version)

    # A pre-release in the release area must never count as a train's latest release:
    # it would keep the RC and propose archiving the real latest release.
    prereleases: list[str] = []
    for label in members:
        finals = [v for v in members[label] if not is_prerelease(v)]
        prereleases += [v for v in members[label] if is_prerelease(v)]
        members[label] = finals
    prereleases.sort(key=version_key)
    latest = {label: vs[-1] for label, vs in members.items() if vs}
    rule_errors = [
        f"train {label!r} keeps {keeps[label]} version(s); the latest of every supported train must stay"
        for label in members
        if keeps[label] < 1 and members[label]
    ]
    past: list[str] = []
    if not rule_errors:
        for label, vs in members.items():
            past.extend(vs[: max(len(vs) - keeps[label], 0)])
    past.sort(key=version_key)

    reasons = []
    if rule_errors:
        reasons += [f"retention-rule-error: {e}" for e in rule_errors]
    reasons += [
        f"{v} is not listed in release-trains.md and is an orphan; no archival command will be "
        "proposed for it — the RM must decide whether to archive, keep, or reconcile it into a known train"
        for v in orphans
    ]
    reasons += [
        f"{v} is a pre-release in the release area; it is not counted for retention and no archival "
        "command will be proposed for it — the RM must decide whether it belongs there"
        for v in prereleases
    ]
    return {
        "releases_found": found,
        "past_retention": [] if rule_errors else past,
        "orphans": orphans,
        "prereleases": prereleases,
        "unmapped": unmapped,
        "latest_of_each_line": latest,
        "trains_without_releases": [label for label, vs in members.items() if not vs],
        "mapping_complete": not unmapped,
        "retention_rule_error": bool(rule_errors),
        "handoff_required": bool(rule_errors or orphans or prereleases),
        "handoff_reasons": reasons,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--listing", required=True, help="file: one dist entry per line ('-' for stdin)")
    parser.add_argument("--trains", required=True, help="JSON file: list of supported trains")
    args = parser.parse_args(argv)
    try:
        text = sys.stdin.read() if args.listing == "-" else Path(args.listing).read_text(encoding="utf-8")
        trains = json.loads(Path(args.trains).read_text(encoding="utf-8"))
        if not isinstance(trains, list) or not trains:
            raise InputError("--trains must hold a non-empty JSON list")
        versions, other = parse_listing(text)
        out = sweep(versions, trains)
        out["non_version_entries"] = other
    except (InputError, OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"error": str(exc)}))
        return 2
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
