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
"""Step 4 item 5: whether the reporter gets a status draft, and how; the pre-draft body check.

`plan` reads the *Security mailing list thread* field (`shared.threads`) and
gives one of the rollup's *Reporter notification* cases:

- `omitted` — no external reporter: a PR-imported or internal-audit tracker;
- `team_member` — the named reporter is on the security team;
- `notified` — a message already sent on the thread told them;
- `draft_pending` — a draft waits on the thread (surfaced, never shadowed),
  or this run creates one (`create`, with the `<pending>` id amended in
  after the draft exists).

The draft fires in direct-reporter and via-forwarder mode alike (the
forwarder-routing policy leaves CVE allocation out), to the primary thread
the field records, `Re: <root subject>`, with `security_cc` in CC; a missing
CC, recipient or subject blocks it. An indeterminate field, or one whose every
thread is a relay, is the user's call.

`check` greps a composed body: it must carry the CVE ID and never the
CVE-tool URL (a reporter cannot open it), a `<tracker>` reference, a bare
`#NNN`, a CVSS score or another ASF project's name.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from security_management.shared import drafting, threads
from security_management.shared.rollup import one_line
from security_management.shared.titles import strip_mail_prefixes


def _out(
    action: str, case: str | None, why: str, note: Mapping[str, Any] | None = None, **extra: Any
) -> dict[str, Any]:
    return {"action": action, "notification": {"case": case, **(note or {})}, "reason": why, **extra}


def plan(data: Mapping[str, Any]) -> dict[str, Any]:
    thread = threads.classify(data.get("security_thread"))
    path = thread["import_path"]
    if path in ("pr_imported", "internal_audit"):
        return _out("skip", "omitted", f"{path.replace('_', '-')}: there is no external reporter to notify")
    if data.get("reporter_on_team"):
        return _out("skip", "team_member", "the reporter is on the security team")
    if path == "indeterminate":
        return _out(
            "ask", None, "the thread field names no thread: ask whether there is a reporter to notify"
        )
    if thread["needs_decision"]:
        return _out("ask", None, thread["needs_decision"], secondary_threads=thread["secondary_threads"])
    if data.get("already_notified"):
        return _out("skip", "notified", "a sent message on the thread already told the reporter")
    existing = [one_line(d) for d in data.get("existing_drafts") or [] if one_line(d)]
    if existing:
        return _out(
            "surface_existing",
            "draft_pending",
            "a draft already waits on the inbound thread: surface it instead of creating another",
            note={"draft_id": existing[0]},
        )
    cc = one_line(data.get("security_cc"))
    if not cc:
        return _out("blocked", None, "no security_cc resolved: draft creation is blocked")
    via = bool(data.get("via_forwarder"))
    to = one_line(data.get("forwarder_contact") if via else data.get("reporter_email"))
    if not to:
        return _out("blocked", None, "no recipient resolved")
    subject = one_line(data.get("root_subject"))
    if not subject:
        return _out("blocked", None, "the inbound root subject is needed: never a fresh subject")
    try:
        backend, note = drafting.backend(data)
    except ValueError as exc:
        return _out("blocked", None, str(exc))
    fields = {
        "thread_id": thread["thread_id"],
        "root_message_id": data.get("root_message_id") or thread["root_message_id"],
        "last_message_id": data.get("last_message_id"),
    }
    anchor = drafting.anchor(backend, fields)
    if not all(anchor.values()):
        return _out("blocked", None, f"{backend} needs {', '.join(anchor)} to attach to the inbound thread")
    return _out(
        "create",
        "draft_pending",
        "a status draft is owed on the inbound thread",
        note={"draft_id": "<pending>"},
        mode="via_forwarder" if via else "direct",
        to=to,
        cc=cc,
        subject=f"Re: {strip_mail_prefixes(subject)}",
        backend=backend,
        backend_note=note,
        anchor=anchor,
        secondary_threads=thread["secondary_threads"],
    )


def check(data: Mapping[str, Any]) -> dict[str, Any]:
    text = str(data.get("body") or "")
    hits = drafting.scan(text, str(data["tracker"]), data.get("own_names") or [])
    record = one_line(data.get("record_url"))
    if record and record in text and not any(h["kind"] == "cve-tool-url" for h in hits):
        hits.append({"kind": "cve-tool-url", "line": None, "text": record})
    cve_id = one_line(data.get("cve_id"))
    if not cve_id or cve_id not in text:
        hits.append({"kind": "missing-cve-id", "line": None, "text": cve_id or "<CVE-ID>"})
    return {"clean": not hits, "hits": hits}
