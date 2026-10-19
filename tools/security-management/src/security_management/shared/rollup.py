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
"""Status-rollup entries the import skills append as a tracker's first entry.

The rollup tool (tools/github-rollup, through vetted-ops `rollup-append`)
writes the `<details>` envelope, so the entry body starts every line at
column 0 (leading spaces inside the envelope render as a code block), and the
action label can hold no `<`, `>` or `·`. Reporter-derived values are
flattened to one line and kept out of code-span breakage.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

from security_management.shared import refs
from security_management.shell import dq

FORBIDDEN_LABEL_CHARS = ("<", ">", "·")
NEXT_STEP = (
    "**Next:** Step 3 — start the validity / CVE-worthiness discussion; "
    "tag at least one other security-team member."
)
MALFORMED_NOTE = "Body markdown was malformed at import (unclosed `{indicator}`) — inlined verbatim, may need manual cleanup."


def one_line(value: object) -> str:
    """`value` on a single line, whitespace runs collapsed."""
    return re.sub(r"\s+", " ", "" if value is None else str(value)).strip()


def code(value: object) -> str:
    """`value` as an inline code span that a backquote in it cannot break."""
    return "`" + one_line(value).replace("`", "'") + "`"


def label_error(label: str) -> str | None:
    bad = [c for c in FORBIDDEN_LABEL_CHARS if c in label]
    if bad:
        return f"rollup action label {label!r} contains {' '.join(bad)}"
    if not label.strip() or "\n" in label:
        return "rollup action label must be one non-empty line"
    return None


def column_zero(text: str) -> str:
    return "\n".join(line.lstrip() for line in text.split("\n"))


def receipt_line(receipt: Mapping[str, Any]) -> str:
    """The *Receipt-of-confirmation reply* line for each Step 7 disposition."""
    draft = receipt.get("draft_id")
    if receipt.get("suppressed_reason"):
        return f"Receipt-of-confirmation reply: {one_line(receipt['suppressed_reason'])}."
    if receipt.get("converged"):
        where = one_line(receipt.get("converged_ref") or "the inbound thread")
        return (
            "Receipt-of-confirmation reply: skipped — the disposition converged on the inbound thread "
            f"({where}); a canned receipt would be tone-deaf."
        )
    if receipt.get("bundle_draft_id"):
        return (
            "Receipt-of-confirmation reply: covered by the consolidated receipt draft "
            f"{code(receipt['bundle_draft_id'])}."
        )
    if draft:
        return f"Receipt-of-confirmation reply: draft {code(draft)} waiting for user review in Gmail."
    return "Receipt-of-confirmation reply: no draft created (no draft backend available)."


def render_entry(
    *,
    headline: str,
    details: Sequence[str],
    tracker: str,
    next_step: str = NEXT_STEP,
) -> str:
    """A generic entry: bold headline, the next step, then one detail per line."""
    lines = [headline, "", next_step, ""]
    lines.extend(one_line(d) for d in details if one_line(d))
    return column_zero(refs.linkify("\n".join(lines), tracker)) + "\n"


def import_mail(data: Mapping[str, Any]) -> dict[str, Any]:
    """The `security-issue-import` entry: `{ok, label, label_shell, text}` or a refusal reason.

    `data`: tracker, thread_id, date, classification, reporter, mailbox (default
    Gmail), provenance, extracted_fields, receipt {draft_id | bundle_draft_id |
    converged + converged_ref | suppressed_reason}, malformed_indicator, notes[].
    """
    classification = one_line(data.get("classification") or "Report")
    reporter = one_line(data.get("reporter"))
    label = f"Import ({classification}, {reporter})"
    error = label_error(label)
    if error:
        return {"ok": False, "refused": error}
    mailbox = one_line(data.get("mailbox") or "Gmail")
    headline = (
        f"**Imported from {mailbox} thread {code(data.get('thread_id'))} on {one_line(data.get('date'))}** "
        f"(class: {code(classification)}, reporter: {code(reporter)})."
    )
    details = [
        f"Provenance: {one_line(data.get('provenance') or 'direct report')}.",
        f"Extracted fields: {one_line(data.get('extracted_fields') or 'see the body')}.",
        receipt_line(data.get("receipt") or {}),
    ]
    if data.get("malformed_indicator"):
        details.append(
            MALFORMED_NOTE.format(indicator=one_line(data["malformed_indicator"]).replace("`", "'"))
        )
    details.extend(str(n) for n in data.get("notes") or [])
    text = render_entry(headline=headline, details=details, tracker=str(data["tracker"]))
    return {"ok": True, "label": label, "label_shell": dq(label), "text": text}


KINDS = {"mail": import_mail}
