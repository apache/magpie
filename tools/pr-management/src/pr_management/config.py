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
"""The pr-management configuration, resolved once from `<project-config>`.

Files read, each personal layer first (see `layers.config_layers`):

* `project.md` — `upstream_repo`, `upstream_default_branch`,
  `upstream_contributing_docs_url`, `project_name`.
* `pr-management-config.md` — identifiers, labels, grace windows, workflow
  choices, `real_ci_patterns`, `static_check_patterns`.
* `pr-management-triage-comment-templates.md` — URL placeholders, the
  triage-marker link text, the AI-attribution footer.
* `pr-management-triage-ci-check-map.md` — check-name pattern → category → doc URL.
* `pr-management-triage.md` — the per-skill override file; its `` `key` ``
  rows win over `pr-management-config.md`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from . import mdconfig

#: Built-in static-check patterns (case-insensitive substring, either direction).
STATIC_CHECK_PATTERNS: tuple[str, ...] = (
    "static check",
    "pre-commit",
    "lint",
    "mypy",
    "ruff",
    "black",
    "flake8",
    "pylint",
    "isort",
    "bandit",
    "codespell",
    "yamllint",
    "shellcheck",
    "spellcheck",
    "spelling",
    "build documentation",
    "build docs",
    "build-docs",
)

#: Grace-window concept text in `pr-management-config.md § Grace windows` → field.
_GRACE_ROWS = {
    "stale-draft close threshold (triaged)": "stale_draft_triaged_days",
    "stale-draft close threshold (untriaged)": "stale_draft_untriaged_days",
    "inactive-open → draft threshold": "inactive_open_days",
    "stale-review-ping cooldown": "stale_review_cooldown_days",
    "stale-workflow-approval threshold": "stale_workflow_approval_days",
    "stale-copilot-review threshold": "stale_copilot_days",
}

DEFAULT_MARKER = "Pull Request quality criteria"
CONFIRMATION_MARKER = "ready for maintainer review confirmation"
FOLD_OPEN = "pr-triage-fold"
FOLD_CLOSE = "/pr-triage-fold"


@dataclass(frozen=True)
class CheckCategory:
    pattern: str
    category: str
    url: str | None

    def matches(self, name: str) -> bool:
        return self.pattern == "*" or self.pattern.lower() in name.lower()


@dataclass
class Config:
    upstream_repo: str | None = None
    default_branch: str = "main"
    contributing_docs_url: str | None = None
    project_name: str | None = None

    committers_team: str | None = None
    area_label_prefix: str | None = "area:"

    ready_label: str = "ready for maintainer review"
    quality_close_label: str | None = "closed because of multiple quality violations"
    suspicious_label: str | None = "suspicious changes detected"
    wip_label: str | None = None

    stale_draft_triaged_days: int = 7
    stale_draft_untriaged_days: int = 14
    inactive_open_days: int = 28
    stale_review_cooldown_days: int = 7
    stale_workflow_approval_days: int = 28
    stale_copilot_days: int = 7

    feedback_channel: str = "pr-body"
    handback_mode: str = "reviewer-ping"
    backport_branches: list[str] = field(default_factory=list)
    backport_policy: str = "fixes-only"
    session_history_gist: str = "enabled"

    real_ci_patterns: list[str] = field(default_factory=list)
    static_check_patterns: list[str] = field(default_factory=lambda: list(STATIC_CHECK_PATTERNS))
    check_map: list[CheckCategory] = field(default_factory=list)
    conflicts_url: str | None = None

    #: Handles a rendered body may keep live (`mention_allowlist`); see mentions.py.
    mention_allowlist: list[str] = field(default_factory=list)

    marker: str = DEFAULT_MARKER
    urls: dict[str, str] = field(default_factory=dict)
    footer: str | None = None

    #: Which file each part came from, for the `config` subcommand.
    sources: dict[str, str | None] = field(default_factory=dict)
    #: Problems the skill must surface (missing required files, malformed values).
    warnings: list[str] = field(default_factory=list)

    @property
    def committers_team_slug(self) -> str | None:
        if not self.committers_team:
            return None
        return self.committers_team.split("/", 1)[-1]

    def category_for(self, check_name: str) -> CheckCategory:
        for row in self.check_map:
            if row.matches(check_name):
                return row
        return CheckCategory("*", "Failing CI checks", self.contributing_docs_url)


def _days(cell: str) -> int | None:
    match = re.search(r"(\d+)\s*day", cell)
    return int(match.group(1)) if match else None


def _set(value: str | None) -> bool:
    return value is not None and not value.startswith("<") and value.upper() != "TODO"


def load(project_root: Path, config_dir: Path | None = None) -> Config:
    resolver = mdconfig.Resolver(project_root, config_dir)
    cfg = Config()

    def source(name: str) -> str | None:
        path = resolver.find(name)
        cfg.sources[name] = str(path) if path else None
        return resolver.read(name)

    project = mdconfig.key_values(source("project.md"))
    if _set(project.get("upstream_repo")):
        cfg.upstream_repo = project["upstream_repo"]
    if _set(project.get("upstream_default_branch")):
        cfg.default_branch = project["upstream_default_branch"] or "main"
    if _set(project.get("upstream_contributing_docs_url")):
        cfg.contributing_docs_url = project["upstream_contributing_docs_url"]
    if _set(project.get("project_name")):
        cfg.project_name = project["project_name"]

    main_text = source("pr-management-config.md")
    if main_text is None:
        cfg.warnings.append("pr-management-config.md not found in <project-config>; using framework defaults")
    values = mdconfig.key_values(main_text)
    override_text = source("pr-management-triage.md")
    values.update({k: v for k, v in mdconfig.key_values(override_text).items() if v is not None})

    if _set(values.get("committers_team")):
        cfg.committers_team = values["committers_team"]
    if "area_label_prefix" in values:
        cfg.area_label_prefix = values["area_label_prefix"]
    for key, attr in (
        ("ready_for_maintainer_review", "ready_label"),
        ("quality_violations_close", "quality_close_label"),
        ("suspicious_changes", "suspicious_label"),
        ("work_in_progress", "wip_label"),
    ):
        if key in values:
            value = values[key]
            if attr == "ready_label":
                if value:
                    cfg.ready_label = value
            else:
                setattr(cfg, attr, value or None)
    for key, attr, allowed in (
        ("triage_feedback_channel", "feedback_channel", {"pr-body", "comment"}),
        ("confirmation_handback_mode", "handback_mode", {"reviewer-ping", "maintainer-sweep"}),
        ("backport_policy", "backport_policy", {"fixes-only", "any"}),
        ("session_history_gist", "session_history_gist", {"enabled", "disabled"}),
    ):
        value = values.get(key)
        if value is None:
            continue
        if value in allowed:
            setattr(cfg, attr, value)
        else:
            cfg.warnings.append(
                f"{key}: {value!r} is not one of {sorted(allowed)}; using {getattr(cfg, attr)!r}"
            )

    for cells in mdconfig.table_rows(main_text):
        if not cells:
            continue
        key = cells[0].strip("`").strip()
        if key == "backport_branches":
            cfg.backport_branches = mdconfig.tokens(cells[1]) if len(cells) > 1 else []
        elif key == "real_ci_patterns" and len(cells) > 1:
            cfg.real_ci_patterns = mdconfig.tokens(cells[1])
        elif key == "mention_allowlist" and len(cells) > 1:
            cfg.mention_allowlist = mdconfig.tokens(cells[1])
        elif key == "static_check_patterns" and len(cells) > 1:
            cfg.static_check_patterns = [*STATIC_CHECK_PATTERNS, *mdconfig.tokens(cells[1])]
        grace_attr = _GRACE_ROWS.get(cells[0].lower())
        if grace_attr and len(cells) >= 2:
            days = _days(cells[-1]) or _days(cells[1])
            if days is not None:
                setattr(cfg, grace_attr, days)
    for bad in [p for p in cfg.real_ci_patterns if not _compiles(p)]:
        cfg.warnings.append(f"real_ci_patterns: {bad!r} is not a valid regular expression; ignored")
    cfg.real_ci_patterns = [p for p in cfg.real_ci_patterns if _compiles(p)]
    if not cfg.real_ci_patterns:
        cfg.warnings.append(
            "real_ci_patterns is not configured in pr-management-config.md; every check context counts as "
            "real CI except known bot checks"
        )

    templates = source("pr-management-triage-comment-templates.md")
    if templates is None:
        cfg.warnings.append(
            "pr-management-triage-comment-templates.md not found; URLs render as placeholders"
        )
    for cells in mdconfig.table_rows(templates):
        if len(cells) < 2:
            continue
        match = re.fullmatch(r"`(<[a-z_]+>)`", cells[0])
        if match:
            value = mdconfig.first_token(cells[1])
            if _set(value) and value is not None and "<" not in value:
                cfg.urls[match.group(1)] = value
        elif cells[0].lower().startswith("triage-marker visible link text"):
            value = mdconfig.first_token(cells[1])
            if value:
                cfg.marker = value
    footer = mdconfig.first_fence(mdconfig.section(templates, "AI-attribution footer"))
    if footer:
        cfg.footer = footer.strip("\n")

    check_map = source("pr-management-triage-ci-check-map.md")
    for cells in mdconfig.table_rows(check_map):
        if len(cells) == 3:
            pattern = mdconfig.first_token(cells[0])
            if pattern is None or pattern.lower() == "pattern":
                continue
            url = mdconfig.first_token(cells[2])
            if url == "<upstream_contributing_docs_url>":
                url = cfg.contributing_docs_url
            cfg.check_map.append(CheckCategory(pattern, cells[1], url if url and "<" not in url else None))
        elif len(cells) == 2 and cells[0].lower().startswith("merge conflicts"):
            url = mdconfig.first_token(cells[1])
            cfg.conflicts_url = url if url and "<" not in url else None
    if cfg.conflicts_url is None:
        cfg.conflicts_url = cfg.urls.get("<merge_conflicts_rebase_url>")
    return cfg


def _compiles(pattern: str) -> bool:
    try:
        re.compile(pattern)
    except re.error:
        return False
    return True
