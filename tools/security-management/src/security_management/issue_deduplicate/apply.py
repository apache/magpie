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
"""Step 5: the confirmed items as commands, in order, one at a time.

1 the merged body (the one load-bearing write), 2 and 3 each side's legacy
folds oldest first and then its rollup entry, 4 the `duplicate` label, 5 the
close (`not planned`: GitHub's duplicate reason is not exposed on every `gh`),
6 the kept side's CVE JSON (and `push_update` with no state transition when
it has a CVE), 7 the governance-gated retraction of the dropped side's CVE.
A plan with an open blocker is refused, and the close re-checks the sides:
the kept tracker stays open.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from security_management.issue_deduplicate.gate import DUPLICATE
from security_management.issue_deduplicate.render import labels
from security_management.shared import selectors
from security_management.shared.rollup import one_line
from security_management.shell import dq, w

CALLER = "--caller security-issue-deduplicate"
TRACKER_OP = f"uv run --project ~/.claude/magpie/vetted-ops vetted-op-tracker {CALLER}"
READ_OP = f"uv run --project ~/.claude/magpie/vetted-ops vetted-op-read {CALLER}"
WRITE_OP = f"uv run --project ~/.claude/magpie/vetted-ops vetted-op {CALLER}"


def plan(data: Mapping[str, Any]) -> dict[str, Any]:
    if data.get("blockers"):
        return {"ok": False, "refused": "the merge has an open blocker: resolve it before applying anything"}
    tracker = str(data["tracker"])
    platform = str(data.get("platform") or "github")
    github = platform == "github"
    keep, drop = data["keep"]["number"], data["drop"]["number"]
    if str(keep) == str(drop):
        return {"ok": False, "refused": "the kept and dropped trackers are the same"}

    def ref(value: object) -> str:
        return str(int(str(value))) if github else w(str(value))

    k, d = ref(keep), ref(drop)
    chosen = {int(n) for n in data.get("items") or []}
    scratch = str(data["scratch"]).rstrip("/")
    slug_k, slug_d = str(keep).replace("/", "-"), str(drop).replace("/", "-")
    kept_label, dropped_label = labels(data)
    duplicate = str(data.get("duplicate_label") or DUPLICATE)
    generator = w(str(data.get("generator") or "<framework>/tools/cve-tool-vulnogram/generate-cve-json"))
    body_file = f"{scratch}/dedupe-{slug_k}-body.md"
    steps: list[dict[str, Any]] = []
    if 1 in chosen:
        command = (
            f"gh issue edit {k} --repo {w(tracker)} --body-file {w(body_file)}"
            if github
            else f"{WRITE_OP} issue-edit-body {k} {w(body_file)}"
        )
        steps.append({"item": 1, "write": body_file, "command": command, "load_bearing": True})
    for item, number, slug, label, folds in (
        (2, k, slug_k, kept_label, data["keep"].get("legacy_comments")),
        (3, d, slug_d, dropped_label, data["drop"].get("legacy_comments")),
    ):
        if item not in chosen:
            continue
        for fold in folds or []:
            steps.append(
                {
                    "item": item,
                    "command": f"{TRACKER_OP} rollup-fold {number} {int(fold['comment_id'])} {dq(fold['action'])}",
                }
            )
        entry = f"{scratch}/dedupe-{slug}-rollup.md"
        steps.append(
            {
                "item": item,
                "write": entry,
                "command": f"{TRACKER_OP} rollup-append {number} {dq(label)} {w(entry)}",
            }
        )
    if 4 in chosen:
        steps.append(
            {
                "item": 4,
                "command": f"gh issue edit {d} --repo {w(tracker)} --add-label {dq(duplicate)}"
                if github
                else f"{WRITE_OP} issue-add-label {d} {dq(duplicate)}",
            }
        )
    if 5 in chosen:
        steps.append(
            {
                "item": 5,
                "command": f"gh issue close {d} --repo {w(tracker)} --reason 'not planned'"
                if github
                else f"{WRITE_OP} issue-close {d} not-planned",
                "check": f"this closes the DROPPED tracker {drop}; the kept tracker {keep} stays open",
            }
        )
    cve_id = one_line(data.get("cve_id")).upper()
    retract = one_line(data.get("retract_cve")).upper()
    for value in (cve_id, retract):
        if value and not selectors.CVE.match(value):
            return {"ok": False, "refused": f"{value!r} is not CVE-YYYY-NNNNN"}
    if 6 in chosen:
        report = f"{scratch}/cve-report-{slug_k}.json"
        if github:
            steps.append(
                {
                    "item": 6,
                    "command": f"uv run --project {generator} generate-cve-json {k} --attach --report-json {w(report)}",
                    "report": report,
                }
            )
        else:
            out = f"{scratch}/{cve_id or 'cve-' + slug_k}.json"
            steps += [
                {
                    "item": 6,
                    "command": f"{READ_OP} --save cve-body-{slug_k}.md issue-body {k}",
                    "prints": "the saved path, used as <saved> below",
                },
                {
                    "item": 6,
                    "command": f"uv run --project {generator} generate-cve-json --stdin --title {dq(data.get('title') or '<issue title>')}"
                    f"{' --review' if data.get('review') else ''} --output {w(out)} --report-json {w(report)} < <saved>",
                    "report": report,
                },
                {
                    "item": 6,
                    "command": f"{WRITE_OP} issue-attach {k} {w(out)} {w((cve_id or 'cve-' + slug_k) + '.json')}",
                },
            ]
        if cve_id:
            steps.append(
                {
                    "item": 6,
                    "command": f"the CVE tool's push_update({cve_id}, <regenerated JSON>) with no state transition",
                }
            )
    if 7 in chosen:
        if not retract or not cve_id:
            return {"ok": False, "refused": "item 7 retracts the dropped side's CVE and needs both CVE IDs"}
        steps.append(
            {
                "item": 7,
                "command": f'the CVE tool\'s retract({retract}, "merged into {cve_id} per {tracker}#{keep} on {one_line(data.get("date"))}")',
                "gate": "governance.cve_allocation_gate: confirm the user holds it before firing",
            }
        )
    if platform == "local-files" and steps:
        steps.append(
            {"item": None, "command": f"{READ_OP} tracker-pending", "then": "propose tracker-publish"}
        )
    return {
        "ok": True,
        "steps": steps,
        "on_failure": "stop and ask; partial merges are recoverable once the body update (item 1) succeeded",
        "then": "run security-issue-sync on the kept tracker",
    }
