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
"""Path-glob matching for the triviality screen.

Globs match the repo-relative POSIX path, segment by segment: `**` matches
any number of segments (zero included), and every other segment is an
`fnmatch` pattern, so `*` never crosses a `/`. Matching is case-sensitive.
"""

from __future__ import annotations

from fnmatch import fnmatchcase
from functools import lru_cache


@lru_cache(maxsize=4096)
def _match(pattern: tuple[str, ...], path: tuple[str, ...]) -> bool:
    if not pattern:
        return not path
    head, rest = pattern[0], pattern[1:]
    if head == "**":
        return any(_match(rest, path[i:]) for i in range(len(path) + 1))
    return bool(path) and fnmatchcase(path[0], head) and _match(rest, path[1:])


def matches(glob: str, path: str) -> bool:
    return _match(tuple(glob.strip("/").split("/")), tuple(path.strip("/").split("/")))


def first_match(globs: list[str], path: str) -> str | None:
    return next((g for g in globs if matches(g, path)), None)
