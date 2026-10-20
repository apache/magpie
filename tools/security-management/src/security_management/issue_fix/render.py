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
"""Step 11: the recap of a pull-request run.

The public PR URL, the branch in the user's fork, the files changed, each
local check with its result, the comment posted on the tracker, the backport
label (or that none was needed), and the next step — by default, wait for
review and re-run `security-issue-sync` once the PR merges.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from security_management.shared import refs
from security_management.shared.rollup import code, one_line

NEXT_STEP = (
    "wait for review; re-run `security-issue-sync` after the PR merges to move the tracker from "
    "`pr created` to `pr merged` and update the milestone."
)


def recap(data: Mapping[str, Any]) -> dict[str, Any]:
    tracker = str(data["tracker"])
    pr_url = one_line(data.get("pr_url"))
    if not pr_url.startswith("https://"):
        return {"ok": False, "refused": "the public PR URL is required"}
    files = [one_line(f) for f in data.get("files") or [] if one_line(f)]
    tests = data.get("tests") or []
    labels = [one_line(x) for x in data.get("backport_labels") or [] if one_line(x)]
    issue = refs.tracker_link(
        tracker, data["issue"], data.get("issue_url"), str(data.get("platform") or "github")
    )
    lines = [
        f"**Fix PR for {issue}:** {pr_url}",
        f"- Branch (your fork): {code(data.get('branch'))}",
        "- Files changed: " + (", ".join(code(f) for f in files) or "none"),
        "- Checks: "
        + ("; ".join(f"{code(t.get('command'))} — {one_line(t.get('result'))}" for t in tests) or "none run"),
    ]
    comment = one_line(data.get("tracker_comment_url"))
    lines.append(
        f"- Tracker comment: [posted]({comment})" if comment else "- Tracker comment: not posted yet"
    )
    lines.append("- Backport label: " + (", ".join(code(x) for x in labels) if labels else "none needed"))
    lines += ["", f"**Next:** {one_line(data.get('next_step') or NEXT_STEP)}"]
    text = refs.linkify("\n".join(lines), tracker) + "\n"
    return {"ok": True, "text": text, "bare_refs": refs.bare_refs(text)}
