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
"""The six triage dispositions and the two literal markers of a triage proposal.

`security-issue-triage` writes the markers; its pre-flight skip and
`security-issue-invalidate`'s `invalidate proposed` read them back, so both
take them from here. `parse_time` reads the timestamps both compare.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

CLASSES = ("VALID", "DEFENSE-IN-DEPTH", "INFO-ONLY", "INVALID", "PROBABLE-DUP", "FIX-ALREADY-PUBLIC")
PROPOSAL_HEADER = "**Triage proposal**"
DISPOSITION_PREFIX = "**Proposed disposition: "
_DISPOSITION = re.compile(r"^\*\*Proposed disposition: ([A-Z-]+)\.?\*\*")


def normalise_class(value: object) -> str | None:
    """`value` as one of the six classes (`defense in depth` → `DEFENSE-IN-DEPTH`), else `None`."""
    text = re.sub(r"[\s_]+", "-", str(value or "").strip().upper()).strip(".")
    return text if text in CLASSES else None


def proposal_class(comment_body: str) -> str | None:
    """The class a triage proposal names, when `comment_body` carries both markers; else `None`.

    The first non-blank line must be the header, and a line must begin with the
    disposition prefix: the shape the Step 4 template writes, nothing looser.
    """
    lines = [ln.strip() for ln in str(comment_body or "").replace("\r\n", "\n").split("\n")]
    first = next((ln for ln in lines if ln), "")
    if first != PROPOSAL_HEADER:
        return None
    for line in lines:
        if line.startswith(DISPOSITION_PREFIX):
            match = _DISPOSITION.match(line)
            return match.group(1) if match else ""
    return None


def parse_time(value: object) -> datetime | None:
    """An ISO 8601 timestamp (`Z` or offset) or epoch milliseconds, in UTC; `None` when unparsable."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return datetime.fromtimestamp(value / 1000, tz=UTC)
    text = str(value).strip()
    if text.isdigit():
        return datetime.fromtimestamp(int(text) / 1000, tz=UTC)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
