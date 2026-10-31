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
"""``pii-reveal`` — substitute identifiers in stdin with stored real values.

Reads stdin (UTF-8), scans for ``<TYPE>-<hex>`` identifiers, and
replaces any that appear in the local mapping with their stored
real values. Identifiers not in the mapping are left untouched —
the redactor that produced them is on a different machine, or
the mapping file was deleted, and we have no way to reverse them.

Skills shell out to this command exactly once per outbound draft,
at the moment the rendered draft text is handed to the send /
draft-create tool. See ``tools/privacy-llm/pii.md`` for the
lifecycle.
"""

from __future__ import annotations

import argparse
import re
import sys

from redactor.mapping import (
    TYPE_CODES,
    Entry,
    load_mapping,
    locate_mapping_path,
)

# An identifier is one of the known type codes followed by a `-`
# and 6+ lowercase hex chars. The codes are listed explicitly to
# avoid matching arbitrary uppercase-prefixed tokens that happen
# to look identifier-shaped (the framework's prose contains
# things like ``HTTP-200`` that would match a generic
# ``[A-Z]+-[0-9a-f]+`` pattern).
_IDENTIFIER_PATTERN = re.compile(
    r"\b(" + "|".join(sorted(TYPE_CODES, key=len, reverse=True)) + r")-([0-9a-f]{6,})\b"
)


def reveal(text: str, mapping: dict[str, Entry]) -> str:
    """Replace each known identifier in ``text`` with its stored value."""

    def _sub(match: re.Match[str]) -> str:
        ident = match.group(0)
        entry = mapping.get(ident)
        if entry is None:
            return ident
        return entry.value

    return _IDENTIFIER_PATTERN.sub(_sub, text)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="pii-reveal",
        description="Replace identifiers in stdin with stored real PII values.",
    )
    parser.add_argument(
        "--mapping-path",
        default=None,
        help=(
            "Override the mapping file path. "
            "Default: $PII_MAPPING_PATH or ~/.config/apache-magpie/pii-mapping.json."
        ),
    )
    args = parser.parse_args(argv)

    mapping_path = locate_mapping_path(args.mapping_path)
    try:
        mapping = load_mapping(mapping_path)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 2

    text = sys.stdin.read()
    sys.stdout.write(reveal(text, mapping))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
