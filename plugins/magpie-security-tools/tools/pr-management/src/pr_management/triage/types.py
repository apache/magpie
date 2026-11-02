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
"""The records the triage table and the sweeps share."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Any

from ..model import PR


@dataclass
class Options:
    viewer: str
    now: dt.datetime
    #: "default" (skip collaborators), "all", or "collaborators".
    authors: str = "default"
    session: dict[str, dict[str, Any]] = field(default_factory=dict)
    #: Run Step 0.5 and the Step 5 stale sweeps after the table.
    sweeps: bool = True


@dataclass
class Decision:
    pr: PR
    outcome: str  # "suppressed" | "filtered" | "needs" | "skip" | "act"
    row: str | None = None
    filter: str | None = None
    classification: str | None = None
    action: str | None = None
    reason: str = ""
    details: dict[str, Any] = field(default_factory=dict)
    needs: list[dict[str, Any]] = field(default_factory=list)
