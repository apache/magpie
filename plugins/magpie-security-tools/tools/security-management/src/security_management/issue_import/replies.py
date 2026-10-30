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
"""Fixed-shape texts the import skill drafts: the rejections-ledger record and the fix-already-public reply.

The canned responses themselves stay in `<project-config>/canned-responses.md`;
these two shapes are the skill's own.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from security_management.shared import body
from security_management.shared.rollup import one_line
from security_management.shared.titles import strip_mail_prefixes

LEDGER_MARKER = "<!-- rejection v1 -->"
ARCHIVE_UNRESOLVED = "unresolved (archive lag)"
LEDGER_KEYS = ("date", "reporter", "title", "canned", "thread", "archive", "summary")


def _ledger_value(value: object) -> str:
    # One line per key, and no comment opener: a reporter-derived value can
    # neither add a key nor forge a second `<!-- rejection v1 -->` record.
    # It is sanitised like a body field, so an image or tag in a rejected
    # subject or a reporter name is not rendered in the ledger comment.
    return body.short_field(one_line(value)).replace("-->", "--&gt;")


def ledger(data: Mapping[str, Any]) -> dict[str, Any]:
    missing = [k for k in ("date", "reporter", "title", "canned", "thread", "summary") if not data.get(k)]
    if missing:
        return {"ok": False, "refused": f"ledger record is missing {', '.join(missing)}"}
    values = {
        "date": data["date"],
        "reporter": data["reporter"],
        "title": strip_mail_prefixes(one_line(data["title"])),
        "canned": data["canned"],
        "thread": data["thread"],
        "archive": data.get("archive") or ARCHIVE_UNRESOLVED,
        "summary": data["summary"],
    }
    lines = [LEDGER_MARKER, *(f"{k}: {_ledger_value(values[k])}" for k in LEDGER_KEYS)]
    return {"ok": True, "archive_resolved": bool(data.get("archive")), "text": "\n".join(lines) + "\n"}


def _pr_link(upstream: str, number: int) -> str:
    return f"[`{upstream}#{number}`](https://github.com/{upstream}/pull/{number})"


def _pr_line(upstream: str, pr: Mapping[str, Any]) -> str:
    number = int(pr["number"])
    author = one_line(pr["author"])
    verb = "merged" if str(pr.get("state", "")).lower() == "merged" else "opened"
    return (
        f"{_pr_link(upstream, number)} ([`{author}`](https://github.com/{author}), {verb} on "
        f"{one_line(pr['date'])})"
    )


def fix_public_reply(data: Mapping[str, Any]) -> dict[str, Any]:
    """The thank-without-credit, verify-with-PR reply; `merged on` / `opened on` per PR state."""
    upstream = str(data["upstream"])
    security_list = one_line(data["security_list"])
    prs: Sequence[Mapping[str, Any]] = data.get("prs") or []
    if not prs:
        return {"ok": False, "refused": "fix-already-public reply needs at least one PR"}
    if len(prs) == 1:
        noticed = (
            f"We noticed that\n{_pr_line(upstream, prs[0])} already appears to address what you described."
        )
        check = f"Could you check whether\n{_pr_link(upstream, int(prs[0]['number']))}\nfixes"
        test = "this PR"
    else:
        listed = "\n".join(f"- {_pr_line(upstream, pr)}" for pr in prs)
        noticed = f"We noticed that these pull requests together already appear to address what you described:\n\n{listed}"
        check = "Could you check whether these pull requests fix"
        test = "these PRs"
    text = (
        f"Thank you for taking the time to report this through\n`{security_list}`. {noticed}\n\n"
        "Per our policy, we do not add a finder when the fix to the\n"
        "reported issue is already public at the time of report — but\n"
        "we very much appreciate your effort in writing to us, and the\n"
        "care you took to send it via the private channel.\n\n"
        f"{check} the behaviour you observed? If it does, no further action\n"
        f"is needed on your side. **If after testing with {test} you\n"
        "still see the issue, please reply on this thread with the\n"
        "failing reproduction** and we will reopen the assessment as a\n"
        "regular report.\n"
    )
    return {"ok": True, "text": text, "finder_credit": None}
