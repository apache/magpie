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
"""GHSA-sourced trackers: the operator's access tier and how each advisory change is delivered.

The tier comes from the one list call of the run (and a single-advisory
GET): a member of the security-manager team is `admin`; an advisory the
list or the GET returns makes the operator a `collaborator`; otherwise
`not-collaborator`. A `403` on an admin-only PATCH is the definitive *not
admin* signal: never retried.

- `field_edit` (link `cve_id`, mirror severity / CWE / ranges / credits):
  the sync writes it at either tier, after confirmation; without access it
  is a relay draft.
- `collaborators`, `state` (publish / close): an admin writes them; a
  collaborator (or anyone after a `403`) hands them off — a **draft** to
  `<foundation-security-list>` through `mcp__gmail-plaintext__create_draft`
  (never the claude.ai connector, which rewrites the advisory links), on
  the originating `<security-list>` thread when there is one, in three
  parts, recorded with the `ghsa-admin-handoff` rollup marker; never a
  tracker comment @-mentioning anyone.
- `reporter_reply`: the advisory discussion has no API, so a collaborator
  opens the advisory and pastes the printed reply (nothing is claimed as
  posted); without access it falls back to the email relay.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

KINDS = ("field_edit", "collaborators", "state", "reporter_reply")
HANDOFF_PARTS = ["already-done", "admin-only-change-and-why", "ask"]


def tier(data: Mapping[str, Any]) -> str:
    if data.get("security_manager"):
        return "admin"
    if data.get("in_list") or int(data.get("advisory_get_status") or 0) == 200:
        return "collaborator"
    return "not-collaborator"


def route(data: Mapping[str, Any]) -> dict[str, Any]:
    kind = str(data.get("change") or "")
    if kind not in KINDS:
        return {"ok": False, "refused": f"change must be one of {', '.join(KINDS)}"}
    level = tier(data)
    got_403 = bool(data.get("got_403"))
    if got_403 and level == "admin":
        level = "collaborator"  # the 403 is the definitive not-admin signal
    out: dict[str, Any] = {
        "ok": True,
        "access_tier": level,
        "mail_tool": None,
        "recipient": None,
        "auto_send": False,
        "reply_on_security_thread": None,
        "retry_after_403": False,
        "posts_tracker_comment": False,
        "rollup_handoff_marker": False,
        "relay_parts": [],
        "claims_reply_posted": False,
        "requires_confirmation": True,
        "open_url": None,
    }

    def relay(why: str) -> dict[str, Any]:
        return {**out, "action": "relay-draft", "channel": "email-draft", "rationale": why}

    if kind == "reporter_reply":
        if level == "not-collaborator":
            return relay("not a collaborator on the advisory: fall back to the email relay, as a draft")
        return {
            **out,
            "action": "browser-paste",
            "channel": "advisory-web-ui",
            "requires_confirmation": None,
            "open_url": data.get("html_url"),
            "rationale": "the advisory discussion has no API: open the advisory and paste the printed reply",
        }
    if kind == "field_edit":
        if level == "not-collaborator":
            return relay(
                "no access to the advisory: relay the field change through the foundation security team"
            )
        return {
            **out,
            "action": "direct-write",
            "channel": "advisory-api",
            "rationale": "field edits are collaborator-tier: the sync PATCHes the advisory after confirmation",
        }
    if level == "admin":
        return {
            **out,
            "action": "direct-write",
            "channel": "advisory-api",
            "rationale": f"{kind} needs the admin / security-manager tier, which the operator holds",
        }
    thread = data.get("security_thread_id")
    return {
        **out,
        "action": "relay-draft",
        "channel": "email-draft",
        "mail_tool": "gmail-plaintext-mcp",
        "recipient": "<foundation-security-list>",
        "reply_on_security_thread": bool(thread),
        "thread_id": thread or None,
        "rollup_handoff_marker": True,
        "relay_parts": list(HANDOFF_PARTS),
        "rationale": f"{kind} is admin-only"
        + (" and the PATCH returned 403 (not retried)" if got_403 else "")
        + ": hand it off as a draft to the advisory-admin team, never as a tracker comment",
    }
