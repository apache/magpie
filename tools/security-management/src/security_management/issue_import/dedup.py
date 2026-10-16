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
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

BATCH = 6
LIMIT = 100
_THREAD_ID = re.compile(r"[A-Za-z0-9_-]{6,64}")


def valid_ids(ids: Iterable[object]) -> tuple[list[str], list[str]]:
    good: list[str] = []
    bad: list[str] = []
    for raw in ids:
        text = str(raw).strip()
        if _THREAD_ID.fullmatch(text):
            if text not in good:
                good.append(text)
        else:
            bad.append(text)
    return good, bad


def batches(ids: Sequence[str], size: int = BATCH) -> list[dict[str, Any]]:
    return [
        {"ids": list(ids[i : i + size]), "query": " OR ".join(ids[i : i + size])}
        for i in range(0, len(ids), size)
    ]


def queries(ids: Iterable[object]) -> dict[str, Any]:
    good, bad = valid_ids(ids)
    return {"batches": batches(good), "rejected_ids": bad}


def attribute(thread_ids: Iterable[object], hits: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Which candidate each hit belongs to; `truncated` and `rerun` when the batch was full."""
    good, bad = valid_ids(thread_ids)
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
        "tracked": tracked,
        "untracked": [] if truncated else unmatched,
        "truncated": truncated,
        "rerun": batches(unmatched, half) if truncated and unmatched else [],
        "rejected_ids": bad,
    }
