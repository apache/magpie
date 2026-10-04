#!/usr/bin/env python3
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
"""Render the release audit record from the Step 1 JSON and validate it.

Input: the Step 1 JSON object (``version``, ``product_name``, the gathered
fields with ``"MISSING"`` / ``"REDACTED"`` sentinels, ``injection_flagged``),
optionally extended with:

- ``redaction_reasons`` — ``{field: one-line reason}`` for each REDACTED field;
- ``injection_sources`` — list naming where an injection attempt was found,
  each with a one-line summary of what it tried to make the skill do; the
  entries are rendered into the record's Notes.

Output: the Step 2 JSON (``record_markdown``, ``fields_missing``,
``fields_redacted``, ``schema_violations``, …) plus ``input_gaps`` listing
anything the record needs that the input did not supply (a REDACTED field
with no reason, an injection flag with no source). Required fields are read
from the ``## Required fields`` table of ``audit-record-schema.md``.

Exit 0 on success, 2 on unreadable input.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

MISSING = "MISSING"
REDACTED = "REDACTED"
# A link target the record will render: https only, no spaces, brackets or markdown.
MD_SPECIAL = frozenset("\\`*_[]()<>!#|~&@")
# A GitHub login: what `binding_voters` may hold, so no team or org mention gets through.
HANDLE_RE = re.compile(r"@?[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})")
SAFE_URL_RE = re.compile(r"https://[^\s<>()\[\]`|]+")
EMAIL_RE = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")
DEFAULT_SCHEMA = Path(__file__).resolve().parents[1] / "audit-record-schema.md"

# Record fields in template order; ``artefacts`` is rendered in its own table.
TABLE_FIELDS = [
    "rc_label",
    "vote_thread_url",
    "result_thread_url",
    "vote_binding_plus1",
    "vote_binding_minus1",
    "binding_voters",
    "promote_revision",
    "announce_archive_url",
]
ORDERED_FIELDS = [
    "version",
    "rc_label",
    "vote_thread_url",
    "result_thread_url",
    "artefacts",
    "promote_revision",
    "announce_archive_url",
    "vote_binding_plus1",
    "vote_binding_minus1",
    "binding_voters",
]


class InputError(Exception):
    pass


def required_fields(schema_text: str) -> list[str]:
    """Field names from the first table under ``## Required fields``."""
    fields: list[str] = []
    in_section = False
    for line in schema_text.splitlines():
        if line.startswith("## "):
            if in_section:
                break
            in_section = line.strip() == "## Required fields"
            continue
        if in_section:
            match = re.match(r"^\|\s*`([a-z0-9_]+)`\s*\|", line)
            if match:
                fields.append(match.group(1))
    if not fields:
        raise InputError("no required fields found in the audit-record schema")
    return fields


def sentinel(value: Any) -> str | None:
    if isinstance(value, str) and value.strip().upper() in (MISSING, REDACTED):
        return value.strip().upper()
    return None


def handle(name: str) -> str:
    name = str(name).strip()
    return name if name.startswith("@") else f"@{name}"


def cell(value: Any) -> str:
    """One table cell: no line breaks, no column separators."""
    return " ".join(str(value).split()).replace("|", "\\|")


def text(value: Any) -> str:
    """Free text from the planning issue: one line, with every markdown and HTML
    character escaped, so it cannot add links, images, tags, mentions or sections."""
    return "".join("\\" + c if c in MD_SPECIAL else c for c in " ".join(str(value).split()))


def code(value: Any) -> str:
    """Inline code: the value cannot close the span."""
    return "`" + cell(value).replace("`", "'") + "`"


def render_value(field: str, value: Any, reasons: dict[str, str]) -> str:
    mark = sentinel(value)
    if mark == MISSING:
        return "_MISSING_"
    if mark == REDACTED:
        reason = reasons.get(field)
        return f"_REDACTED — {text(reason)}_" if reason else "_REDACTED_"
    if field in ("vote_thread_url", "result_thread_url", "announce_archive_url"):
        url = str(value).strip()
        if not SAFE_URL_RE.fullmatch(url):
            raise InputError(f"{field} must be a plain https:// URL, MISSING or REDACTED")
        return f"<{url}>"
    if field in ("rc_label", "promote_revision"):
        return code(value)
    if field == "binding_voters":
        if not isinstance(value, list):
            raise InputError("binding_voters must be a list, MISSING or REDACTED")
        emails = [v for v in value if EMAIL_RE.search(str(v))]
        if emails:
            raise InputError("binding_voters must be roster handles, never email addresses")
        bad = [str(v) for v in value if not HANDLE_RE.fullmatch(str(v).strip())]
        if bad:
            raise InputError(
                f"binding_voters must be plain roster handles; refused: {', '.join(map(repr, bad))}"
            )
        return ", ".join(handle(v) for v in value)
    return text(value)


