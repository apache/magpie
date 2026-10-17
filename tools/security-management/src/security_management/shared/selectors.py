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
"""Tracker issue numbers from a selector: `212`, `#212, #215`, `#210-#215`, `owner/repo#212`, an issue URL.

A reference into any repository other than `<tracker>` is refused, never
quietly re-pointed; so is a reversed range or one wider than `MAX_RANGE`.
The CVE token rule (`^CVE-\\d{4}-\\d{4,7}$`) lives here too: an unvalidated
token never reaches a search argument.
"""

from __future__ import annotations

import re

MAX_RANGE = 1000
CVE = re.compile(r"^CVE-\d{4}-\d{4,7}$")
_ITEM = re.compile(
    r"^(?:https://github\.com/(?P<url_repo>[\w.-]+/[\w.-]+)/(?:issues|pull)/(?P<url_n>\d+)(?:[/?#]\S*)?"
    r"|(?P<repo>[\w.-]+/[\w.-]+)#(?P<repo_n>\d+)"
    r"|#?(?P<lo>\d+)(?:-#?(?P<hi>\d+))?)$"
)


def issue_numbers(text: str, tracker: str) -> list[int]:
    """The issue numbers `text` names, in order, de-duplicated; `ValueError` naming the bad token."""
    numbers: list[int] = []
    joined = re.sub(r"(\d)\s*-\s*(#?\d)", r"\1-\2", text.strip())
    tokens = [t for t in re.split(r"[\s,]+", joined) if t]
    if not tokens:
        raise ValueError("no issue number given")
    for token in tokens:
        match = _ITEM.match(token)
        if not match:
            raise ValueError(f"{token!r} is not an issue number, range, {tracker}#N or issue URL")
        repo = match.group("url_repo") or match.group("repo")
        if repo is not None:
            if repo.lower() != tracker.lower():
                raise ValueError(f"{token!r} points at {repo}, not {tracker}")
            found = [int(match.group("url_n") or match.group("repo_n"))]
        else:
            lo = int(match.group("lo"))
            hi = int(match.group("hi") or lo)
            if hi < lo:
                raise ValueError(f"range {token!r} runs backwards")
            if hi - lo + 1 > MAX_RANGE:
                raise ValueError(f"range {token!r} spans more than {MAX_RANGE} issues")
            found = list(range(lo, hi + 1))
        numbers.extend(n for n in found if n not in numbers)
    if any(n < 1 for n in numbers):
        raise ValueError("issue numbers start at 1")
    return numbers
