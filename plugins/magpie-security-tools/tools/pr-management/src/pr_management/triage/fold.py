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
"""Splice a `pr-triage-fold` block into a PR description: replace, never append.

Every existing span from an opening `<!-- pr-triage-fold: … -->` marker through
its closing `<!-- /pr-triage-fold -->` marker is removed, inclusive, with the
blank lines around it; the new block is appended after one blank line. Applying
the same block twice yields the same body — exactly one block, always current.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from ..config import FOLD_CLOSE, FOLD_OPEN

_SPAN = re.compile(
    r"\n*[ \t]*<!--\s*" + re.escape(FOLD_OPEN) + r":.*?<!--\s*" + re.escape(FOLD_CLOSE) + r"\s*-->[ \t]*\n*",
    flags=re.DOTALL,
)
#: An opening marker with no closing one: everything after it is the old block.
_UNCLOSED = re.compile(r"\n*[ \t]*<!--\s*" + re.escape(FOLD_OPEN) + r":.*\Z", flags=re.DOTALL)


def read_body(path: Path) -> str:
    """A raw markdown body, or the JSON `pr-view-with-body` saved (its `body` field)."""
    text = path.read_text(encoding="utf-8")
    stripped = text.lstrip()
    if stripped.startswith("{"):
        try:
            data = json.loads(stripped)
        except json.JSONDecodeError:
            return text
        if isinstance(data, dict) and "body" in data:
            return str(data.get("body") or "")
    return text


def strip(body: str) -> tuple[str, bool]:
    """The body without any fold span, and whether one was there."""
    body = body.replace("\r\n", "\n")
    out, count = _SPAN.subn("\n\n", body)
    out, unclosed = _UNCLOSED.subn("", out)
    return out.strip("\n"), bool(count or unclosed)


def splice(body: str, block: str) -> tuple[str, bool]:
    kept, replaced = strip(body)
    block = block.replace("\r\n", "\n").strip("\n")
    new = f"{kept}\n\n{block}\n" if kept else f"{block}\n"
    return new, replaced
