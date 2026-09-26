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

"""The PEP 440 subset Magpie versions actually use, compared correctly.

Only two forms occur in a lock or a plugin listing: a release
(``0.2.0``) and a dated development build of one (``0.2.0.dev202609211315``).
The rule that matters, and the one a string comparison gets wrong in both
directions, is that a dev build sorts *below* the release it leads to while
``0.10.0`` sorts *above* ``0.9.0``.

Nothing here strips or rounds the ``.devN`` segment.  A dev build is a
version like any other: an adopter running one has accepted that it moves,
and telling them they are up to date when they are not would be the same
bug as telling them to downgrade.

Deliberately not `packaging.version`: this module is copied into an
adopter's gitignored `.apache-magpie-local/` and run with bare `python3`,
so it cannot depend on anything outside the standard library.
"""

from __future__ import annotations

import re

_VERSION_RE = re.compile(
    r"^\s*v?(?P<release>\d+(?:\.\d+)*)(?:\.dev(?P<dev>\d+))?\s*$",
    re.ASCII,
)


class InvalidVersion(ValueError):
    """Raised for a string this subset cannot order."""


def parse(text: str) -> tuple[tuple[int, ...], int, int]:
    """Return a sort key for `text`, or raise `InvalidVersion`.

    The key is `(release, is_release, dev)`: `is_release` is 1 for a final
    release and 0 for a dev build, so `0.2.0` outranks `0.2.0.dev1` while
    both outrank `0.1.9`.  `dev` orders two dev builds of the same release.
    """
    match = _VERSION_RE.match(text)
    if not match:
        raise InvalidVersion(f"not a Magpie version: {text!r}")
    release = tuple(int(part) for part in match.group("release").split("."))
    dev = match.group("dev")
    return (release, 0 if dev is not None else 1, int(dev) if dev is not None else 0)


def _padded(a: tuple[int, ...], b: tuple[int, ...]) -> tuple[tuple[int, ...], tuple[int, ...]]:
    """Pad the shorter release tuple with zeros so `1.2` == `1.2.0`."""
    width = max(len(a), len(b))
    return a + (0,) * (width - len(a)), b + (0,) * (width - len(b))


def compare(left: str, right: str) -> int:
    """-1, 0 or 1 as `left` sorts below, equal to, or above `right`."""
    (lrel, lfinal, ldev) = parse(left)
    (rrel, rfinal, rdev) = parse(right)
    lrel, rrel = _padded(lrel, rrel)
    lkey, rkey = (lrel, lfinal, ldev), (rrel, rfinal, rdev)
    if lkey < rkey:
        return -1
    return 1 if lkey > rkey else 0


def below(candidate: str, floor: str) -> bool:
    """True when `candidate` is strictly below `floor`.

    Being *ahead* of a floor is the normal case and never a finding, so
    this is the only direction the floor check asks about.
    """
    return compare(candidate, floor) < 0
