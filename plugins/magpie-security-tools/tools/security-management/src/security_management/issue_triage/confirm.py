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
"""The Step 5 confirmation grammar. Nothing posts by default: the user names what posts.

- `all` — every proposal; `1,3,5` — the listed items;
- `N:skip` — drop item N; `N:edit <freeform>` — re-draft item N
  (the argument runs to the next directive);
- `N:downgrade <CLASS>` / `N:upgrade <CLASS>` — re-classify item N to one
  of the six classes;
- `force-triage <tracker>` — pull a pre-flight-skipped tracker back in;
- `none` / `cancel` — post nothing.

`post_items` is every item selected (by `all` or by number) and not
skipped; items with an edit or a re-classification are in `redraft_items`,
so `post_now` is what posts this turn and the re-drafted ones are shown
again. Anything the grammar cannot place (free text, an unknown item, a
skip with no `all` or number list, an item both listed and skipped, a
negation) makes the action `ambiguous`: nothing posts, and the agent asks
about `ambiguous_tokens` / `ambiguous_items`.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

from security_management.shared import dispositions

_DIRECTIVE = re.compile(
    r"#?(?P<item>\d+)\s*:\s*(?P<verb>skip|edit|downgrade|upgrade)\b:?|\bforce-triage\s+#?(?P<forced>\d+)",
    re.IGNORECASE,
)
_NEGATION = re.compile(r"\b(?:not|no|never|don'?t|stop|wait|hold)\b|n't\b", re.IGNORECASE)
_CANCEL = frozenset({"none", "cancel"})


def _empty(action: str, ambiguous: list[str], held: list[int]) -> dict[str, Any]:
    return {
        "action": action,
        "post_items": [],
        "post_now": [],
        "skip_items": [],
        "edits": [],
        "reclassifications": [],
        "redraft_items": [],
        "force_triage": [],
        "ambiguous_tokens": ambiguous,
        "ambiguous_items": held,
    }


def parse(text: str, items: Sequence[int], skipped_trackers: Sequence[int] = ()) -> dict[str, Any]:
    known = {int(i) for i in items}
    forced_ok = {int(n) for n in skipped_trackers}
    free: list[str] = []
    skips: list[int] = []
    edits: list[dict[str, Any]] = []
    reclass: dict[int, set[str]] = {}
    forced: list[int] = []
    ambiguous: list[str] = []
    held: set[int] = set()

    matches = list(_DIRECTIVE.finditer(text))
    free.append(text[: matches[0].start()] if matches else text)
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        arg = text[match.end() : end].strip().strip(",").strip()
        token = text[match.start() : end].strip()
        if match.group("forced"):
            number = int(match.group("forced"))
            if number in forced_ok:
                forced.append(number)
            else:
                ambiguous.append(token)
            free.append(arg)
            continue
        item = int(match.group("item"))
        verb = match.group("verb").lower()
        if item not in known:
            ambiguous.append(token)
            continue
        if verb == "skip":
            skips.append(item)
            free.append(arg)
        elif verb == "edit":
            if not arg:
                ambiguous.append(token)
                held.add(item)
            else:
                edits.append({"item": item, "instruction": arg})
        else:
            words = arg.split(maxsplit=1)
            new_class = dispositions.normalise_class(words[0]) if words else None
            if new_class is None:
                ambiguous.append(token)
                held.add(item)
                continue
            reclass.setdefault(item, set()).add(new_class)
            free.append(words[1] if len(words) > 1 else "")

    select_all = False
    listed: list[int] = []
    cancel = False
    for chunk in free:
        if _NEGATION.search(chunk):
            ambiguous.append(chunk.strip())
            continue
        for word in [t for t in re.split(r"[\s,]+", chunk.strip()) if t]:
            low = word.lower().rstrip(".")
            if low == "all":
                select_all = True
            elif low in _CANCEL:
                cancel = True
            elif re.fullmatch(r"#?\d+", word):
                number = int(word.lstrip("#"))
                if number in known:
                    listed.append(number)
                else:
                    ambiguous.append(word)
            else:
                ambiguous.append(word)
    if cancel:
        return _empty("cancel", [], [])
    for item, classes in reclass.items():
        if len(classes) > 1:
            ambiguous.append(f"conflicting re-classifications for item {item}")
            held.add(item)
    both = sorted(set(listed) & set(skips))
    for item in both:
        ambiguous.append(f"item {item} is both listed and skipped")
        held.add(item)
    if not select_all and not listed and not forced and (skips or edits or reclass):
        ambiguous.append("no items selected to post: say `all` or list the items")
    if ambiguous:
        return _empty("ambiguous", ambiguous, sorted(held))
    selected = sorted(known) if select_all else sorted(set(listed))
    post = [i for i in selected if i not in skips]
    redraft = sorted({e["item"] for e in edits} | set(reclass))
    return {
        "action": "post" if post or forced else "ambiguous",
        "post_items": post,
        "post_now": [i for i in post if i not in redraft],
        "skip_items": sorted(set(skips)),
        "edits": edits,
        "reclassifications": [{"item": i, "new_class": next(iter(c))} for i, c in sorted(reclass.items())],
        "redraft_items": redraft,
        "force_triage": forced,
        "ambiguous_tokens": [] if post or forced else ["nothing selected to post"],
        "ambiguous_items": [],
    }


def parse_input(data: Mapping[str, Any]) -> dict[str, Any]:
    return parse(str(data.get("reply") or ""), data.get("items") or [], data.get("skipped_trackers") or [])
