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
"""Step 3: what the user sees to get a CVE ID, by who they are and what the pre-flight chose.

- `api` (a governance-authorised user, pre-flight `api`): one proposal to
  allocate through the CVE tool's API, with the form URL as the fallback and
  the one `vulnogram-api-allocate` command to run on a yes.
- `recipe` (authorised, any other pre-flight outcome): open the allocation
  URL, paste the title, submit, paste the ID back.
- `relay` (not authorised): a terse request for an authorised member — the
  URL, the title and one line asking for the ID back, nothing else. The
  submit surface refuses a non-member, so they never get "click *Allocate*".

The authorisation question must be answered first: an unknown answer is
refused. The title sits in a `text` fence longer than any backtick run in it,
and is shell-quoted in the API command, since it is reporter-influenced.
"""

from __future__ import annotations

import re
import shlex
from collections.abc import Mapping, Sequence
from typing import Any

from security_management.cve_allocate.gate import OAUTH_API
from security_management.shared import refs
from security_management.shared.rollup import one_line
from security_management.shell import w

PASTE_BACK = "Paste the allocated `CVE-YYYY-NNNNN` back here when done."
_HANDLE = re.compile(r"^@?([A-Za-z0-9](?:[A-Za-z0-9-]{0,38}))$")


def fence(text: str) -> str:
    longest = max((len(run) for run in re.findall(r"`+", text)), default=0)
    ticks = "`" * max(3, longest + 1)
    return f"{ticks}text\n{text}\n{ticks}"


def _handles(values: Sequence[object]) -> list[str]:
    out = []
    for value in values:
        match = _HANDLE.match(one_line(value))
        if not match:
            raise ValueError(f"{value!r} is not a GitHub handle")
        out.append("@" + match.group(1))
    return out


def render(data: Mapping[str, Any]) -> dict[str, Any]:
    member = data.get("governance_member")
    if member not in (True, False):
        return {
            "ok": False,
            "refused": "ask whether the user is authorised under governance.cve_allocation_gate first",
        }
    title = one_line(data.get("title"))
    if not title:
        return {"ok": False, "refused": "no CVE-ready title: run Step 2 first"}
    url = one_line(data.get("allocate_url"))
    if not url.startswith("https://"):
        return {"ok": False, "refused": "cve_authority.allocate_url is not an https URL"}
    tracker = str(data["tracker"])
    link = refs.tracker_link(
        tracker, data["issue"], data.get("issue_url"), str(data.get("platform") or "github")
    )
    block = fence(title)
    command = None
    if member and (data.get("preflight") or {}).get("path") == "api":
        pmc = one_line(data.get("pmc"))
        if not pmc:
            return {"ok": False, "refused": "the API path needs cna_private_owner (the PMC) from project.md"}
        oauth_api = str(data.get("oauth_api") or OAUTH_API)
        path = "api"
        text = (
            f"**Allocate a CVE for {link}** through the Vulnogram API, for `{pmc}`, with this title:\n\n"
            f"{block}\n\n"
            "This reserves a CVE ID immediately and cannot be undone.\n"
            f"(Fallback, if the API path fails: the form at {url}.)\n"
        )
        command = f"uv run --project {w(oauth_api)} vulnogram-api-allocate --pmc {w(pmc)} --title {shlex.quote(title)}"
    elif member:
        path = "recipe"
        indented = "\n".join("   " + line for line in block.split("\n"))
        text = (
            f"**Allocate a CVE for {link}.**\n\n"
            "1. Authenticate to the CVE tool per the adapter's docs, then open the allocation URL:\n"
            f"   {url}\n"
            "2. In the *Title* field, paste this:\n\n"
            f"{indented}\n\n"
            "3. Submit the allocation. The CVE tool returns a `CVE-YYYY-NNNNN` ID — for the Vulnogram "
            "adapter, clicking *Allocate*.\n"
            "4. Paste the allocated CVE ID back into this conversation — the skill will pick it up and "
            "update the tracker.\n"
        )
    else:
        path = "relay"
        handles = _handles(data.get("authorised_handles") or [])
        ask = f"{' '.join(handles)} — could" if handles else "Could"
        text = f"{ask} one of you allocate a CVE for {link}?\n\n{url}\n\nTitle:\n\n{block}\n\n{PASTE_BACK}\n"
    return {
        "ok": True,
        "path": path,
        "text": text,
        "command": command,
        "governance_member_path": member,
        "relay_message_present": path == "relay",
        "api_allocation_proposed": path == "api",
        "bare_refs": refs.bare_refs(text),
    }
