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

"""security-issue-fix public-PR scrubbing guard (skill-contributed).

Deterministically blocks a CVE id or security-fix language in a PUBLIC
`gh pr create` / `gh pr edit` title or body — per the ASF process, the security
nature of a fix must not appear in public content before the CVE is announced.

Scoped to PR create/edit (NOT comments) on purpose, so it does not collide with
the pr-management-triage `security_language_signal` warning comment, which
deliberately quotes the matched text back to the contributor. Discovered by the
agent-guard PreToolUse dispatcher; uses only ``ctx`` + the stdlib.
"""

import re

TRIGGERS = ["gh"]

CVE_RE = re.compile(r"\bCVE-\d{4}-\d{3,}\b", re.IGNORECASE)

# Curated subset of the canonical list in tools/skill-and-tool-validator
# (security_pattern check) — kept narrow to limit false positives.
SECURITY_KEYWORDS = (
    "sql injection",
    "xss",
    "csrf",
    "ssrf",
    "remote code execution",
    "arbitrary code execution",
    "path traversal",
    "directory traversal",
    "privilege escalation",
    "auth bypass",
    "authentication bypass",
    "buffer overflow",
    "heap overflow",
    "use-after-free",
    "security vulnerability",
    "security fix",
    "exploitable",
)


def guard(ctx):
    if ctx.gh_subcommand() not in (("pr", "create"), ("pr", "edit")):
        return None
    text = ctx.gh_body(include_title=True, read_files=True)
    if not text:
        return None
    if ctx.override("MAGPIE_ALLOW_SECURITY_LANG"):
        return None
    lowered = text.lower()
    hits = []
    cve = CVE_RE.search(text)
    if cve:
        hits.append(cve.group(0))
    hits.extend(kw for kw in SECURITY_KEYWORDS if kw in lowered)
    if hits:
        return (
            "agent-guard[security-language]: this public PR title/body contains "
            f"security-fix language {sorted(set(hits))}. Per the ASF process, the "
            "security nature of a fix must not appear in public content before the CVE "
            "is announced — neutralise the wording. If disclosure is already public, "
            "override with MAGPIE_ALLOW_SECURITY_LANG=1."
        )
    return None
