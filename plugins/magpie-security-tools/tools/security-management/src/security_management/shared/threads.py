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
"""What the *Security mailing list thread* field says about where a tracker came from.

The importers write one of a few shapes (`issue-import`'s Gmail-only line and
archive URL, `-from-pr`'s, `-from-md`'s and `-from-scan`'s `N/A — …` sentinels), and
`security-issue-deduplicate` or a later relay appends further lines. The
primary reporter thread is the line with no forwarder or relay signal, per
`tools/gmail/threading.md` § *Selecting the inbound thread when multiple are
recorded*; a field whose every line carries one, with more than one line, is
left for the user to decide.
"""

from __future__ import annotations

import re
from typing import Any

from generate_cve_json.cve_json import MD_SENTINEL, NO_THREAD_PREFIX, PR_SENTINEL, SCAN_SENTINEL

GMAIL_SENTINEL = "No public archive URL — tracked privately on Gmail thread"

_THREAD_ID = re.compile(r"Gmail thread\s+`?([A-Za-z0-9_-]{6,})`?", re.IGNORECASE)
_URL = re.compile(r"https?://[^\s)`>\]]+")
_ROOT = re.compile(r"^Root Message-ID:\s*`?(<[^`]+>|[^`\s]+)`?\s*$", re.IGNORECASE)
_RELAY = re.compile(
    r"\bvia\s+(?:huntr(?:\.com)?|ghsa|hackerone|bugcrowd)\b|asf[- ]relayed|asf[- ]security[- ]relay|"
    r"relayed by|forward(?:er|ed by)|\brelay(?:ed)?\b|-class duplicate",
    re.IGNORECASE,
)

EMAIL_STEP = {
    "security_at_imported_public": "required",
    "security_at_imported_gmail_only": "required",
    "pr_imported": "skip",
    "internal_audit": "skip",
    "indeterminate": "surface_to_user",
}


def _line(text: str) -> dict[str, Any]:
    thread = _THREAD_ID.search(text)
    url = _URL.search(text)
    annotation = _THREAD_ID.sub("", text)
    return {
        "text": text,
        "thread_id": thread.group(1) if thread else None,
        "url": url.group(0) if url else None,
        "relay": bool(_RELAY.search(annotation)),
    }


def classify(value: str | None) -> dict[str, Any]:
    """`{import_path, email_draft_step, thread_id, archive_url, root_message_id, secondary_threads, needs_decision}`."""
    raw = [ln.strip() for ln in (value or "").replace("\r\n", "\n").split("\n")]
    root = next((m.group(1) for ln in raw if (m := _ROOT.match(ln))), None)
    lines = [_line(ln) for ln in raw if ln and not _ROOT.match(ln)]
    out: dict[str, Any] = {
        "thread_id": None,
        "archive_url": None,
        "root_message_id": root,
        "secondary_threads": [],
        "needs_decision": None,
    }

    def done(path: str, why: str) -> dict[str, Any]:
        return {"import_path": path, "email_draft_step": EMAIL_STEP[path], "rationale": why, **out}

    if not lines:
        return done("indeterminate", "the field is empty or `_No response_`")
    if lines[0]["text"].startswith(PR_SENTINEL):
        return done("pr_imported", "the field holds the import-from-pr sentinel: there is no reporter")
    if lines[0]["text"].startswith(MD_SENTINEL):
        return done(
            "internal_audit", "the field holds the import-from-md sentinel: an internal audit finding"
        )
    if lines[0]["text"].startswith(SCAN_SENTINEL):
        return done(
            "internal_audit", "the field holds the import-from-scan sentinel: an internal scan finding"
        )
    if lines[0]["text"].startswith(NO_THREAD_PREFIX):
        return done(
            "internal_audit", "the field starts with `N/A —`: no reporter thread, an internal finding"
        )
    threads = [ln for ln in lines if ln["thread_id"] or ln["url"]]
    if not threads:
        return done("indeterminate", "the field names no thread and no URL")
    primaries = [ln for ln in threads if not ln["relay"]]
    if not primaries and len(threads) > 1:
        out["needs_decision"] = (
            "every recorded thread carries a relay signal; ask which one the reply goes to"
        )
        primary = threads[0]
    else:
        primary = primaries[0] if primaries else threads[0]
    out["thread_id"] = primary["thread_id"]
    out["archive_url"] = primary["url"]
    out["secondary_threads"] = [
        {"thread_id": ln["thread_id"], "url": ln["url"], "relay": ln["relay"]}
        for ln in threads
        if ln is not primary
    ]
    if primary["text"].startswith(GMAIL_SENTINEL) or (primary["thread_id"] and not primary["url"]):
        return done("security_at_imported_gmail_only", "the primary line names a private Gmail thread")
    return done("security_at_imported_public", "the primary line carries an archive URL")
