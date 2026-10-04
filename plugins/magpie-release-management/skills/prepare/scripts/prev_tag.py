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
"""Find the previous release tag of the same train.

Reads tag names from ``--tags`` (one per line; ``git ls-remote --tags``
lines are accepted, ``^{}`` peel entries are folded) and prints the highest
*final* release tag below ``--version`` whose version falls in ``--train``.

- ``--train`` is the train pattern from ``release-trains.md`` (``2.x``,
  ``2.11.x``); default: the major version of ``--version``.
- A tag is a final release when it is ``[v]X.Y[.Z...]`` or carries a
  ``.postN`` suffix; release candidates and other pre-releases
  (``2.11.0rc1``, ``2.11.0-rc1``, ``3.0.0b1``) are skipped.
- ``--tag-prefix`` strips a namespace such as ``rel/`` or
  ``providers-amazon/``; without it, tags containing ``/`` are skipped.

``previous_tag`` is null when no tag qualifies (a first release, or a train
with no earlier release); the model then asks the Release Manager.
Exit 0 on success, 2 on bad input.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

FINAL_RE = re.compile(r"^v?(\d+(?:\.\d+)+)(?:[.-]?post(\d+))?$")
TRAIN_RE = re.compile(r"^(\d+(?:\.\d+)*)\.x$")


class InputError(Exception):
    pass


def key(release: str, post: str | None) -> tuple[tuple[int, ...], int]:
    parts = [int(p) for p in release.split(".")]
    while len(parts) > 1 and parts[-1] == 0:
        parts.pop()
    return tuple(parts), int(post) if post is not None else -1


def tag_names(text: str) -> list[str]:
    names: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        name = line.split()[-1]
        name = name.removeprefix("refs/tags/").removesuffix("^{}")
        if name not in names:
            names.append(name)
    return names


def find_previous(tags: list[str], version: str, train: str | None, prefix: str) -> dict[str, Any]:
    target = FINAL_RE.match(version)
    if not target:
        raise InputError(f"--version {version!r} is not a final release version")
    target_key = key(target.group(1), target.group(2))
    if train:
        match = TRAIN_RE.match(train.strip())
        if not match:
            raise InputError(f"--train {train!r} is not a dotted prefix ending in .x (e.g. 2.x)")
        train_prefix = tuple(int(p) for p in match.group(1).split("."))
    else:
        train_prefix = (int(target.group(1).split(".")[0]),)

    candidates: list[tuple[tuple[tuple[int, ...], int], str]] = []
    skipped_prerelease: list[str] = []
    for tag in tags:
        name = tag
        if prefix:
            if not name.startswith(prefix):
                continue
            name = name[len(prefix) :]
        elif "/" in name:
            continue
        m = FINAL_RE.match(name)
        if not m:
            if re.match(r"^v?\d+(?:\.\d+)+", name):
                skipped_prerelease.append(tag)
            continue
        parts = tuple(int(p) for p in m.group(1).split("."))
        if parts[: len(train_prefix)] != train_prefix:
            continue
        k = key(m.group(1), m.group(2))
        if k < target_key:
            candidates.append((k, tag))
    candidates.sort()
    return {
        "version": version,
        "train": train or f"{train_prefix[0]}.x",
        "previous_tag": candidates[-1][1] if candidates else None,
        "candidates_in_train": [t for _, t in candidates],
        "skipped_prerelease_tags": skipped_prerelease,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--tags", required=True, help="file of tag names or git ls-remote output ('-' for stdin)"
    )
    parser.add_argument("--version", required=True)
    parser.add_argument("--train", help="train pattern, e.g. 2.x or 2.11.x")
    parser.add_argument("--tag-prefix", default="", help="namespace to strip, e.g. rel/")
    args = parser.parse_args(argv)
    try:
        text = sys.stdin.read() if args.tags == "-" else Path(args.tags).read_text(encoding="utf-8")
        out = find_previous(tag_names(text), args.version, args.train, args.tag_prefix)
    except (InputError, OSError) as exc:
        print(json.dumps({"error": str(exc)}))
        return 2
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
