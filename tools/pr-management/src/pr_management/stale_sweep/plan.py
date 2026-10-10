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
"""Thresholds and the selector: what to fetch and which windows apply.

Thresholds come from `<project-config>/stale-sweep-config.md`, read as
`pr_warn_days` / `pr_close_days` / `pr_hard_close_days` — a `` `key` `` table
row or a `key: value` line — so the PR thresholds are independent of the
issue sweep's `warn_days` / `close_days` / `hard_close_days` in the same file.
Defaults are 45 / 90 / 180: PR queues move faster than issue trackers. Inline
`warn:<N>` / `close:<N>` / `hard:<N>` override them.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .. import mdconfig

DEFAULTS = {"warn": 45, "close": 90, "hard": 180}
KEYS = {"warn": "pr_warn_days", "close": "pr_close_days", "hard": "pr_hard_close_days"}
CONFIG_FILE = "stale-sweep-config.md"

#: Save names the skill uses for its reads.
PAGES = "stale-pages.json"
TEAM = "team-members.txt"

_LINE = re.compile(r"^\s*(pr_(?:warn|close|hard_close)_days)\s*:\s*(\d+)\b")


@dataclass
class Plan:
    selector_type: str = "default"
    warn_days: int = DEFAULTS["warn"]
    close_days: int = DEFAULTS["close"]
    hard_close_days: int = DEFAULTS["hard"]
    label_filter: str | None = None
    explicit_numbers: list[int] | None = None
    dry_run: bool = False
    source: str = "framework defaults"
    error: str | None = None
    reads: list[dict[str, Any]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return dict(vars(self))


def _from_config(text: str | None) -> dict[str, int]:
    found: dict[str, int] = {}
    if not text:
        return found
    for name, key in KEYS.items():
        value = mdconfig.key_values(text).get(key)
        if value is not None and value.strip().isdigit():
            found[name] = int(value)
    for line, _inside in mdconfig.live_lines(text):
        match = _LINE.match(line)
        if match:
            name = {v: k for k, v in KEYS.items()}[match.group(1)]
            found.setdefault(name, int(match.group(2)))
    return found


def build(
    tokens: list[str], project_root: Path, config_dir: Path | None, committers_team: str | None
) -> Plan:
    plan = Plan()
    resolver = mdconfig.Resolver(project_root, config_dir)
    configured = _from_config(resolver.read(CONFIG_FILE))
    if configured:
        plan.source = CONFIG_FILE
    values = {**DEFAULTS, **configured}
    overrides: dict[str, int] = {}
    numbers: list[int] = []
    for token in tokens:
        token = token.strip()
        if not token or token == "stale":
            continue
        if token in ("--dry-run", "dry-run"):
            plan.dry_run = True
            continue
        key, sep, rest = token.partition(":")
        if sep and key in ("warn", "close", "hard"):
            if not rest.isdigit():
                plan.error = f"{key}: needs a whole number of days, got {rest!r}"
                continue
            overrides[key] = int(rest)
            continue
        if sep and key == "label":
            if not rest:
                plan.error = "label: needs a label name"
                continue
            plan.label_filter = rest
            continue
        parts = [p for p in re.split(r"[,\s]+", token) if p]
        if parts and all(p.lstrip("#").isdigit() for p in parts):
            numbers += [int(p.lstrip("#")) for p in parts]
            continue
        plan.error = f"unrecognised selector {token!r}"
    if overrides:
        plan.source = "inline override"
    values.update(overrides)
    plan.warn_days, plan.close_days, plan.hard_close_days = values["warn"], values["close"], values["hard"]
    if plan.error is None:
        if min(values.values()) < 0:
            plan.error = "thresholds must not be negative"
        elif plan.warn_days >= plan.close_days:
            plan.error = f"warn_days ({plan.warn_days}) must be less than close_days ({plan.close_days})"
        elif plan.close_days >= plan.hard_close_days:
            plan.error = (
                f"close_days ({plan.close_days}) must be less than hard_close_days ({plan.hard_close_days})"
            )
    if numbers:
        plan.selector_type = "explicit-numbers"
        plan.explicit_numbers = numbers
        plan.reads = [
            {"op": "gql-pr-stale-one", "params": [str(n)], "save": f"stale-one-{n}.json"} for n in numbers
        ]
    elif plan.label_filter:
        plan.selector_type = "label"
        plan.reads = [{"op": "gql-pr-stale-label", "params": [plan.label_filter], "save": PAGES}]
    else:
        plan.reads = [{"op": "gql-pr-stale-open", "params": [], "save": PAGES}]
    if committers_team:
        plan.reads.append({"op": "team-members", "params": [committers_team.split("/")[-1]], "save": TEAM})
    if plan.error:
        plan.reads = []
    return plan
