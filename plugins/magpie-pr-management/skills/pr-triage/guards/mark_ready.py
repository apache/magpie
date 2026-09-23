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

"""pr-management-triage mark-ready guard (skill-contributed).

Deterministically enforces Golden rule 1b: never add the "ready for maintainer
review" label while the PR head SHA still has GitHub Actions runs awaiting
approval (the real CI has not run yet). Fail-open if the authoritative lookup
cannot be made — never block a legitimate label on a transient error.
Discovered by the agent-guard PreToolUse dispatcher; import-free (uses ``ctx``).
"""

TRIGGERS = ["gh"]


def guard(ctx):
    if ctx.gh_subcommand() != ("pr", "edit"):
        return None
    label = ctx.opt("", "--add-label")
    ready = ctx.ready_label
    if not label or label.strip().lower() != ready.strip().lower():
        return None
    if ctx.override("MAGPIE_ALLOW_MARK_READY"):
        return None

    target = ctx.positional_after("edit")
    if not target:
        return None  # fail-open: cannot identify the PR.
    repo = ctx.opt("-R", "--repo")
    head = ctx.run(
        ["gh", "pr", "view", target, *ctx.repo_flag(), "--json", "headRefOid", "--jq", ".headRefOid"]
    )
    if not repo:
        repo = ctx.run(["gh", "repo", "view", "--json", "nameWithOwner", "--jq", ".nameWithOwner"])
    if not head or not repo:
        return None  # fail-open: cannot run the authoritative check.
    pending = ctx.run(
        [
            "gh",
            "api",
            f"repos/{repo}/actions/runs?head_sha={head}&per_page=20",
            "--jq",
            '[.workflow_runs[] | select(.conclusion == "action_required")] | length',
        ]
    )
    if pending and pending.isdigit() and int(pending) > 0:
        return (
            f"agent-guard[mark-ready]: PR has {pending} GitHub Actions run(s) awaiting "
            f"approval at head {head[:7]}; adding '{ready}' now is premature (Golden rule "
            "1b) — the real CI has not run. Approve/await the workflow first. Override: "
            "MAGPIE_ALLOW_MARK_READY=1."
        )
    return None