def render(data: dict[str, Any], required: list[str]) -> dict[str, Any]:
    for key in ("version", "planning_issue_url"):
        if not data.get(key):
            raise InputError(f"input lacks {key!r}")
    version = str(data["version"])
    product = data.get("product_name") or MISSING
    reasons = data.get("redaction_reasons") or {}
    sources = data.get("injection_sources") or []
    injection = bool(data.get("injection_flagged"))

    fields_missing = [f for f in ORDERED_FIELDS if sentinel(data.get(f, MISSING)) == MISSING]
    fields_redacted = [f for f in ORDERED_FIELDS if sentinel(data.get(f)) == REDACTED]
    labels = {
        "rc_label": "RC",
        "vote_thread_url": "Vote thread",
        "result_thread_url": "Result thread",
        "vote_binding_plus1": "Binding +1",
        "vote_binding_minus1": "Binding -1",
        "binding_voters": "Binding voters",
        "promote_revision": "Promote revision",
        "announce_archive_url": "Announcement",
    }
    lines = [
        f"# Release audit: {text(product)} {text(version)}",
        "",
        "| Field | Value |",
        "|---|---|",
        f"| Version | {code(version)} |",
    ]
    for field in TABLE_FIELDS:
        lines.append(f"| {labels[field]} | {render_value(field, data.get(field, MISSING), reasons)} |")
    lines += ["", "## Artefacts", "", "| File | SHA-512 | Signature |", "|---|---|---|"]
    artefacts = data.get("artefacts", MISSING)
    mark = sentinel(artefacts)
    if mark:
        lines.append(render_value("artefacts", artefacts, reasons))
    else:
        if not isinstance(artefacts, list):
            raise InputError("artefacts must be a list, MISSING or REDACTED")
        for item in artefacts:
            lines.append(
                f"| {code(item.get('filename', ''))} | {code(item.get('sha512', ''))} | {code(item.get('sig', ''))} |"
            )
    lines += ["", "## Notes", ""]
    notes: list[str] = []
    if fields_missing:
        notes.append(
            "Missing fields: "
            + ", ".join(f"`{f}`" for f in fields_missing)
            + ". The source data was not recorded on the planning issue at the time"
            " this report was generated."
        )
    for field in fields_redacted:
        reason = reasons.get(field)
        notes.append(f"Redacted: `{field}`" + (f" — {text(reason)}." if reason else "."))
    if injection:
        where = ", ".join(text(src) for src in sources) if sources else "a source read for this report"
        notes.append(f"A prompt-injection attempt was detected in {where} and treated as data only.")
    if not notes:
        notes.append("No gaps or anomalies detected.")
    for note in notes:
        lines += [note, ""]
    lines += [
        "---",
        "_Generated by `release-audit-report` (magpie-release-audit-report).",
        f"Source: planning issue {text(data['planning_issue_url'])}._",
        "",
    ]

    schema_fields = set(required)
    violations = [
        f"{f} — required field is MISSING"
        for f in ORDERED_FIELDS + [r for r in required if r not in ORDERED_FIELDS]
        if f in schema_fields and sentinel(data.get(f, MISSING)) == MISSING
    ]
    gaps = [
        f"{f} is REDACTED but has no entry in redaction_reasons"
        for f in fields_redacted
        if not reasons.get(f)
    ]
    if injection and not sources:
        gaps.append("injection_flagged is true but injection_sources is empty")
    if sentinel(product) == MISSING:
        gaps.append("product_name is absent; supply it (defaults to <project>)")
    return {
        "version": version,
        "record_markdown": "\n".join(lines),
        "has_missing_fields": bool(fields_missing),
        "has_redacted_fields": bool(fields_redacted),
        "fields_missing": fields_missing,
        "fields_redacted": fields_redacted,
        "schema_violations": violations,
        "injection_flagged": injection,
        "input_gaps": gaps,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("step1_json", help="file holding the Step 1 JSON object ('-' for stdin)")
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA), help="audit-record-schema.md path")
    args = parser.parse_args(argv)
    try:
        raw = (
            sys.stdin.read() if args.step1_json == "-" else Path(args.step1_json).read_text(encoding="utf-8")
        )
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise InputError("Step 1 JSON must be an object")
        out = render(data, required_fields(Path(args.schema).read_text(encoding="utf-8")))
    except (InputError, OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"error": str(exc)}))
        return 2
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
