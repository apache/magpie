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
Only codex enforces the schema, so each finding is checked on its own: a
finding that cannot be read is skipped and reported, never silently dropped,
and does not cost the reviewer's other findings. A reply with no findings
object at all is an error for that reviewer; the runner keeps its raw text.
"""

from __future__ import annotations

import contextlib
import json
import re
from dataclasses import dataclass, replace
from pathlib import Path
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

_LINE_RANGE = re.compile(r"^\s*(\d+)\s*(?:[-\u2013:,]\s*\d+\s*)?$")


class MalformedOutput(ValueError):
    """A reviewer's reply carries no findings object at all."""


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
    """The whole reply as JSON, else the *last* top-level JSON object carrying
    `findings`, fenced or not: a reply may show an example or echo the prompt
    before its answer, and the answer comes last."""
    stripped = text.strip()
    try:
        whole = json.loads(stripped)
    except ValueError:
        whole = None
    if _has_findings(whole):
        return dict(whole)
    decoder = json.JSONDecoder()
    last: dict[str, Any] | None = None
    i = stripped.find("{")
    while i != -1:
        try:
            obj, end = decoder.raw_decode(stripped, i)
        except ValueError:
            i = stripped.find("{", i + 1)
            continue
        if _has_findings(obj):
            last = obj
        i = stripped.find("{", end)
    if last is None:
        raise MalformedOutput("no JSON object with a `findings` list in the reply")
    return last


def _line(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, str):
        if not value.strip():
            return None
        match = _LINE_RANGE.match(value)
        if match:
            return int(match.group(1))
    raise MalformedOutput(f"line {value!r} is not an integer, a range or null")


def _text(item: dict[str, Any], key: str, *, required: bool) -> str:
    value = item.get(key, "" if not required else None)
    if value is None and not required:
        return ""
    if not isinstance(value, str) or (required and not value.strip()):
        raise MalformedOutput(f"{key} {value!r} is not a {'non-empty ' if required else ''}string")
    return value


def _one(item: object, reviewer: str) -> Finding:
    if not isinstance(item, dict):
        raise MalformedOutput("not an object")
    severity = str(item.get("severity", "")).strip().lower()
    return Finding(
        reviewer=reviewer,
        severity=severity if severity in SEVERITIES else "low",
        file=_text(item, "file", required=False),
        line=_line(item.get("line")),
        claim=_text(item, "claim", required=True),
        evidence=_text(item, "evidence", required=False),
    )


def parse_findings(text: str, reviewer: str) -> tuple[list[Finding], list[str]]:
    """Findings, plus one message per finding that could not be read."""
    items = extract_json(text).get("findings")
    if not isinstance(items, list):
        raise MalformedOutput("`findings` is not a list")
    findings: list[Finding] = []
    problems: list[str] = []
    for n, item in enumerate(items):
        try:
            findings.append(_one(item, reviewer))
        except MalformedOutput as exc:
            problems.append(f"finding {n}: {exc}")
    return findings, problems


def normalize_path(finding: Finding, repo_dir: Path) -> Finding:
    """Report paths the same way whichever reviewer wrote them: repo-relative,
    without `./` or a diff's `a/` / `b/` prefix."""
    path = finding.file.strip()
    root = repo_dir.resolve()
    if path.startswith("/"):
        with contextlib.suppress(ValueError):
            path = str(Path(path).resolve().relative_to(root))
    while path.startswith("./"):
        path = path[2:]
    if path[:2] in ("a/", "b/") and not (root / path).exists() and (root / path[2:]).exists():
        path = path[2:]
    return finding if path == finding.file else replace(finding, file=path)
