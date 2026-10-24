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
"""Step 0 item 5: the `disclosure_governance` keys from `security-intake-config.md`.

A missing file or block is not an error: the skill silently applies the ASF
defaults (`manual`, 90 days). A value outside the vocabulary falls back to its
default too, and is named in `warnings` so the agent can mention it.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

MODELS = ("manual", "auto", "none")
DEFAULT_MODEL = "manual"
DEFAULT_WINDOW_DAYS = 90

_BLOCK = re.compile(r"^disclosure_governance:\s*(?:#.*)?$")
_KEY = re.compile(r"^\s+([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.*?)\s*$")


def _scalar(raw: str) -> str:
    value = re.sub(r"\s+#.*$", "", raw).strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
        value = value[1:-1]
    return value


def parse(text: str) -> dict[str, str] | None:
    """The `disclosure_governance` block's scalar keys, or None when there is no block."""
    lines = text.split("\n")
    start = next((i for i, line in enumerate(lines) if _BLOCK.match(line)), None)
    if start is None:
        return None
    keys: dict[str, str] = {}
    for line in lines[start + 1 :]:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if not line[:1].isspace() or line.strip().startswith("```"):
            break
        match = _KEY.match(line)
        if match:
            keys[match.group(1)] = _scalar(match.group(2))
    return keys


def resolve(config: str | Path) -> dict[str, Any]:
    path = Path(config)
    result: dict[str, Any] = {
        "config_file_found": path.is_file(),
        "reporter_acknowledgement_model": DEFAULT_MODEL,
        "window_days": DEFAULT_WINDOW_DAYS,
        "block_found": False,
        "warnings": [],
    }
    if not result["config_file_found"]:
        return result
    keys = parse(path.read_text(encoding="utf-8"))
    if keys is None:
        return result
    result["block_found"] = True
    model = keys.get("reporter_acknowledgement_model")
    if model is not None:
        if model in MODELS:
            result["reporter_acknowledgement_model"] = model
        else:
            result["warnings"].append(
                f"reporter_acknowledgement_model {model!r} is not one of {', '.join(MODELS)}; using {DEFAULT_MODEL}"
            )
    days = keys.get("window_days")
    if days is not None:
        if days.isdigit() and int(days) > 0:
            result["window_days"] = int(days)
        else:
            result["warnings"].append(
                f"window_days {days!r} is not a positive integer; using {DEFAULT_WINDOW_DAYS}"
            )
    return result
