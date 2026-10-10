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
"""The quick-merge configuration, from `<project-config>/pr-management-quick-merge-config.md`.

Thresholds and switches are `` | `key` | value | `` rows (the value column is
the one the adopter edits; a missing row keeps the framework default). The
three glob lists are the fenced blocks under the headings that name them;
`#` lines and unfilled `<placeholder>` lines are not globs.
"""

from __future__ import annotations

import re
import shlex
from dataclasses import dataclass, field
from pathlib import Path

from .. import mdconfig

CONFIG_FILE = "pr-management-quick-merge-config.md"
DEFAULT_MERGE_TEMPLATE = "gh pr merge <N> --squash --repo <repo>"


@dataclass
class QuickMergeConfig:
    max_churn: int = 20
    max_files: int = 3
    default_tiers: tuple[str, ...] = ("A", "B")
    tier_a: list[str] = field(default_factory=list)
    tier_b: list[str] = field(default_factory=list)
    deny: list[str] = field(default_factory=list)
    merge_template: str = DEFAULT_MERGE_TEMPLATE
    enable_approve: bool = True
    approve_requires_diff_view: bool = True
    approve_body: str | None = None
    source: str | None = None
    warnings: list[str] = field(default_factory=list)


def _bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in ("true", "yes", "1", "on")


def _globs(text: str | None, key: str, warnings: list[str]) -> list[str]:
    block = mdconfig.first_fence(mdconfig.section(text, key))
    found: list[str] = []
    for line in (block or "").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "<" in line and ">" in line:
            warnings.append(f"{key}: {line!r} is an unfilled placeholder; ignored — fill it in")
            continue
        found.append(line)
    return found


def load(project_root: Path, config_dir: Path | None = None) -> QuickMergeConfig:
    resolver = mdconfig.Resolver(project_root, config_dir)
    cfg = QuickMergeConfig()
    path = resolver.find(CONFIG_FILE)
    cfg.source = str(path) if path else None
    text = resolver.read(CONFIG_FILE)
    if text is None:
        cfg.warnings.append(
            f"{CONFIG_FILE} not found in <project-config>; no path is allowed, so nothing qualifies"
        )
        return cfg
    values = mdconfig.key_values(text)
    for key, attr in (("max_churn", "max_churn"), ("max_files", "max_files")):
        raw = values.get(key)
        if raw is not None:
            if re.fullmatch(r"\d+", raw):
                setattr(cfg, attr, int(raw))
            else:
                cfg.warnings.append(f"{key}: {raw!r} is not a number; using {getattr(cfg, attr)}")
    tiers = values.get("default_tiers")
    if tiers:
        picked = tuple(t.strip().upper() for t in tiers.split(",") if t.strip().upper() in ("A", "B"))
        cfg.default_tiers = picked or cfg.default_tiers
    template = values.get("merge_command_template")
    if template:
        cfg.merge_template = template
    cfg.enable_approve = _bool(values.get("enable_approve"), True)
    cfg.approve_requires_diff_view = _bool(values.get("approve_requires_diff_view"), True)
    cfg.approve_body = values.get("approve_body") or None
    cfg.tier_a = _globs(text, "tier_a_allow_globs", cfg.warnings)
    cfg.tier_b = _globs(text, "tier_b_allow_globs", cfg.warnings)
    cfg.deny = _globs(text, "deny_globs", cfg.warnings)
    both = sorted((set(cfg.tier_a) | set(cfg.tier_b)) & set(cfg.deny))
    if both:
        cfg.warnings.append(f"globs in both an allow list and deny_globs (deny wins): {both}")
    try:
        tokens = shlex.split(cfg.merge_template)
    except ValueError:
        tokens = []
    if not tokens or tokens[0] != "gh" or "<N>" not in tokens:
        cfg.warnings.append(
            f"merge_command_template {cfg.merge_template!r} must be a `gh …` command with a <N> token; using "
            f"{DEFAULT_MERGE_TEMPLATE!r}"
        )
        cfg.merge_template = DEFAULT_MERGE_TEMPLATE
    return cfg
