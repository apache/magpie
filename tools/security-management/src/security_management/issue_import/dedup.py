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
"""Step 2: exact identifier matching against saved tracker issue bodies.

The matcher uses the authoritative mailing-thread field and fails closed
when the index is incomplete or its field values are ambiguous.
Only issue summaries are exposed in the result.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from security_management.shared import fields, threads

# Gmail / PonyMail ids and maildir file names (`1700000000.M1P2.host,U=12:2,S`).
_OPAQUE_ID = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.,:=+-]{5,127}")
# An RFC-5322 Message-ID, angle brackets included: a conservative dot-atom on each side.
_MESSAGE_ID = re.compile(r"<[A-Za-z0-9!#%&'*+/=?^_{|}~.-]{1,128}@[A-Za-z0-9.-]{1,253}>")


def valid_ids(ids: Iterable[object]) -> tuple[list[str], list[str]]:
    good: list[str] = []
    bad: list[str] = []
    for raw in ids:
        text = str(raw).strip()
        if _OPAQUE_ID.fullmatch(text) or _MESSAGE_ID.fullmatch(text):
            if text not in good:
                good.append(text)
        else:
            bad.append(text)
    return good, bad


def _recorded_thread_ids(field_value: str) -> set[str]:
    """Extract all supported IDs from the authoritative mailing-thread field.

    Unlike threads.classify(), this scans all recorded entries, including
    those after import sentinels and multiple root Message-ID lines.
    """
    known: set[str] = set()

    gmail = re.compile(
        r"Gmail thread\s+(?:`([^`\r\n]+)`|"
        r"([A-Za-z0-9_][A-Za-z0-9_.,:=+-]{5,127}))",
        re.IGNORECASE,
    )
    archive = re.compile(r"/thread/([A-Za-z0-9_.,:=+-]{6,128})(?:[/?#]|$)")
    root = re.compile(
        r"^Root Message-ID:\s*`?(<[^`\s]+>)`?\s*$",
        re.IGNORECASE,
    )

    for line in field_value.splitlines():
        line = line.strip()

        for match in gmail.finditer(line):
            value = match.group(1) or match.group(2)
            if match.group(2):
                value = value.rstrip(".")
            if not valid_ids([value])[1]:
                known.add(value)

        for match in archive.finditer(line):
            value = match.group(1)
            if not valid_ids([value])[1]:
                known.add(value)

        root_match = root.fullmatch(line)
        if root_match:
            value = root_match.group(1)
            if not valid_ids([value])[1]:
                known.add(value)

    return known


def attribute_index(
    thread_ids: Iterable[object],
    issues: Sequence[Mapping[str, Any]],
    *,
    body_fields: Mapping[str, str] | None = None,
    limit: int = 1000,
) -> dict[str, Any]:
    """Match IDs against a bounded, complete issue-body index.

    Never expose body contents in the result. Missing or ambiguous
    authoritative fields prevent a definitive negative result when
    they cannot be interpreted safely.
    """
    good, bad = valid_ids(thread_ids)
    if bad:
        return {
            "ok": False,
            "refused": "thread ids no mail-source backend emits",
            "rejected_ids": bad,
        }

    tracked: dict[str, list[dict[str, Any]]] = {}
    undecided: list[dict[str, Any]] = []

    for issue in issues:
        summary = {key: issue.get(key) for key in ("number", "title", "state", "url")}
        if not isinstance(issue.get("body"), str):
            undecided.append(
                {
                    "number": issue.get("number"),
                    "reason": "missing or invalid issue body",
                }
            )
            continue

        parsed = fields.read(
            issue["body"],
            ["mailing_thread"],
            body_fields,
        )

        if parsed["undecided"]:
            undecided.append(
                {
                    "number": issue.get("number"),
                    "reason": "ambiguous mailing_thread field",
                }
            )
            continue

        field_value = parsed["values"].get("mailing_thread", "")
        if not field_value:
            continue

        identity = threads.classify(field_value)
        if identity["needs_decision"]:
            undecided.append(
                {
                    "number": issue.get("number"),
                    "reason": "mailing_thread needs a decision",
                }
            )
            continue

        known = _recorded_thread_ids(field_value)

        for candidate in good:
            if candidate in known:
                tracked.setdefault(candidate, []).append(summary)

    truncated = len(issues) >= limit
    complete = not truncated and not undecided

    return {
        "ok": True,
        "tracked": tracked,
        "untracked": [candidate for candidate in good if candidate not in tracked] if complete else [],
        "complete": complete,
        "truncated": truncated,
        "undecided": undecided,
        "rejected_ids": [],
    }
