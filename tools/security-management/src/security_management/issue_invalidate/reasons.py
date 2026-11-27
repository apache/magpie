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
"""The close reasons: `invalid` (the default), `defense-in-depth` and `info-only`.

`security-issue-triage` proposes six classes; three of them end in a close this
skill applies, each with its own reason. The reason picks the labels added
(`invalidate.reason_labels` in project.md overrides the defaults per reason),
the closing comment's wording, the rollup action label `Closed as <reason>`,
the default canned response and the next step. The close state is
`not planned` for every reason.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

INVALID = "invalid"
DEFENSE_IN_DEPTH = "defense-in-depth"
INFO_ONLY = "info-only"
REASONS = (INVALID, DEFENSE_IN_DEPTH, INFO_ONLY)
DEFAULT_LABELS: Mapping[str, tuple[str, ...]] = {
    INVALID: ("invalid",),
    DEFENSE_IN_DEPTH: ("defense-in-depth", "wontfix"),
    INFO_ONLY: ("info-only",),
}
FROM_CLASS = {"INVALID": INVALID, "DEFENSE-IN-DEPTH": DEFENSE_IN_DEPTH, "INFO-ONLY": INFO_ONLY}
CANNED_DEFAULT = {
    INVALID: "the project's generic negative-assessment section, the team's reasoning filling its placeholder",
    DEFENSE_IN_DEPTH: (
        "the project's generic negative-assessment section, augmented to say the hardening is welcome "
        "as a public PR and is not a CVE"
    ),
    INFO_ONLY: "the canned-response heading the triage proposal named, verbatim",
}
TERMINAL = "none — terminal disposition."
NEXT = {
    INVALID: TERMINAL,
    DEFENSE_IN_DEPTH: "file the public hardening PR (normal-process work, no CVE).",
    INFO_ONLY: TERMINAL,
}


def normalise(value: object) -> str:
    """`value` as one of the three reasons (`DEFENSE-IN-DEPTH`, `defense in depth` → `defense-in-depth`).

    Empty means the default, `invalid`; anything else raises `ValueError`.
    """
    text = re.sub(r"[\s_]+", "-", str(value or "").strip().lower()).strip(".`")
    if not text:
        return INVALID
    if text not in REASONS:
        raise ValueError(f"{value!r} is not a close reason: one of {', '.join(REASONS)}")
    return text


def labels_for(reason: str, reason_labels: Any) -> list[str]:
    """The labels a close with `reason` adds: the `reason_labels` entry, else the default."""
    configured = reason_labels.get(reason) if isinstance(reason_labels, Mapping) else None
    if configured is None:
        return list(DEFAULT_LABELS[reason])
    if isinstance(configured, str):
        configured = [configured]
    names = [str(x).strip() for x in configured if str(x).strip()]
    if not names:
        raise ValueError(f"invalidate.reason_labels.{reason} is empty: a close must add at least one label")
    return names


def action_label(reason: str) -> str:
    return f"Closed as {reason}"
