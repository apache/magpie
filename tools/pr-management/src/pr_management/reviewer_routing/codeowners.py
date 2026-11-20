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
    """GitHub's CODEOWNERS glob: `*` stays within a component, `**` crosses it."""
    anchored = pattern.startswith("/")
    body = pattern.strip("/") if pattern != "/" else ""
    directory = pattern.endswith("/")
    out = ""
    i = 0
    while i < len(body):
        char = body[i]
        if body.startswith("**/", i):
            out += "(?:.*/)?"
            i += 3
            continue
        if body.startswith("**", i):
            out += ".*"
            i += 2
            continue
        if char == "*":
            out += "[^/]*"
        elif char == "?":
            out += "[^/]"
        else:
            out += re.escape(char)
        i += 1
    if not anchored and "/" not in body:
        out = "(?:.*/)?" + out  # a bare name matches at any depth
    # A pattern that names a directory owns everything below it; one whose last
    # component is a glob does not. `docs/*` matches `docs/getting-started.md`
    # but not `docs/build-app/troubleshooting.md`, while `/apps/github` owns
    # that whole subdirectory.
    last = body.rsplit("/", 1)[-1]
    literal_last = "*" not in last and "?" not in last
    if directory:
        tail = "/.*"
    elif literal_last:
        tail = "(?:/.*)?"
    else:
        tail = ""
    return re.match("^" + out + tail + "$", path) is not None


def owners_of(path: str, rules: list[tuple[str, list[str]]]) -> list[str]:
    owners: list[str] = []
    for pattern, who in rules:
        if _matches(pattern, path):
            owners = who
    return owners
