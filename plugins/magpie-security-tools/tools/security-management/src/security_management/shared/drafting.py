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
"""Reporter drafts the security skills share: the backend choice and the leak scan.

- `backend` picks the drafting backend per `tools/gmail/draft-backends.md`:
  `maildir` when configured, else `oauth_curl` (the `gmail-plaintext` MCP
  server), and the discouraged `claude_ai_mcp` only without OAuth
  credentials and with no link in the body, since it rewrites links.
- `anchor` is what each backend needs to attach the draft to the inbound thread.
- `scan` greps a composed body before it is drafted: any `<tracker>`
  reference (the reporter cannot open it), the CVE-tool URL, a bare `#NNN`,
  a re-opening phrase, a CVSS score, and the AGENTS.md list of other ASF
  project names. Writing the body stays the agent's job.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from typing import Any

from security_management.shared import refs

ASF_PROJECTS = (
    "Superset", "Allura", "Tomcat", "Kafka", "Spark", "Cassandra", "Hadoop", "Hive", "HTTPD", "Struts",
    "Solr", "Zookeeper", "Beam", "Flink", "NiFi", "Pulsar", "CloudStack", "OFBiz", "Commons", "Lucene",
    "Camel", "Druid", "ActiveMQ", "Guacamole", "Shiro", "CXF", "Iceberg",
)  # fmt: skip
_CROSS_PROJECT = re.compile(
    r"also reported against|cross-project|other apache projects|sister project|the same finder also",
    re.IGNORECASE,
)
_REOPEN = re.compile(
    r"happy to discuss further|open to other views|let us know if you disagree", re.IGNORECASE
)
_CVSS = re.compile(r"CVSS|\bAV:[NALP]\b|\b\d{1,2}\.\d\s*\(?(?:low|medium|high|critical)\b", re.IGNORECASE)
_CVE_TOOL_URL = re.compile(r"cveprocess\.apache\.org\S*")


def backend(data: Mapping[str, Any]) -> tuple[str, str | None]:
    """`(backend, note)`; `ValueError` when only `claude_ai_mcp` is left and the body has links."""
    if str(data.get("drafting_backend") or "gmail") == "maildir":
        return "maildir", None
    if data.get("oauth_credentials", True):
        return "oauth_curl", None
    if data.get("body_has_links", True):
        raise ValueError(
            "no oauth_curl credentials and the body has links: the claude_ai_mcp backend would rewrite them; "
            "refresh the OAuth credentials"
        )
    return "claude_ai_mcp", "discouraged: no OAuth credentials and the body has no links"


def choose(data: Mapping[str, Any]) -> dict[str, Any]:
    """The whole choice: Gmail or Maildir first, then the Gmail backend.

    The person's `tools.mail_create.backend` (`user_backend`) wins over the
    project's `mail_create.backend` (`project_backend`), else `gmail`.
    `oauth_credentials` is the `mcp__gmail-plaintext__check_auth` answer.
    """
    decided_by = "default"
    choice = "gmail"
    for key, source in (("user_backend", "user.md"), ("project_backend", "project.md")):
        value = str(data.get(key) or "").strip().lower()
        if value:
            if value not in ("gmail", "maildir"):
                raise ValueError(f"{source}: mail_create.backend {value!r} is neither gmail nor maildir")
            choice, decided_by = value, source
            break
    name, note = backend({**data, "drafting_backend": choice})
    return {"backend": name, "decided_by": decided_by, "note": note}


def anchor(name: str, data: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "oauth_curl": {"thread_id": data.get("thread_id")},
        "claude_ai_mcp": {"reply_to_message_id": data.get("last_message_id")},
        "maildir": {"in_reply_to": data.get("root_message_id")},
    }[name]


def scan(text: str, tracker: str, own_names: Iterable[object] = ()) -> list[dict[str, Any]]:
    """Every leak in `text`: `{kind, line, text}`, `line` 1-based or `None`."""
    owner = tracker.split("/")[0]
    hits: list[dict[str, Any]] = []

    def hit(kind: str, pattern: re.Pattern[str]) -> None:
        for number, line in enumerate(text.split("\n"), 1):
            for match in pattern.finditer(line):
                hits.append({"kind": kind, "line": number, "text": match.group(0)})

    hit(
        "tracker-reference",
        re.compile(re.escape(tracker) + r"|\b" + re.escape(owner) + r"#\d+", re.IGNORECASE),
    )
    hit("cve-tool-url", _CVE_TOOL_URL)
    hit("reopening-phrase", _REOPEN)
    hit("cvss", _CVSS)
    hit("cross-project", _CROSS_PROJECT)
    own = {str(n).lower() for n in own_names}
    names = [n for n in ASF_PROJECTS if n.lower() not in own]
    hit("asf-project", re.compile(r"\b(?:" + "|".join(names) + r")\b"))
    for ref in refs.bare_refs(text):
        hits.append({"kind": "bare-ref", "line": None, "text": ref})
    return hits
