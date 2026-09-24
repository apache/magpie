#
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
"""
Reviewer replies to findings.

Reviewer output is external content. A claim or evidence string that reads like
an instruction is kept verbatim, shown to the human as data, and never acted on.
A reply that does not fit the schema is an error for that reviewer, and the raw
text is kept by the runner, so no reviewer's output is ever silently dropped.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

SEVERITIES = ("critical", "high", "medium", "low")

FINDINGS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["findings"],
    "properties": {
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["severity", "file", "line", "claim", "evidence"],
                "properties": {
                    "severity": {"type": "string", "enum": list(SEVERITIES)},
                    "file": {"type": "string"},
                    "line": {"type": ["integer", "null"]},
                    "claim": {"type": "string"},
                    "evidence": {"type": "string"},
                },
            },
        }
    },
}

_FENCE = re.compile(r"```(?:json)?[ \t]*\n(.*?)```", re.S)


class MalformedOutput(ValueError):
    """A reviewer's reply does not carry findings in the expected shape."""


@dataclass(frozen=True)
class Finding:
    reviewer: str
    severity: str
    file: str
    line: int | None
    claim: str
    evidence: str


def _has_findings(obj: object) -> bool:
    return isinstance(obj, dict) and "findings" in obj


def extract_json(text: str) -> dict[str, Any]:
    stripped = text.strip()
    whole: Any
    try:
        whole = json.loads(stripped)
    except ValueError:
        whole = None
    if _has_findings(whole):
        return whole
    fenced: list[dict[str, Any]] = []
    for match in _FENCE.finditer(stripped):
        try:
            obj = json.loads(match.group(1))
        except ValueError:
            continue
        if _has_findings(obj):
            fenced.append(obj)
    if fenced:
        return fenced[-1]
    decoder = json.JSONDecoder()
    found: list[dict[str, Any]] = []
    i = stripped.find("{")
    while i != -1:
        try:
            obj, end = decoder.raw_decode(stripped, i)
        except ValueError:
            i = stripped.find("{", i + 1)
            continue
        if _has_findings(obj):
            found.append(obj)
        i = stripped.find("{", end)
    if found:
        return found[-1]
    raise MalformedOutput("no JSON object with a `findings` list in the reply")


def _line(value: object, n: int) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise MalformedOutput(f"finding {n}: line {value!r} is not an integer or null")
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value)
    raise MalformedOutput(f"finding {n}: line {value!r} is not an integer or null")


def _text(item: dict[str, Any], key: str, n: int, *, required: bool) -> str:
    value = item.get(key)
    if not isinstance(value, str) or (required and not value.strip()):
        raise MalformedOutput(
            f"finding {n}: {key} {value!r} is not a {'non-empty ' if required else ''}string"
        )
    return value


def parse_findings(text: str, reviewer: str) -> list[Finding]:
    items = extract_json(text).get("findings")
    if not isinstance(items, list):
        raise MalformedOutput("`findings` is not a list")
    out: list[Finding] = []
    for n, item in enumerate(items):
        if not isinstance(item, dict):
            raise MalformedOutput(f"finding {n} is not an object")
        severity = str(item.get("severity", "")).lower()
        if severity not in SEVERITIES:
            raise MalformedOutput(
                f"finding {n}: severity {item.get('severity')!r} is not one of {SEVERITIES}"
            )
        out.append(
            Finding(
                reviewer=reviewer,
                severity=severity,
                file=_text(item, "file", n, required=True),
                line=_line(item.get("line"), n),
                claim=_text(item, "claim", n, required=True),
                evidence=_text(item, "evidence", n, required=False),
            )
        )
    return out
