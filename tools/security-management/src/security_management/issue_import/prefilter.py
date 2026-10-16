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
"""The Step 1 pre-filter: classes decidable from the subject and the sender alone.

Rules, first match wins, applied to every message of a thread:

1. Subject carries a `GHSA-` token, sender is `notifications@github.com`, and
   the subject begins with `[<upstream>]` → keep, pre-tagged `ghsa-relay`.
2. Sender is `<security-list>` (or a configured CVE-tool sender) and the whole
   subject is one of the CVE-tool bookkeeping shapes, `CVE-\\d{4}-\\d{4,7}`,
   no `Re:` / `Fwd:` / other prefix → drop as `cve-tool-bookkeeping`.
3. Anything else → keep; Steps 2 to 3 decide.

A thread is dropped only when every message the search result lists matches
rule 2; a message with no subject or no sender keeps the thread; an
explicitly named thread (`import thread:<id>`) is never dropped. Bodies are
never read here: the body-line bookkeeping variant stays with Step 3.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from email.utils import parseaddr
from typing import Any

CVE = r"CVE-\d{4}-\d{4,7}"
BOOKKEEPING_SUBJECTS = tuple(
    re.compile(p)
    for p in (
        rf"{CVE} reserved for .+",
        rf"Comment added on {CVE}",
        rf"{CVE} is now READY",
        rf"{CVE} is now PUBLIC",
        rf"{CVE} is now PUBLISHED",
        rf"{CVE} REJECTED",
    )
)
GHSA_SENDER = "notifications@github.com"
_GHSA = re.compile(r"\bGHSA-[0-9a-z]{4}-", re.IGNORECASE)


def address(sender: str) -> str:
    return parseaddr(sender)[1].strip().lower()


def message_rule(
    subject: str | None,
    sender: str | None,
    *,
    upstream: str,
    bookkeeping_senders: Iterable[str],
) -> int:
    if not subject or not sender:
        return 3
    addr = address(sender)
    if addr == GHSA_SENDER and _GHSA.search(subject) and subject.lstrip().startswith(f"[{upstream}]"):
        return 1
    if addr in {s.lower() for s in bookkeeping_senders} and any(
        p.fullmatch(subject.strip()) for p in BOOKKEEPING_SUBJECTS
    ):
        return 2
    return 3


def classify(data: Mapping[str, Any]) -> dict[str, Any]:
    """`data`: upstream, security_list, cve_tool_senders[], named_thread_id, threads[]."""
    upstream = str(data["upstream"])
    senders = [str(data["security_list"]), *(str(s) for s in data.get("cve_tool_senders") or [])]
    named = data.get("named_thread_id")
    out: list[dict[str, Any]] = []
    for thread in data.get("threads") or []:
        messages = thread.get("messages") or []
        rules = [
            message_rule(m.get("subject"), m.get("from"), upstream=upstream, bookkeeping_senders=senders)
            for m in messages
        ]
        rule = rules[0] if rules and all(r == rules[0] for r in rules) else 3
        root = messages[0] if messages else {}
        entry: dict[str, Any] = {
            "thread_id": thread.get("thread_id"),
            "subject": root.get("subject"),
            "sender": root.get("from"),
            "rule": rule,
            "decision": "drop" if rule == 2 else "keep",
            "class": "cve-tool-bookkeeping" if rule == 2 else None,
            "pretag": "ghsa-relay" if rule == 1 else None,
        }
        if named is not None and thread.get("thread_id") == named:
            entry["named"] = True
            entry["decision"] = "keep"
        out.append(entry)
    dropped = [t for t in out if t["decision"] == "drop"]
    return {
        "threads": out,
        "keep": [t["thread_id"] for t in out if t["decision"] == "keep"],
        "dropped": dropped,
        "counts": {"cve-tool-bookkeeping": len(dropped)},
    }
