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
"""Step 2: the CVE-ready title, the bare description the CNA container scopes to the product.

The cascade of `title-normalize.md`: leading tags (a `[...]` / `(...)` tag
naming *Security* or *Important*, `Security Report:`, the project name with an
optional version) twice, then until nothing changes the identifier-bearing
parentheticals anywhere (`(GHSA-…)` or `[GHSA-…]`, the project's external tracker IDs,
`split from #N`, a prior CVE ID) and the trailing `in <Project>`,
`(<Project> x.y)` and `(<name> follow-up)`; whitespace collapsed, a final
period dropped, the first letter capitalised. The project's names and
tracker prefixes come from `<project-config>/title-normalization.md`.

Fewer than 3 words left is an over-strip warning: over-stripping is worse
than one redundant word.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

from security_management.shared.rollup import one_line

TRACKER_PREFIXES = ("ZDRES", "HUNTR", "GHSL")
MIN_WORDS = 3
_DASHES = "\u2013\u2014"  # en and em dash
_SEP = rf"[ \t:|\-{_DASHES}]"
_MARK = rf"[:|\-{_DASHES}]"
_VERSION = r"(?:[ \t]+v?\d+(?:\.\d+)*(?:\.x)?)?"


def _patterns(names: Sequence[str], short: Sequence[str], prefixes: Sequence[str]) -> tuple[list[str], ...]:
    leading = [
        rf"^[ \t]*(?:\[[^\]]*\b(?:Security|Important)\b[^\]]*\]|\([^)]*\b(?:Security|Important)\b[^)]*\)){_SEP}*",
        rf"^[ \t]*Security (?:Report|Issue|Vulnerability|Bug){_SEP}+",
    ]
    trailing = []
    for name in names:
        n = re.escape(name)
        leading.append(rf"^[ \t]*{n}{_VERSION}[ \t]*{_MARK}?[ \t]*")
        trailing.append(rf"[ \t]+in[ \t]+{n}[ \t]*\.?$")
        trailing.append(rf"[ \t]*\({n}{_VERSION}\)\.?[ \t]*$")
    for name in short:
        leading.append(rf"^[ \t]*{re.escape(name)}{_VERSION}[ \t]*{_MARK}[ \t]*")
    # Reporter attribution belongs in the credits field; kept end-anchored because
    # the pattern is loose enough to eat a substantive clause mid-title.
    trailing.append(r"[ \t]*\([\w.][\w. -]*[ \t]+follow-up\)\.?[ \t]*$")
    ids = "|".join(re.escape(p) for p in prefixes)
    anywhere = [
        r"[ \t]*(?:\(GHSA-[\w-]+\)|\[GHSA-[\w-]+\])\.?",
        r"[ \t]*\([^)]*split from #\d+[^)]*\)\.?",
        r"[ \t]*\([^)]*\bCVE-\d{4}-\d{4,7}\b[^)]*\)\.?",
    ]
    if ids:
        anywhere.insert(1, rf"[ \t]*(?:\[(?:{ids})-[\w-]+\]|\((?:{ids})-[\w-]+\))\.?")
    return leading, anywhere, trailing


def strip(
    title: str, names: Sequence[str], short: Sequence[str] = (), prefixes: Sequence[str] = TRACKER_PREFIXES
) -> str:
    leading, anywhere, trailing = _patterns(names, short, prefixes)
    text = one_line(title)
    # Twice: stripping one tag can reveal the next.
    for _ in range(2):
        for pattern in leading:
            text = re.sub(pattern, "", text, flags=re.IGNORECASE)
    previous = None
    while previous != text:
        previous = text
        for pattern in anywhere + trailing:
            text = re.sub(pattern, "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text).strip().rstrip(".")
    return text[:1].upper() + text[1:]


def _list(value: Any) -> list[str]:
    if isinstance(value, str):
        value = [value]
    return [one_line(v) for v in value or [] if one_line(v)]


def normalize(data: Mapping[str, Any]) -> dict[str, Any]:
    names = _list(data.get("project_names"))
    if not names:
        return {
            "ok": False,
            "refused": "project_names is empty: read the project's names from title-normalization.md",
        }
    prefixes = data.get("tracker_prefixes")
    original = one_line(data.get("title"))
    normalized = strip(
        original,
        names,
        _list(data.get("short_names")),
        TRACKER_PREFIXES if prefixes is None else _list(prefixes),
    )
    words = len(normalized.split())
    warning = None
    if words < MIN_WORDS:
        count = "no words" if not words else f"only {words} word" + ("s" if words > 1 else "")
        warning = (
            f"Normalized title is {count} — verify no over-stripping occurred and consider a manual override "
            "before pasting it into the CVE tool"
        )
    return {
        "original_title": original,
        "normalized_title": normalized,
        "word_count": words,
        "changed": normalized != original,
        "over_strip_warning": warning,
    }
