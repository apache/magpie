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
#
"""Fail-closed organization check for optional ASF network permissions."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from .layers import resolve

_COMMENT = re.compile(r"<!--.*?(?:-->|\Z)", re.DOTALL)
_FENCE = re.compile(r"^\s*(`{3,}|~{3,})")
_ROW = re.compile(r"^\s*\|\s*`?organization`?\s*\|\s*([^|]*)\|")
_LINE = re.compile(r"^\s*organization\s*:\s*(.*?)\s*$")
_QUOTED_ASF = re.compile(r"^`ASF`(?:\s+\([^\n]*\))?$")


def declares_asf(text: str) -> bool:
    """True only for one explicit, unambiguous ASF declaration.

    Accept the framework's Markdown table and organization: syntax.
    Ignore comments, fenced examples and blockquotes.
    """
    values: list[str] = []
    fence: str | None = None

    for line in _COMMENT.sub("", text).splitlines():
        marker = _FENCE.match(line) if not line.startswith(("    ", "\t")) else None

        if fence is not None:
            if marker:
                kind = marker.group(1)
                remainder = line[marker.end() :]
                if kind[0] == fence[0] and len(kind) >= len(fence) and not remainder.strip():
                    fence = None
            continue

        # Markdown indented code is an example, not a declaration.
        if line.startswith(("    ", "\t")):
            continue

        if marker:
            fence = marker.group(1)
            continue

        if line.lstrip().startswith(">"):
            continue

        row = _ROW.match(line)
        if row:
            values.append(row.group(1).strip())
            continue

        match = _LINE.match(line)
        if match:
            values.append(match.group(1).strip())

    if len(values) != 1:
        return False

    value = values[0]
    return value == "ASF" or _QUOTED_ASF.fullmatch(value) is not None


def is_asf_project(root: Path) -> bool:
    """Resolve project.md once, personal-first; never merge lower layers."""
    try:
        config = resolve(root, "project.md")
        return config is not None and declares_asf(config.read_text(encoding="utf-8"))
    except (OSError, UnicodeError):
        return False


_ASF_DOMAINS = (
    "lists.apache.org",
    "dist.apache.org",
    "repository.apache.org",
    "downloads.apache.org",
    "archive.apache.org",
    "cveprocess.apache.org",
)
_ASF_WEBFETCH = "WebFetch(domain:lists.apache.org)"


def selected_asf_network_settings(root: Path, fragment: Path) -> dict[str, object]:
    """Read the reviewed ASF overlay only for an explicitly configured ASF project."""
    if not is_asf_project(root):
        return {}

    data = json.loads(fragment.read_text(encoding="utf-8"))

    expected = {
        "sandbox": {"network": {"allowedDomains": list(_ASF_DOMAINS)}},
        "permissions": {"allow": [_ASF_WEBFETCH]},
    }

    if data != expected:
        raise ValueError("Invalid ASF network fragment: unexpected or missing grants")

    return data


def main(argv: list[str] | None = None) -> int:
    """Print the selected project-local network overlay as JSON."""
    parser = argparse.ArgumentParser(description="Select the reviewed ASF network settings for a project.")
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument(
        "--fragment", type=Path, default=Path(__file__).with_name("claude-settings.asf.fragment.json")
    )
    args = parser.parse_args(argv)

    try:
        settings = selected_asf_network_settings(args.project_root, args.fragment)
    except (OSError, UnicodeError, ValueError) as exc:
        parser.exit(1, f"ASF network policy error: {exc}\n")

    print(json.dumps(settings, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
