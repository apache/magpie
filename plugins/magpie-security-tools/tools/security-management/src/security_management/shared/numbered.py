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
"""The numbered-proposal confirmation reply of the tracker-update skills. Nothing applies by default.

- `all` / `go` / `proceed` / `yes` — `apply` every proposed item;
- `1,3,4` (commas, spaces or `and`) — `apply` those items only, also when a
  dash, colon or semicolon puts a comment after the list (`1,2 — skip 3 for
  now`), as long as the comment names no listed item and names others only
  to hold them back (`skip`, `not`, `except`, `without`, `hold`, `leave out`);
- `none` / `cancel` — `cancel`;
- any other text — `edit`: the agent regenerates the affected items and
  asks again; nothing applies.

A go word applies only as the whole reply, so `don't go` is an edit, not a
yes. No reply, or a number the proposal does not carry, is `ambiguous`:
nothing applies. `items_skipped` holds every canonical item that will not
run, proposed or not.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from typing import Any

_GO = frozenset({"all", "go", "proceed", "yes", "y", "ok", "okay"})
_CANCEL = frozenset({"none", "cancel", "abort"})
# Separators that cannot overlap (a comma, `and`, or whitespace alone), so matching stays linear.
_LIST_BODY = r"#?\d+(?:(?:\s*,\s*|\s+and\s+|\s+)#?\d+)*"
_LIST = re.compile(rf"^{_LIST_BODY}$", re.IGNORECASE)
_LIST_THEN_NOTE = re.compile(
    rf"^(?P<list>{_LIST_BODY})\s*(?:[\u2014\u2013:;]|\s-)\s*(?P<note>\S.*)$", re.IGNORECASE | re.DOTALL
)
# A comment may name other items only to hold them back.
_HOLD = re.compile(r"^(?:but\s+)?(?:skip|not|except|without|hold(?:\s+off)?(?:\s+on)?|leave(?:\s+out)?)\b")


def parse(reply: object, items: Iterable[object], canonical: Sequence[int]) -> dict[str, Any]:
    text = str(reply or "").strip()
    proposed = sorted({int(str(n)) for n in items})

    def out(action: str, applied: list[int], why: str, edit: str | None = None) -> dict[str, Any]:
        skipped = [n for n in canonical if n not in applied] if action == "apply" else []
        return {
            "action": action,
            "items_applied": applied,
            "items_skipped": skipped,
            "edit": edit,
            "rationale": why,
        }

    word = text.lower().rstrip(".!")
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
    noted = _LIST_THEN_NOTE.match(word)
    if noted:
        chosen = sorted({int(n) for n in re.findall(r"\d+", noted.group("list"))})
        named = {int(n) for n in re.findall(r"\d+", noted.group("note"))}
        unknown = [n for n in [*chosen, *sorted(named)] if n not in proposed]
        if unknown or named & set(chosen) or (named and not _HOLD.match(noted.group("note"))):
            return out(
                "ambiguous", [], "the comment after the list names a listed or unknown item; ask again"
            )
        result = out("apply", chosen, "the user picked these items")
        result["note"] = text[noted.start("note") :].strip()
        return result
    if not text:
        return out("ambiguous", [], "no reply: nothing applies; ask again")
    return out("edit", [], "free-form edits: regenerate the affected items and confirm again", edit=text)
