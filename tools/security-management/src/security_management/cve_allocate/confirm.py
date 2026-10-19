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
"""Step 5: the confirmation reply. Nothing applies by default.

- `all` / `go` / `proceed` / `yes` — `apply` every proposed item;
- `1,3,4` (commas, spaces or `and`) — `apply` those items only;
- `none` / `cancel` — `cancel`;
- any other text — `edit`: the agent regenerates the affected items and
  asks again; nothing applies.

A go word applies only as the whole reply, so `don't go` is an edit, not a
yes. No reply, or a number the proposal does not carry, is `ambiguous`:
nothing applies. `items_skipped` holds every one of the
five canonical items that will not run, proposed or not.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

CANONICAL = (1, 2, 3, 4, 5)
_GO = frozenset({"all", "go", "proceed", "yes", "y", "ok", "okay"})
_CANCEL = frozenset({"none", "cancel", "abort"})
# Separators that cannot overlap (a comma, `and`, or whitespace alone), so matching stays linear.
_LIST = re.compile(r"^#?\d+(?:(?:\s*,\s*|\s+and\s+|\s+)#?\d+)*$", re.IGNORECASE)


def parse(data: Mapping[str, Any]) -> dict[str, Any]:
    reply = str(data.get("reply") or "").strip()
    proposed = sorted({int(n) for n in data.get("items") or []})

    def out(action: str, applied: list[int], why: str, edit: str | None = None) -> dict[str, Any]:
        skipped = [n for n in CANONICAL if n not in applied] if action == "apply" else []
        return {
            "action": action,
            "items_applied": applied,
            "items_skipped": skipped,
            "edit": edit,
            "rationale": why,
        }

    word = reply.lower().rstrip(".!")
    if not proposed:
        return out("ambiguous", [], "no proposed items were passed")
    if word in _GO:
        return out("apply", proposed, f"`{word}` applies every proposed item")
    if word in _CANCEL:
        return out("cancel", [], "nothing is applied; the tracker stays as it is")
    if _LIST.match(word):
        chosen = sorted({int(n) for n in re.findall(r"\d+", word)})
        unknown = [n for n in chosen if n not in proposed]
        if unknown:
            return out(
                "ambiguous", [], f"item(s) {', '.join(map(str, unknown))} are not in the proposal; ask again"
            )
        return out("apply", chosen, "the user picked these items")
    if not reply:
        return out("ambiguous", [], "no reply: nothing applies; ask again")
    return out("edit", [], "free-form edits: regenerate the affected items and confirm again", edit=reply)
