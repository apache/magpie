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
Formerly a script beside the skill; now `release-management prepare prev-tag`,
which exits 2 on bad input. `train_of` / `covers` reuse the same train
matching for the Step 0 check that `release-trains.md` covers `<version>`.
"""

from __future__ import annotations

import re
from typing import Any

FINAL_RE = re.compile(r"^v?(\d+(?:\.\d+)+)(?:[.-]?post(\d+))?$")
TRAIN_RE = re.compile(r"^(\d+(?:\.\d+)*)\.x$")
TRAIN_IN_TEXT = re.compile(r"(?<![\w.])\d+(?:\.\d+)*\.x(?![\w])")
VERSION_IN_TEXT = re.compile(r"(?<![\w.])v?(\d+(?:\.\d+)+)(?:[.-]?post(\d+))?(?![\w.]*\w)")


class InputError(Exception):
    pass


def key(release: str, post: str | None) -> tuple[tuple[int, ...], int]:
    parts = [int(p) for p in release.split(".")]
    while len(parts) > 1 and parts[-1] == 0:
        parts.pop()
    return tuple(parts), int(post) if post is not None else -1


def parse_train(train: str) -> tuple[int, ...]:
    """`2.x` → `(2,)`, `2.11.x` → `(2, 11)`."""
    match = TRAIN_RE.match(train.strip())
    if not match:
        raise InputError(f"--train {train!r} is not a dotted prefix ending in .x (e.g. 2.x)")
    return tuple(int(p) for p in match.group(1).split("."))


def covers(line: str, version: str) -> bool | None:
    """Whether one `release-trains.md` release line covers `version`.

    True when a train pattern in it (`2.x`, `2.11.x`) contains the version, or it
    names the version itself; False when it names trains or versions and none
    match; None when it names neither, so the agent reads the line itself.
    """
    target = FINAL_RE.match(version)
    if not target:
        return None
    parts = tuple(int(p) for p in target.group(1).split("."))
    trains = [parse_train(m.group(0)) for m in TRAIN_IN_TEXT.finditer(line)]
    versions = list(VERSION_IN_TEXT.finditer(line))
    if not trains and not versions:
        return None
    if any(parts[: len(prefix)] == prefix for prefix in trains):
        return True
    target_key = key(target.group(1), target.group(2))
    return any(key(m.group(1), m.group(2)) == target_key for m in versions)


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
    train_prefix = parse_train(train) if train else (int(target.group(1).split(".")[0]),)

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
