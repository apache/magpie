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
"""``pii-redact`` — replace declared PII values in stdin with identifiers.

Reads stdin (UTF-8), substitutes every occurrence of each declared
``--field <type>:<value>`` with the matching hash-prefixed
identifier, writes the result to stdout, persists any new
mapping entries to the local mapping file.

Skills shell out to this command immediately after fetching
content from a private source. See ``tools/privacy-llm/pii.md``
for the lifecycle.
"""

from __future__ import annotations

import argparse
import re
import sys

from redactor.mapping import (
    TYPE_NAMES,
    Entry,
    load_mapping,
    locate_mapping_path,
    save_mapping_atomic,
    upsert,
)


def parse_field(spec: str) -> tuple[str, str]:
    """Parse a ``<type>:<value>`` spec into ``(type_code, value)``.

    The ``<type>`` half accepts either a friendly type name
    (``reporter``, ``email``, …) or the type code (``R``, ``E``,
    …). Returns the canonical type code.
    """
    if ":" not in spec:
        raise SystemExit(f"--field value must be of the form <type>:<value>; got {spec!r}")
    type_part, value = spec.split(":", 1)
    type_part = type_part.strip()
    if not value:
        raise SystemExit(f"--field {type_part!r}: value is empty")
    # Accept friendly name first, then code.
    if type_part.lower() in TYPE_NAMES:
        return TYPE_NAMES[type_part.lower()], value
    if type_part.upper() in {"N", "E", "P", "IP", "H", "A"}:
        return type_part.upper(), value
    raise SystemExit(
        f"unknown field type {type_part!r}. "
        f"Use one of: {', '.join(sorted(TYPE_NAMES))} (friendly) "
        f"or {', '.join(sorted(TYPE_NAMES.values()))} (code)."
    )


def _build_pattern(value: str) -> re.Pattern[str] | None:
    """Build a case-insensitive, whitespace-normalised regex for ``value``.

    Splits on Python ``str.split`` whitespace and rejoins with
    ``[^\\S\\n]+`` (any in-line whitespace — space, tab, NBSP — but
    *not* newline). This matches:

    - ``Jane Smith`` → ``jane smith``, ``Jane  Smith`` (double-space),
      ``Jane\\tSmith``, ``JANE SMITH``;

    and deliberately does **not** match:

    - ``Jane\\nSmith`` (paragraph break — the original text almost
      never wraps a name across lines, and matching there risks
      redacting unrelated lines that happen to share endpoints).

    Returns ``None`` for empty values and whitespace-only values
    (the caller skips those — preserves the prior empty-value
    behaviour).
    """
    parts = [re.escape(p) for p in value.split()]
    if not parts:
        return None
    return re.compile(r"[^\S\n]+".join(parts), re.IGNORECASE)


def apply_redactions(text: str, fields: list[tuple[str, str, Entry]]) -> str:
    """Substitute every declared value with its identifier.

    Substitutes longer values first so that a value which is a
    substring of another (e.g. reporter ``Jane`` inside email
    ``jane@x.com``) does not break the longer match.

    Matching is **case-insensitive** and **whitespace-normalised**
    (variable-width spaces, tabs, NBSPs between tokens all match).
    Values that span newlines are still matched only as supplied;
    see :func:`_build_pattern` for the exact whitespace class.
    """
    # Sort by raw value length descending so the longer match wins
    # against substring overlap (e.g. reporter `Jane` vs email
    # `jane@x.com`).
    fields_sorted = sorted(fields, key=lambda triple: len(triple[1]), reverse=True)
    for _type_code, value, entry in fields_sorted:
        pattern = _build_pattern(value)
        if pattern is None:
            continue
        text = pattern.sub(entry.identifier, text)
    return text


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="pii-redact",
        description="Replace declared PII values in stdin with hash-prefixed identifiers.",
    )
    parser.add_argument(
        "--field",
        action="append",
        default=[],
        metavar="<type>:<value>",
        help=(
            "PII to redact, declared as type:value. "
            "Repeat for each field. Type is one of: "
            "name, email, phone, ip, handle, address (or codes N, E, P, IP, H, A)."
        ),
    )
    parser.add_argument(
        "--mapping-path",
        default=None,
        help=(
            "Override the mapping file path. "
            "Default: $PII_MAPPING_PATH or ~/.config/apache-steward/pii-mapping.json."
        ),
    )
    args = parser.parse_args(argv)

    if not args.field:
        # Nothing declared — pass stdin to stdout unchanged. This
        # is a legitimate case (skill calling redact on a body
        # that turned out to have no fields to redact for this
        # message).
        sys.stdout.write(sys.stdin.read())
        return 0

    mapping_path = locate_mapping_path(args.mapping_path)
    try:
        mapping = load_mapping(mapping_path)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 2

    declared: list[tuple[str, str, Entry]] = []
    for spec in args.field:
        type_code, value = parse_field(spec)
        entry = upsert(mapping, type_code, value)
        declared.append((type_code, value, entry))

    text = sys.stdin.read()
    redacted = apply_redactions(text, declared)
    sys.stdout.write(redacted)

    save_mapping_atomic(mapping_path, mapping)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
