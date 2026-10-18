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
"""The mentoring configuration: `<project-config>/mentoring-config.md`.

Required keys abort the skill when missing or still a template placeholder;
the skill never guesses a project value. `committers_team` comes from
`pr-management-config.md`, for the maintainer-engaged check.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from .. import mdconfig

REQUIRED = (
    "mentoring_invocation_command",
    "maintainer_team_handle",
    "ai_attribution_footer",
    "convention_pointers",
    "max_agent_turns",
    "out_of_scope_topics",
)

#: Keywords a topic heading implies, so a prose topic still has a deterministic prefilter.
_TOPIC_KEYWORDS: dict[str, tuple[str, ...]] = {
    "security": ("security", "vulnerab", "cve-", "exploit", "embargo", "rce", "remote code execution"),
    "deprecation": ("deprecate", "deprecation", "deprecated", "drop support", "removal of"),
    "license": ("licen", "copyright"),
}


@dataclass(frozen=True)
class Pointer:
    trigger: str
    url: str | None
    label: str | None


@dataclass
class MentoringConfig:
    invocation_command: str | None = None
    maintainer_team_handle: str | None = None
    footer: str | None = None
    max_agent_turns: int | None = None
    pointers: list[Pointer] = field(default_factory=list)
    out_of_scope: list[str] = field(default_factory=list)
    committers_team: str | None = None
    missing: list[str] = field(default_factory=list)
    source: str | None = None

    def keywords(self) -> dict[str, list[str]]:
        """Out-of-scope topic → the lowercase keywords that prefilter it."""
        found: dict[str, list[str]] = {}
        for topic in self.out_of_scope:
            lowered = topic.lower()
            words: list[str] = []
            for key, implied in _TOPIC_KEYWORDS.items():
                if key in lowered:
                    words.extend(implied)
            inside = re.findall(r"\(([^)]*)\)", topic)
            for chunk in inside:
                words.extend(w.strip().lower() for w in re.split(r"[,;]| or ", chunk) if len(w.strip()) > 3)
            found[topic] = sorted(set(words))
        return found


def _is_placeholder(value: str | None) -> bool:
    return value is None or not value.strip() or "<" in value or value.upper().startswith("TODO")


def load(project_root: Path, config_dir: Path | None = None) -> MentoringConfig:
    resolver = mdconfig.Resolver(project_root, config_dir)
    cfg = MentoringConfig()
    path = resolver.find("mentoring-config.md")
    cfg.source = str(path) if path else None
    text = resolver.read("mentoring-config.md")
    values = mdconfig.key_values(text)
    cfg.invocation_command = values.get("mentoring_invocation_command")
    cfg.maintainer_team_handle = values.get("maintainer_team_handle")
    turns = values.get("max_agent_turns")
    if turns and turns.strip().isdigit():
        cfg.max_agent_turns = int(turns)
    for cells in mdconfig.table_rows(mdconfig.section(text, "Convention pointers")):
        if len(cells) < 3 or cells[0].lower() == "trigger":
            continue
        url = mdconfig.first_token(cells[1])
        label = mdconfig.first_token(cells[2])
        cfg.pointers.append(
            Pointer(
                cells[0], None if _is_placeholder(url) else url, None if _is_placeholder(label) else label
            )
        )
    topics = mdconfig.section(text, "Out-of-scope topics") or ""
    current: list[str] = []
    for line, inside in mdconfig.live_lines(topics):
        if inside:
            continue
        if re.match(r"^\s*[-*]\s+", line):
            if current:
                cfg.out_of_scope.append(" ".join(current))
            current = [re.sub(r"^\s*[-*]\s+", "", line).strip()]
        elif line.startswith("  ") and current:
            current.append(line.strip())
    if current:
        cfg.out_of_scope.append(" ".join(current))
    footer = mdconfig.first_fence(mdconfig.section(text, "AI-attribution footer"))
    cfg.footer = footer.strip("\n") if footer else None

    triage = mdconfig.key_values(resolver.read("pr-management-config.md"))
    team = triage.get("committers_team")
    cfg.committers_team = None if _is_placeholder(team) else team

    if text is None:
        cfg.missing = list(REQUIRED)
        return cfg
    for key, value in (
        ("mentoring_invocation_command", cfg.invocation_command),
        ("maintainer_team_handle", cfg.maintainer_team_handle),
        ("ai_attribution_footer", cfg.footer),
    ):
        if _is_placeholder(value):
            cfg.missing.append(key)
    if cfg.max_agent_turns is None:
        cfg.missing.append("max_agent_turns")
    if not any(p.url and p.label for p in cfg.pointers):
        cfg.missing.append("convention_pointers")
    if not cfg.out_of_scope:
        cfg.missing.append("out_of_scope_topics")
    return cfg
