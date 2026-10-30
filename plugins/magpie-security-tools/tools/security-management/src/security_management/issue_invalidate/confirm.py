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
"""The Step 5f confirmation forms. Unlike the importers, nothing applies by default.

- `go` / `proceed` / `yes` (and `all` in bulk) — `apply`;
- `email: <freeform>` — `replace_email_body` (only when a draft is proposed);
- `canned: <section name>` — `repick_canned`;
- `silent` — `apply_silent`: close, skip the draft, say why in the rollup;
- `cancel` / `none` — `cancel`.

Anything else, a negation, or two forms at once is `ambiguous`: nothing
applies and the agent asks again.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

_GO = frozenset({"go", "proceed", "yes", "all"})
_CANCEL = frozenset({"cancel", "none"})
_NEGATION = re.compile(r"\b(?:not|no|never|don'?t|stop|wait|hold)\b|n't\b", re.IGNORECASE)


def _out(action: str, why: str, email: str | None = None, canned: str | None = None) -> dict[str, Any]:
    return {
        "action": action,
        "email_body_override": email,
        "canned_section_override": canned,
        "rationale": why,
    }


def parse(data: Mapping[str, Any]) -> dict[str, Any]:
    reply = str(data.get("reply") or "").strip()
    draft_proposed = bool(data.get("draft_proposed", True))
    form = re.match(r"^(email|canned)\s*:\s*(.+)$", reply, re.IGNORECASE | re.DOTALL)
    if form:
        kind, arg = form.group(1).lower(), form.group(2).strip()
        if kind == "email":
            if not draft_proposed:
                return _out(
                    "ambiguous",
                    "no email draft is proposed for this tracker; `email:` has nothing to replace",
                )
            return _out("replace_email_body", "the user supplied the email body", email=arg)
        return _out("repick_canned", "the user named the canned section to use", canned=arg)
    word = reply.lower().rstrip(".!")
    if word in _GO and not _NEGATION.search(reply):
        return _out("apply", f"`{word}` applies the proposal as shown")
    if word == "silent":
        return _out("apply_silent", "close and skip the email draft; the rollup records why")
    if word in _CANCEL:
        return _out("cancel", "nothing is applied; the tracker stays as it is")
    return _out("ambiguous", "the reply is none of the confirmation forms; ask again")
