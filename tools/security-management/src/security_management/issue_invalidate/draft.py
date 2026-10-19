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
"""Step 5d: whether a reporter draft is owed, to whom and how, and the pre-draft body check.

`plan` maps the import path and the reporter channel onto one of the
*Reporter notification* cases of the Step 5e rollup entry, and for a draft
the recipients (reporter, or the forwarder contact in via-forwarder mode),
the `security_cc` copy, the `Re: <root subject>` subject, the inbound-thread
anchor per backend, and the backend (`oauth_curl` preferred; the discouraged
`claude_ai_mcp` only without credentials and with no link in the body). A
pending draft on the thread is surfaced, never shadowed; a missing
`security_cc` blocks drafting.

`check` greps a composed body before it is drafted: any `<tracker>`
reference (the reporter cannot open it), the CVE-tool URL, a bare `#NNN`, a
re-opening phrase, a CVSS score, a missing canonical CVE for a duplicate,
and the AGENTS.md list of other ASF project names. Writing the body (the
canned spine and its augmentation) stays the agent's job.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from security_management.shared import drafting
from security_management.shared.rollup import one_line
from security_management.shared.titles import strip_mail_prefixes

_CVE = re.compile(r"CVE-\d{4}-\d{4,7}")


def _skip(case: str, why: str) -> dict[str, Any]:
    return {"action": "skip", "notification_case": case, "reason": why}


def plan(data: Mapping[str, Any]) -> dict[str, Any]:
    path = str(data["import_path"])
    if data.get("silent"):
        return _skip("silent", "the user chose `silent`; the rollup notes why")
    if path == "pr_imported":
        return _skip("pr_imported", "PR-imported: no reporter to notify, and no outreach to the PR author")
    if path == "internal_audit":
        return _skip("internal_audit", "internal audit finding: no inbound security@ thread, no reporter")
    if path == "indeterminate":
        return {
            "action": "ask",
            "notification_case": None,
            "reason": "indeterminate import path: ask whether there is a thread to reply on, or a silent close",
        }
    ghsa = data.get("ghsa") or {}
    if ghsa.get("only_channel"):
        if ghsa.get("write_access"):
            return _skip(
                "ghsa_comment", "GHSA-relay-only with GHSA write access: close on the advisory itself"
            )
        if not data.get("forwarder_contact"):
            return {
                "action": "ask",
                "notification_case": None,
                "reason": "GHSA-relay-only without write access needs a forwarder contact",
            }
    existing = [d for d in data.get("existing_drafts") or [] if d]
    if existing:
        return {
            "action": "surface_existing",
            "notification_case": None,
            "existing_draft": existing[0],
            "reason": "a draft already waits on the inbound thread: surface it instead of shadowing it",
        }
    cc = one_line(data.get("security_cc"))
    if not cc:
        return {
            "action": "blocked",
            "notification_case": None,
            "reason": "no security_cc resolved: draft creation is blocked",
        }
    via = bool(data.get("via_forwarder")) or bool(ghsa.get("only_channel"))
    to = one_line(data.get("forwarder_contact") if via else data.get("reporter_email"))
    if not to:
        return {"action": "blocked", "notification_case": None, "reason": "no recipient resolved"}
    subject = one_line(data.get("root_subject"))
    if not subject:
        return {
            "action": "blocked",
            "notification_case": None,
            "reason": "the inbound root subject is needed: never a fresh subject",
        }
    backend, backend_note = drafting.backend(data)
    anchor = drafting.anchor(backend, data)
    if not all(anchor.values()):
        return {
            "action": "blocked",
            "notification_case": None,
            "reason": f"{backend} needs {', '.join(anchor)} to attach to the inbound thread",
        }
    case = "ghsa_forwarder" if ghsa.get("only_channel") else "via_forwarder" if via else "direct"
    if str(data.get("disposition") or "invalid") == "duplicate":
        case += "_duplicate"
    return {
        "action": "create",
        "notification_case": case,
        "to": to,
        "cc": cc,
        "subject": f"Re: {strip_mail_prefixes(subject)}",
        "backend": backend,
        "backend_note": backend_note,
        "anchor": anchor,
        "reason": None,
    }


def check(data: Mapping[str, Any]) -> dict[str, Any]:
    text = str(data.get("body") or "")
    tracker = str(data["tracker"])
    hits = drafting.scan(text, tracker, data.get("own_names") or [])
    if str(data.get("disposition") or "invalid") == "duplicate":
        canonical = one_line(data.get("canonical_cve"))
        if not canonical or canonical not in _CVE.findall(text):
            hits.append({"kind": "missing-canonical-cve", "line": None, "text": canonical or "<CVE-ID>"})
    return {"clean": not hits, "hits": hits}
