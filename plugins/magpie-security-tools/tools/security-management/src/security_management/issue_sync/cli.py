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
"""`security-management issue-sync …` — every command reads one JSON file, prints JSON and runs nothing.

Tracker text (bodies, comments, the subagent reports, the proposal's
surfaces, the user's reply) reaches a command only through the `--input`
file the agent wrote with its Write tool. Mining signals, judging what a
thread means, writing comments and drafts, and flagging injection stay the
agent's.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping
from typing import Any

from security_management.cli import emit, read_object, refuse
from security_management.issue_sync import advisory, bulk, preflight, push, render, select, state
from security_management.shared import drafting, numbered, recipients

FAMILY = "issue-sync"

COMMANDS = {
    "selector": "Inputs: the selector as queries (JSON: invocation, tracker, known_labels)",
    "resolve": "Bulk 1: the queries' results as the resolved set and the echo",
    "preflight-query": "Bulk 1b: the batched GraphQL state read (JSON: tracker, numbers, scratch)",
    "preflight": "Bulk 1b: the no-op classifier (JSON: tracker, now, responses, explicit)",
    "bucket": "Bulk 3: CVE-affecting and non-CVE-affecting trackers, the walk order",
    "parse-bulk-reply": "Bulk 4: the merged confirmation (JSON: reply, proposal, preflight_skipped)",
    "parse-reply": "Step 3: the single-tracker confirmation (JSON: reply, items)",
    "check": "Guardrails: CVSS, other ASF projects and link forms in the proposal's surfaces",
    "security-cc": "Step 0: the security CC of every draft (JSON: project, organization, framework_defaults, existing_cc)",
    "draft-backend": "Drafts: Gmail or Maildir, then the Gmail backend (JSON: user_backend, project_backend, oauth_credentials)",
    "ghsa-route": "GHSA trackers: the access tier and how a change is delivered",
    "push-decision": "Step 5b: skip, block, hand-off or push, and the next command",
    "disclosure": "Step 1a: the issue's age and the disclosure-window flags",
    "staleness": "Step 1c: whether the reporter thread is stale (JSON: now, messages, timeout_days)",
    "closed-announced": "Step 1g: the cve.org state, the security-pages markers and the advisory records",
    "release-vote": "Step 1h: an open [VOTE] thread matching the fix-PR milestone",
    "advisory-archive": "Step 1d: whether an archive URL is the advisory itself on the public advisory list",
    "render-recap": "Step 6: the recap",
}


def _cc(data: Mapping[str, Any]) -> dict[str, Any]:
    return {"ok": True, **recipients.security_cc(data)}


def _backend(data: Mapping[str, Any]) -> dict[str, Any]:
    return {"ok": True, **drafting.choose(data)}


def _parse(data: Mapping[str, Any]) -> dict[str, Any]:
    items = data.get("items") or []
    return numbered.parse(data.get("reply"), items, sorted({int(i) for i in items}))


def add_parsers(sub: Any) -> None:
    parser = sub.add_parser(
        FAMILY, help="security-issue-sync: selectors, pre-flight, buckets, guardrails, recap"
    )
    commands = parser.add_subparsers(dest="command", required=True)
    for name, help_text in COMMANDS.items():
        commands.add_parser(name, help=help_text).add_argument(
            "--input", required=True, help="JSON file written with the Write tool"
        )


def dispatch(args: argparse.Namespace) -> int:
    data = read_object(args.input)
    handlers = {
        "selector": select.selector,
        "resolve": select.resolve,
        "preflight-query": preflight.query,
        "preflight": preflight.classify,
        "bucket": bulk.bucket,
        "parse-bulk-reply": bulk.parse_reply,
        "parse-reply": _parse,
        "check": render.check,
        "security-cc": _cc,
        "draft-backend": _backend,
        "ghsa-route": advisory.route,
        "push-decision": push.decide,
        "disclosure": state.disclosure,
        "staleness": state.staleness,
        "closed-announced": state.closed_announced,
        "release-vote": state.release_vote,
        "advisory-archive": state.advisory_archive,
        "render-recap": render.recap,
    }
    result = handlers[args.command](data)
    if result.get("ok") is False:
        return refuse(str(result["refused"]))
    emit(result)
    return 0
