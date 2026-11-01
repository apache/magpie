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
"""pr-stale-sweep Step 4: the one comment per proposal, rendered.

The nudge carries `<!-- pr-stale-sweep-nudge -->`, the close notice
`<!-- pr-stale-sweep-close -->` — a close notice is not a nudge, so a later
sweep never reads it as one. The author is the only `@`-mention (any other
handle is backtick-quoted) and every bare `#NNN` is linked, by the triage
renderer's `enforce`.
"""

from __future__ import annotations

import re
import shlex
from importlib import resources
from pathlib import Path
from typing import Any

from .. import mentions
from ..config import Config
from ..triage.render import enforce

TEMPLATES = {"REQUEST-UPDATE": "request-update", "CLOSE-STALE": "close-stale"}
_PLACEHOLDER = re.compile(r"<[a-z_]+>")


def _template(stem: str) -> str:
    text = (
        resources.files("pr_management.stale_sweep")
        .joinpath("templates", f"{stem}.tmpl")
        .read_text(encoding="utf-8")
    )
    return re.sub(r"\A<!-- SPDX.*?-->\n", "", text, flags=re.DOTALL)


def render(entry: dict[str, Any], cfg: Config, out_dir: Path) -> dict[str, Any]:
    """Write the comment for one proposal (an entry of `classify`'s `proposals`)."""
    cls = entry["class"]
    if cls not in TEMPLATES:
        raise ValueError(f"{cls} takes no comment")
    values = {
        "<author>": entry["author"],
        "<days_idle>": str(entry["days_idle"]),
        "<remaining_days>": str(entry.get("remaining_days", "")),
        "<default_branch>": cfg.default_branch,
    }
    body = _template(TEMPLATES[cls])
    for key, value in values.items():
        body = body.replace(key, value)
    body, mentioned = enforce(body, entry["author"], cfg.upstream_repo, mentions.allowed(cfg))
    leftover = sorted(set(_PLACEHOLDER.findall(re.sub(r"<!--.*?-->", "", body, flags=re.DOTALL))))
    number = int(entry["number"])
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"pr-stale-sweep-{number}.md"
    path.write_text(body, encoding="utf-8")
    repo = cfg.upstream_repo or "<upstream>"
    commands = [shlex.join(["gh", "pr", "comment", str(number), "--repo", repo, "--body-file", str(path)])]
    if cls == "CLOSE-STALE":
        # Only after the comment posted and the maintainer confirmed the close a second time.
        commands.append(shlex.join(["gh", "pr", "close", str(number), "--repo", repo]))
    return {
        "pr": number,
        "class": cls,
        "body_file": str(path),
        "mentions": mentioned,
        "preview": body,
        "commands": commands,
        "ok": not leftover,
        "warnings": [f"unresolved placeholder {p}" for p in leftover],
    }
