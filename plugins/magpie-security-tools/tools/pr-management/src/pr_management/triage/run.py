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
"""pr-management-triage Step 2 end to end: the decision table, then Step 0.5 and the Step 5 sweeps.

The table (`classify.classify`) and the sweeps (`sweeps.sweep`) stay separate
modules — Sweep 4 re-runs the table live on a candidate — and this module is
the only one that calls both, so neither imports the other's caller.
"""

from __future__ import annotations

from typing import Any

from ..config import Config
from ..model import PR
from ..people import Maintainers
from . import classify as table
from .sweeps import sweep
from .types import Decision, Options


def classify(
    prs: list[PR],
    cfg: Config,
    opts: Options,
    people: Maintainers,
    action_required: dict[str, list[dict[str, Any]]],
    systemic: set[str],
) -> list[Decision]:
    """Every PR's decision: the table's, replaced by a sweep's where one applies."""
    decisions = table.classify(prs, cfg, opts, people, action_required, systemic)
    if not opts.sweeps:
        return decisions
    swept = {d.pr.number: d for d in sweep(prs, decisions, cfg, opts, people, action_required, systemic)}
    return [swept.pop(d.pr.number, d) for d in decisions]
