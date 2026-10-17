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
"""Step 3: the parent-side pre-screen before invoking `security-issue-import-via-forwarder`.

Detection is an OR of two signals per enabled adapter: `sender_pattern`
against the root `From:` address, `preamble_match` against the first 400
characters of the root body. When neither matches for any enabled adapter the
candidate is not a relay and the sub-skill is not invoked. Any match, or an
adapter whose patterns cannot be resolved or compiled, invokes it: the
sub-skill's own Step 1 stays the authority. The patterns come from
`project.md → forwarders.<adapter>` (else the adapter's defaults), passed in;
none are hard-coded here.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from security_management.issue_import.prefilter import address

PREAMBLE_CHARS = 400


def prescreen(message: Mapping[str, Any], forwarders: Mapping[str, Any]) -> dict[str, Any]:
    enabled = [str(a) for a in forwarders.get("enabled") or []]
    if not enabled:
        return {"invoke_subskill": False, "reason": "forwarders.enabled is empty", "adapters": []}
    sender = address(str(message.get("from") or ""))
    preamble = str(message.get("body") or "")[:PREAMBLE_CHARS]
    adapters: list[dict[str, Any]] = []
    for name in enabled:
        config = forwarders.get(name) or {}
        sender_pattern = config.get("sender_pattern")
        preamble_pattern = config.get("preamble_match")
        if not sender_pattern or not preamble_pattern:
            adapters.append({"adapter": name, "match": None, "reason": "patterns unresolved"})
            continue
        try:
            by_sender = bool(re.search(str(sender_pattern), sender, re.IGNORECASE))
            by_preamble = bool(re.search(str(preamble_pattern), preamble))
        except re.error as exc:
            adapters.append({"adapter": name, "match": None, "reason": f"pattern does not compile: {exc}"})
            continue
        adapters.append(
            {"adapter": name, "match": by_sender or by_preamble, "sender": by_sender, "preamble": by_preamble}
        )
    invoke = any(a["match"] is not False for a in adapters)
    return {
        "invoke_subskill": invoke,
        "reason": "a signal matched or an adapter is unresolved" if invoke else "no signal matched",
        "adapters": adapters,
    }
