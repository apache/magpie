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

"""The rules prose ships with the tool, and every finding can reach its own."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from setup_preflight import sections
from setup_preflight.core import Finding, Verdict


def test_every_section_a_finding_can_name_actually_ships() -> None:
    """The contract between `core` and `sections`. A finding whose section
    is missing would reach the agent as a rule-less instruction to act."""
    import setup_preflight.core as core

    source = Path(core.__file__).read_text(encoding="utf-8")
    named = set(re.findall(r'"(step-\d+)"', source))
    assert named, "no sections referenced from core.py — the regex has rotted"
    assert named <= set(sections.available())


def test_an_unknown_section_raises_rather_than_returning_nothing() -> None:
    with pytest.raises(sections.UnknownSection):
        sections.load("step-999")


def test_a_section_is_emitted_once_however_many_findings_name_it() -> None:
    both = sections.for_findings(["step-4", "step-4", "step-3"])
    assert list(both) == ["step-4", "step-3"]


def test_an_ok_verdict_carries_no_rules() -> None:
    payload = json.loads(Verdict("ok").to_json())
    assert payload == {"verdict": "ok"}


def test_an_action_verdict_carries_the_rules_for_its_findings() -> None:
    verdict = Verdict("action", [Finding("skill", "fingerprint-moved", "step-4", {})])
    payload = json.loads(verdict.to_json())
    assert set(payload["rules"]) == {"step-4"}
    assert payload["rules"]["step-4"].startswith("## step-4")


def test_rules_can_be_suppressed_for_a_caller_that_only_wants_the_verdict() -> None:
    verdict = Verdict("action", [Finding("skill", "fingerprint-moved", "step-4", {})])
    assert "rules" not in json.loads(verdict.to_json(with_rules=False))
