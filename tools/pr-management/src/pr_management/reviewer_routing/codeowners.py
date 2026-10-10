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
"""CODEOWNERS: last matching rule wins, gitignore-style patterns."""

from __future__ import annotations

import fnmatch
import re


def parse(text: str) -> list[tuple[str, list[str]]]:
    rules: list[tuple[str, list[str]]] = []
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        parts = line.split()
        owners = [o.lstrip("@") for o in parts[1:] if o.startswith("@")]
        rules.append((parts[0], owners))
    return rules


def _matches(pattern: str, path: str) -> bool:
    anchored = pattern.startswith("/")
    pat = pattern.lstrip("/")
    if pat.endswith("/"):
        pat += "**"
    if "/" not in pat.rstrip("*") and not anchored:
        # A bare name matches at any depth.
        return any(fnmatch.fnmatch(part, pat) for part in path.split("/")) or fnmatch.fnmatch(path, pat)
    regex = re.escape(pat).replace(r"\*\*", ".*").replace(r"\*", "[^/]*").replace(r"\?", "[^/]")
    return re.match(rf"^{regex}(/.*)?$", path) is not None


def owners_of(path: str, rules: list[tuple[str, list[str]]]) -> list[str]:
    owners: list[str] = []
    for pattern, who in rules:
        if _matches(pattern, path):
            owners = who
    return owners
