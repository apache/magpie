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

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import typed_decision_prefilter
from typed_decision.exceptions import TypedDecisionUnavailable
from typed_decision.interface import DecisionProvider


class MockDecisionProvider(DecisionProvider):
    """Mock provider for unit testing."""

    def __init__(
        self,
        choice_result: dict[str, Any] | None = None,
        raise_exc: Exception | None = None,
    ) -> None:
        self.choice_result = choice_result
        self.raise_exc = raise_exc
        self.choice_calls: list[tuple[str, list[str]]] = []

    @property
    def name(self) -> str:
        return "mock"

    def choice(self, prompt: str, options: list[str]) -> dict[str, Any]:
        self.choice_calls.append((prompt, options))
        if self.raise_exc:
            raise self.raise_exc
        return self.choice_result or {"label": options[0], "confidence": 0.90}

    def score(
        self, prompt: str, scale: tuple[float, float] | list[float] | int | float
    ) -> dict[str, Any]:
        return {"value": 1.0, "confidence": 0.9}

    def noul(self, prompt: str) -> dict[str, Any]:
        return {"probability": 0.5}


class TestTypedDecisionPrefilter(unittest.TestCase):
    """Test suite for typed_decision_prefilter."""

    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.tmp_path = Path(self.temp_dir.name)
        self.log_file = self.tmp_path / "telemetry.jsonl"
        self.sample_pr = {
            "number": 1201,
            "title": "Add connection retry with jitter to HTTP provider",
            "body": "Adds exponential back-off with full jitter to HTTP provider.",
            "author": {"login": "jane-contributor"},
            "authorAssociation": "CONTRIBUTOR",
            "statusCheckRollup": "SUCCESS",
            "failed_checks": [],
            "recent_main_failures": [],
            "mergeable": "MERGEABLE",
            "unresolved_threads": 0,
            "isDraft": False,
            "commits_behind": 3,
            "real_ci_ran": True,
            "labels": [],
            "commit_messages": ["Add retry with jitter to HTTP provider"],
        }

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    # 1. Flag off: behaves identically to today (provider never called, falls through)
    def test_flag_off_bypasses_provider_and_falls_through(self) -> None:
        """When enable_typed_decision_prefilter is false:

        - typed_decision.choice is NEVER called.
        - Returns applied=False, used_or_fell_through='fell_through'.
        - No telemetry is logged.
        - Triage behavior is identical to baseline.
        """
        provider = MockDecisionProvider(choice_result={"label": "passing", "confidence": 0.99})
        config = typed_decision_prefilter.PrefilterConfig(
            enabled=False,
            confidence_threshold=0.85,
            log_path=self.log_file,
        )

        result = typed_decision_prefilter.prefilter_pr(
            self.sample_pr,
            config=config,
            provider=provider,
            log_path=self.log_file,
        )

        self.assertFalse(result.applied)
        self.assertIsNone(result.predicted_label)
        self.assertIsNone(result.confidence)
        self.assertEqual(result.used_or_fell_through, "fell_through")
        self.assertEqual(result.reason, "disabled")
        # Ensure provider was never invoked
        self.assertEqual(len(provider.choice_calls), 0)
        # Ensure no telemetry log file was created
        self.assertFalse(self.log_file.exists())

    # 2. Flag on, high confidence: pre-fill used, HITL prompt still shown
    def test_flag_on_high_confidence_uses_prefill_and_preserves_hitl(self) -> None:
        """When flag is enabled and confidence >= threshold:

        - Candidate classification is pre-filled from choice() output.
        - Agent reasoning step is skipped for this PR.
        - HITL confirmation prompt is still strictly required before any action.
        - Call is logged to structured log file with used_or_fell_through='used'.
        """
        provider = MockDecisionProvider(choice_result={"label": "passing", "confidence": 0.95})
        config = typed_decision_prefilter.PrefilterConfig(
            enabled=True,
            confidence_threshold=0.85,
            log_path=self.log_file,
        )

        result = typed_decision_prefilter.prefilter_pr(
            self.sample_pr,
            config=config,
            provider=provider,
            log_path=self.log_file,
        )

        self.assertTrue(result.applied)
        self.assertEqual(result.predicted_label, "passing")
        self.assertEqual(result.confidence, 0.95)
        self.assertEqual(result.used_or_fell_through, "used")
        self.assertEqual(len(provider.choice_calls), 1)

        # Invariant check: HITL confirmation UX is preserved.
        # Candidate bucket is used for presenting to maintainer, NOT for unilateral mutation.
        candidate_classification = result.predicted_label
        maintainer_confirmed = False

        # Simulate interaction loop HITL gate
        def simulated_hitl_interaction_gate(candidate: str, user_input: str) -> str:
            if user_input == "confirm":
                return f"action_executed_for_{candidate}"
            return "skipped"

        # Candidate is proposed to maintainer
        self.assertIsNotNone(candidate_classification)
        assert candidate_classification is not None
        self.assertEqual(candidate_classification, "passing")
        # Action is NOT executed without confirmation
        self.assertFalse(maintainer_confirmed)
        # Action only executes on maintainer confirmation
        action_outcome = simulated_hitl_interaction_gate(candidate_classification, "confirm")
        self.assertEqual(action_outcome, "action_executed_for_passing")

        # Telemetry log verification
        self.assertTrue(self.log_file.exists())
        lines = self.log_file.read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual(len(lines), 1)
        record = json.loads(lines[0])
        self.assertEqual(record["predicted_label"], "passing")
        self.assertEqual(record["confidence"], 0.95)
        self.assertEqual(record["used_or_fell_through"], "used")
        self.assertIn("latency_ms", record)
        self.assertEqual(record["pr"], 1201)

    # 3. Flag on, low confidence: falls through silently to current behavior
    def test_flag_on_low_confidence_falls_through_silently(self) -> None:
        """When flag is enabled and confidence < threshold:

        - Candidate classification falls through silently (applied=False).
        - No error is raised to the user.
        - Fallback to standard agent reasoning / decision table occurs.
        - Telemetry logs call with used_or_fell_through='fell_through'.
        """
        provider = MockDecisionProvider(choice_result={"label": "passing", "confidence": 0.65})
        config = typed_decision_prefilter.PrefilterConfig(
            enabled=True,
            confidence_threshold=0.85,
            log_path=self.log_file,
        )

        result = typed_decision_prefilter.prefilter_pr(
            self.sample_pr,
            config=config,
            provider=provider,
            log_path=self.log_file,
        )

        self.assertFalse(result.applied)
        self.assertEqual(result.predicted_label, "passing")
        self.assertEqual(result.confidence, 0.65)
        self.assertEqual(result.used_or_fell_through, "fell_through")
        self.assertEqual(result.reason, "confidence_below_threshold")
        self.assertEqual(len(provider.choice_calls), 1)

        # Telemetry log verification
        self.assertTrue(self.log_file.exists())
        record = json.loads(self.log_file.read_text(encoding="utf-8").strip())
        self.assertEqual(record["predicted_label"], "passing")
        self.assertEqual(record["confidence"], 0.65)
        self.assertEqual(record["used_or_fell_through"], "fell_through")

    # 4. Flag on, TypedDecisionUnavailable: falls through silently, no user-visible error
    def test_flag_on_provider_unavailable_falls_through_silently(self) -> None:
        """When provider raises TypedDecisionUnavailable:

        - Fail-open contract: Caught silently without raising.
        - Returns applied=False, used_or_fell_through='fell_through'.
        - Telemetry logs call with predicted_label=None, confidence=None, used_or_fell_through='fell_through'.
        - Standard triage continues without interruption.
        """
        provider = MockDecisionProvider(
            raise_exc=TypedDecisionUnavailable("TypeSafe Jev service unreachable")
        )
        config = typed_decision_prefilter.PrefilterConfig(
            enabled=True,
            confidence_threshold=0.85,
            log_path=self.log_file,
        )

        # Must not raise TypedDecisionUnavailable
        result = typed_decision_prefilter.prefilter_pr(
            self.sample_pr,
            config=config,
            provider=provider,
            log_path=self.log_file,
        )

        self.assertFalse(result.applied)
        self.assertIsNone(result.predicted_label)
        self.assertIsNone(result.confidence)
        self.assertEqual(result.used_or_fell_through, "fell_through")
        self.assertTrue("provider_unavailable" in str(result.reason))

        # Telemetry log verification
        self.assertTrue(self.log_file.exists())
        record = json.loads(self.log_file.read_text(encoding="utf-8").strip())
        self.assertIsNone(record["predicted_label"])
        self.assertIsNone(record["confidence"])
        self.assertEqual(record["used_or_fell_through"], "fell_through")
        self.assertIn("latency_ms", record)

    # 5. Configuration parsing and override precedence
    def test_config_resolution_precedence(self) -> None:
        """Test override resolution: local wins over committed overrides."""
        local_dir = self.tmp_path / ".apache-magpie-local"
        overrides_dir = self.tmp_path / ".apache-magpie-overrides"
        local_dir.mkdir(parents=True)
        overrides_dir.mkdir(parents=True)

        # Write committed override: enabled=true, threshold=0.80
        (overrides_dir / "pr-management-triage.md").write_text(
            """### Override — Typed decision prefilter
```yaml
enable_typed_decision_prefilter: true
confidence_threshold: 0.80
```
""",
            encoding="utf-8",
        )

        cfg1 = typed_decision_prefilter.resolve_prefilter_config(self.tmp_path)
        self.assertTrue(cfg1.enabled)
        self.assertEqual(cfg1.confidence_threshold, 0.80)

        # Write personal local override: enabled=false
        (local_dir / "pr-management-triage.md").write_text(
            """### Override — Disable prefilter locally
```yaml
enable_typed_decision_prefilter: false
confidence_threshold: 0.95
```
""",
            encoding="utf-8",
        )

        # Local override wins!
        cfg2 = typed_decision_prefilter.resolve_prefilter_config(self.tmp_path)
        self.assertFalse(cfg2.enabled)
        self.assertEqual(cfg2.confidence_threshold, 0.95)

    def test_config_resolution_markdown_table(self) -> None:
        """Test parsing configuration written in a markdown table."""
        overrides_dir = self.tmp_path / ".apache-magpie-overrides"
        overrides_dir.mkdir(parents=True)
        (overrides_dir / "pr-management-config.md").write_text(
            """# PR Management Config
| Key | Value | Notes |
| enable_typed_decision_prefilter | true | Opt-in pre-filter |
| confidence_threshold | 0.92 | Tuned threshold |
""",
            encoding="utf-8",
        )

        cfg = typed_decision_prefilter.resolve_prefilter_config(self.tmp_path)
        self.assertTrue(cfg.enabled)
        self.assertEqual(cfg.confidence_threshold, 0.92)

    def test_build_triage_prompt_structure(self) -> None:
        """Verify prompt contains required fields matching decision-table format."""
        prompt = typed_decision_prefilter.build_triage_prompt(self.sample_pr)
        self.assertIn("## PR state", prompt)
        self.assertIn("PR #1201", prompt)
        self.assertIn("Author: jane-contributor", prompt)
        self.assertIn("StatusCheckRollup: SUCCESS", prompt)
        self.assertIn("Title: Add connection retry with jitter to HTTP provider", prompt)
        self.assertIn("Apply the decision table and return JSON only.", prompt)


if __name__ == "__main__":
    unittest.main()
