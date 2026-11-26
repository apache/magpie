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
"""The CVE JSON refresh on a GitHub tracker, as apply-plan steps.

`generate-cve-json <N> --attach` would run `gh` inside the sandbox, which
cannot read its configuration. So the issue and the roster are saved through
vetted reads, the generator runs on those files (`--issue-json`,
`--collaborators`, `--attach --output-body`) and never calls `gh`, and the
vetted `issue-edit-body` write puts the body back.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from security_management.shell import w


def _ws(workspace: str, name: str) -> str:
    """A path under the vetted-ops workspace; the `<workspace>` placeholder stays bare."""
    path = f"{workspace.rstrip('/')}/{name}"
    return path if workspace == "<workspace>" else w(path)


def github_steps(
    item: int,
    ref: str,
    slug: str,
    generator: str,
    report: str,
    data: Mapping[str, Any],
    read_op: str,
    write_op: str,
) -> list[dict[str, Any]]:
    """The four steps: save the issue, save the roster, generate, write the body back."""
    workspace = str(data.get("workspace") or "<workspace>")
    issue = f"cve-issue-{slug}.json"
    body = _ws(workspace, f"cve-body-{slug}.md")
    baseline = f" --baseline {w(data['baseline'])}" if data.get("baseline") else ""
    return [
        {"item": item, "command": f"{read_op} --save {issue} issue-view {ref}"},
        {"item": item, "command": f"{read_op} --save cve-team.txt collaborators"},
        {
            "item": item,
            "command": f"{generator} --issue-json {_ws(workspace, 'saved/' + issue)}"
            f" --collaborators {_ws(workspace, 'saved/cve-team.txt')}{baseline}"
            f" --attach --output-body {body} --report-json {w(report)}",
            "report": report,
        },
        {
            "item": item,
            "command": f"{write_op} issue-edit-body {ref} {body}",
            "when": "the generator wrote the body (it did not print `already current`)",
        },
    ]
