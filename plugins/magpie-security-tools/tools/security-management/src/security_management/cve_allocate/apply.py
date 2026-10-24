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

1 the *CVE tool link* field (`body-field-set`, the one load-bearing write: a
later sync reads the CVE from it), 2 the label, 3 the legacy folds oldest
first and then the rollup entry, 4 the CVE JSON (`--attach` on GitHub; the
saved body, `--stdin` and `issue-attach` elsewhere), 5 the draft, and the
rollup amend when the entry went out with the `<pending>` draft id. Stop at
the first failure and ask; never retry silently.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from security_management.cve_allocate.gate import CVE_ALLOCATED, CVE_FIELD
from security_management.cve_allocate.render import _cve, label
from security_management.shell import dq, w

CALLER = "--caller security-cve-allocate"
TRACKER_OP = f"uv run --project ~/.claude/magpie/vetted-ops vetted-op-tracker {CALLER}"
READ_OP = f"uv run --project ~/.claude/magpie/vetted-ops vetted-op-read {CALLER}"
WRITE_OP = f"uv run --project ~/.claude/magpie/vetted-ops vetted-op {CALLER}"


def plan(data: Mapping[str, Any]) -> dict[str, Any]:
    tracker = str(data["tracker"])
    platform = str(data.get("platform") or "github")
    issue = data["issue"]
    ref = str(int(issue)) if platform == "github" else w(str(issue))
    cve_id = _cve(data)
    chosen = {int(n) for n in data.get("items") or []}
    scratch = str(data["scratch"]).rstrip("/")
    slug = str(issue).replace("/", "-")
    field = str(data.get("cve_field") or CVE_FIELD)
    allocated = str(data.get("cve_allocated_label") or CVE_ALLOCATED)
    generator = f"uv run --project {w(str(data.get('generator') or '<framework>/tools/cve-tool-vulnogram/generate-cve-json'))} generate-cve-json"
    action = dq(label(cve_id))
    link_file = f"{scratch}/cve-tool-link-{slug}.md"
    rollup_file = f"{scratch}/rollup-entry-{slug}.md"
    report = f"{scratch}/cve-report-{slug}.json"
    steps: list[dict[str, Any]] = []
    if 1 in chosen:
        steps.append(
            {
                "item": 1,
                "write": link_file,
                "command": f"{TRACKER_OP} body-field-set {ref} {dq(field)} {w(link_file)}",
                "load_bearing": True,
            }
        )
    if 2 in chosen:
        command = (
            f"gh issue edit {ref} --repo {w(tracker)} --add-label {dq(allocated)}"
            if platform == "github"
            else f"{WRITE_OP} issue-add-label {ref} {dq(allocated)}"
        )
        steps.append({"item": 2, "command": command})
    if 3 in chosen:
        for fold in data.get("legacy_comments") or []:
            steps.append(
                {
                    "item": 3,
                    "command": f"{TRACKER_OP} rollup-fold {ref} {int(fold['comment_id'])} {dq(fold['action'])}",
                }
            )
        steps.append(
            {
                "item": 3,
                "write": rollup_file,
                "command": f"{TRACKER_OP} rollup-append {ref} {action} {w(rollup_file)}",
            }
        )
    if 4 in chosen:
        if platform == "github":
            steps.append(
                {
                    "item": 4,
                    "command": f"{generator} {ref} --attach --report-json {w(report)}",
                    "report": report,
                }
            )
        else:
            out = f"{scratch}/{cve_id}.json"
            review = " --review" if data.get("review") else ""
            steps += [
                {
                    "item": 4,
                    "command": f"{READ_OP} --save cve-body-{slug}.md issue-body {ref}",
                    "prints": "the saved path, used as <saved> below",
                },
                {
                    "item": 4,
                    "command": f"{generator} --stdin --title {dq(data.get('title') or '<issue title>')}{review} "
                    f"--output {w(out)} --report-json {w(report)} < <saved>",
                    "report": report,
                },
                {"item": 4, "command": f"{WRITE_OP} issue-attach {ref} {w(out)} {w(cve_id + '.json')}"},
            ]
    if 5 in chosen:
        steps.append({"item": 5, "command": "create the draft from the Step 4 draft plan"})
        if data.get("needs_amend"):
            steps.append(
                {
                    "item": 5,
                    "write": rollup_file,
                    "command": f"{TRACKER_OP} rollup-amend-latest {ref} {action} {w(rollup_file)}",
                    "when": "the rollup entry went out with the `<pending>` draft id",
                }
            )
    if platform == "local-files" and steps:
        steps.append(
            {"item": None, "command": f"{READ_OP} tracker-pending", "then": "propose tracker-publish"}
        )
    return {
        "tracker": tracker,
        "issue": issue,
        "steps": steps,
        "on_failure": "stop and ask; item 1 is the only load-bearing write (a later sync reads the CVE from it)",
        "then": "Step 6: run security-issue-sync on the same tracker",
    }
