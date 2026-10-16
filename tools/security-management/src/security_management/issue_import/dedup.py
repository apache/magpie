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
"""Step 2: the batched `threadId` search against tracker bodies, and its attribution.

GitHub search allows at most five `OR` operators, so a query carries at most
six thread ids. A batch that returns exactly 100 hits (the `--limit`) may be
truncated: its unmatched ids are not reported as untracked but split into
smaller batches to re-run.

Identifiers follow the mail-source backends (tools/mail-source/contract.md,
`thread_id_kind`): a Gmail or PonyMail id, a maildir file name, or an
RFC-5322 root `Message-ID` such as `<report@example.org>` (IMAP, mbox). Each
goes into the query as a quoted search phrase, and `command` is the whole
`gh search issues` call shell-quoted. Any id outside those shapes makes the
result `ok: false`: the skill stops and shows it rather than search without it.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from security_management.shell import w

BATCH = 6
LIMIT = 100
# Gmail / PonyMail ids and maildir file names (`1700000000.M1P2.host,U=12:2,S`).
_OPAQUE_ID = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.,:=+-]{5,127}")
# An RFC-5322 Message-ID, angle brackets included: a conservative dot-atom on each side.
_MESSAGE_ID = re.compile(r"<[A-Za-z0-9!#%&'*+/=?^_{|}~.-]{1,128}@[A-Za-z0-9.-]{1,253}>")


def valid_ids(ids: Iterable[object]) -> tuple[list[str], list[str]]:
    good: list[str] = []
    bad: list[str] = []
    for raw in ids:
        text = str(raw).strip()
        if _OPAQUE_ID.fullmatch(text) or _MESSAGE_ID.fullmatch(text):
            if text not in good:
                good.append(text)
        else:
            bad.append(text)
    return good, bad


def _command(query: str, tracker: str | None) -> str | None:
    if not tracker:
        return None
    return (
        f"gh search issues {w(query)} --repo {w(tracker)} --match body --limit {LIMIT} "
        "--json number,title,state,url,body"
    )


def batches(ids: Sequence[str], size: int = BATCH, tracker: str | None = None) -> list[dict[str, Any]]:
    out = []
    for i in range(0, len(ids), size):
        chunk = list(ids[i : i + size])
        query = " OR ".join(f'"{t}"' for t in chunk)
        out.append({"ids": chunk, "query": query, "command": _command(query, tracker)})
    return out


def queries(ids: Iterable[object], tracker: str | None = None) -> dict[str, Any]:
    good, bad = valid_ids(ids)
    if bad:
        return {"ok": False, "refused": "thread ids no mail-source backend emits", "rejected_ids": bad}
    return {"ok": True, "batches": batches(good, tracker=tracker), "rejected_ids": []}


def attribute(thread_ids: Iterable[object], hits: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Which candidate each hit belongs to; `truncated` and `rerun` when the batch was full."""
    good, bad = valid_ids(thread_ids)
    if bad:
        return {"ok": False, "refused": "thread ids no mail-source backend emits", "rejected_ids": bad}
    tracked: dict[str, list[dict[str, Any]]] = {}
    for hit in hits:
        body = str(hit.get("body") or "")
        summary = {k: hit.get(k) for k in ("number", "title", "state", "url")}
        for tid in good:
            if tid in body:
                tracked.setdefault(tid, []).append(summary)
    truncated = len(hits) >= LIMIT
    unmatched = [t for t in good if t not in tracked]
    half = max(1, (len(unmatched) + 1) // 2)
    return {
        "ok": True,
        "tracked": tracked,
        "untracked": [] if truncated else unmatched,
        "truncated": truncated,
        "rerun": batches(unmatched, half) if truncated and unmatched else [],
        "rejected_ids": bad,
    }
