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
"""Steps 5a, 5c, 5f, 7 and 9: the forbidden-term check on every public surface.

One check for the branch name, the commit message, the PR title and body,
a newsfragment and a comment on `<upstream>`: the machine-checkable subset
of the 5c list, from `magpie_vcs.publication.scrub` (CVE IDs and `CVE`,
`vulnerability`, `security fix`, `advisory`, `security@`, the CVE-tool URL,
`exploit`, vulnerability-class names), plus each reporter name and the
private tracker text verbatim. A branch name also may not carry `security`
as a word (5a). Tracker URLs and `#NNN` are not flagged: they are
public-safe identifiers.

What a pattern cannot see — exploitation detail, the *"sensitive"* wording
of 5c — stays the model's check; a clean result is the floor.
A newsfragment is not proposed by default for a security-adjacent fix; one
carrying security framing is a violation either way.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from security_management.shared import reuse

SURFACES = ("branch", "title", "body", "commit_message", "newsfragment", "comment")
_SECURITY_WORD = re.compile(r"\bsecurity\b", re.IGNORECASE)


def check(data: Mapping[str, Any]) -> dict[str, Any]:
    names = [str(n) for n in data.get("reporter_names") or [] if str(n).strip()]
    private = [str(t) for t in data.get("private_texts") or [] if str(t).strip()]
    allow = [str(a) for a in data.get("allow") or []]
    out: dict[str, Any] = {"ok": True}
    every: list[dict[str, Any]] = []
    for surface in SURFACES:
        text = data.get(surface)
        if text is None:
            continue
        text = str(text)
        if surface == "branch":
            result = reuse.scrub(branch=text, extra_terms=names, allow=allow)
            hits = list(result["hits"])
            spaced = re.sub(r"[-_/.]+", " ", text)
            if _SECURITY_WORD.search(spaced) and not any(h["term"] == "security fix" for h in hits):
                hits.append(
                    {"surface": "branch", "term": "security", "match": "security", "line": None, "file": None}
                )
        else:
            result = reuse.scrub(message=text, extra_terms=names, allow=allow, private_texts=private)
            hits = list(result["hits"])
        for hit in hits:
            hit["surface"] = surface
        out[surface] = {"valid": not hits, "terms": sorted({h["term"] for h in hits}), "hits": hits}
        every.extend(hits)
    out["clean"] = not every
    out["forbidden_terms_found"] = sorted({h["match"] for h in every})
    if "newsfragment" in out:
        out["include_newsfragment"] = False
        out["security_framing_violation"] = not out["newsfragment"]["valid"]
    return out
