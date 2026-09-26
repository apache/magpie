#!/usr/bin/env python3
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

"""Opt-in typed-decision pre-filter for pr-management-triage.

Provides an accelerated candidate generation pass using ``typed_decision.choice()``.
When enabled via ``enable_typed_decision_prefilter``:
  - Constructs the agent triage prompt from PR state.
  - Calls ``typed_decision.choice()`` across the triage bucket taxonomy.
  - If confidence >= ``confidence_threshold`` (default 0.85), pre-fills the
    candidate classification, bypassing the agent reasoning step for that PR.
  - On ``TypedDecisionUnavailable``, network error, or low confidence, falls
    through silently to the standard triage decision table / agent reasoning.
  - Every call is logged to a structured JSON Lines file for precision/recall evaluation.
  - Preserves the human-in-the-loop (HITL) confirmation UX unchanged: the candidate
    classification is presented for maintainer review, never executed unilaterally.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import sys
import tempfile
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Ensure typed_decision can be imported even when run standalone
try:
    import typed_decision
    from typed_decision.exceptions import TypedDecisionUnavailable
    from typed_decision.interface import DecisionProvider
except ImportError:
    # Look for tools/typed-decision/src relative to repository root
    _cur = Path(__file__).resolve()
    for parent in _cur.parents:
        _candidate = parent / "tools" / "typed-decision" / "src"
        if _candidate.is_dir():
            sys.path.insert(0, str(_candidate))
            break
    import typed_decision
    from typed_decision.exceptions import TypedDecisionUnavailable
    from typed_decision.interface import DecisionProvider

# The default bucket taxonomy from classify-and-act.md
DEFAULT_TRIAGE_BUCKETS: tuple[str, ...] = (
    "pending_workflow_approval",
    "stale_copilot_review",
    "already_triaged",
    "stale_draft",
    "security_language_signal",
    "deterministic_flag",
    "author_confirmed_ready",
    "awaiting_author_confirmation",
    "stale_review",
    "passing",
)

DEFAULT_CONFIDENCE_THRESHOLD: float = 0.85
CONFIG_FILES: tuple[str, ...] = (
    "pr-management-triage.md",
    "pr-triage.md",
    "pr-management-config.md",
)
OVERRIDE_DIRS: tuple[str, ...] = (
    ".apache-magpie-local",
    ".apache-magpie-overrides",
)

_FENCE_PATTERN = re.compile(r"^```ya?ml[ \t]*\n(.*?)^```[ \t]*$", re.M | re.S)
_COMMENT_PATTERN = re.compile(r"(^|\s)#.*$")
_KV_PATTERN = re.compile(r"^\s*([A-Za-z0-9_-]+)\s*[:=]\s*(.+?)\s*$")
_TABLE_ROW_PATTERN = re.compile(r"^\|\s*([A-Za-z0-9_-]+)\s*\|\s*([^|]+)\s*\|")


@dataclass(frozen=True)
class PrefilterConfig:
    """Configuration knobs for typed-decision pre-filtering."""

    enabled: bool = False
    confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD
    options: tuple[str, ...] = DEFAULT_TRIAGE_BUCKETS
    log_path: Path | None = None
    source_file: Path | None = None


@dataclass(frozen=True)
class PrefilterResult:
    """Outcome of a pre-filter pass on a single PR."""

    applied: bool
    predicted_label: str | None
    confidence: float | None
    latency_ms: float
    used_or_fell_through: str  # "used" or "fell_through"
    reason: str | None = None


def _find_repo_root(start: Path | None = None) -> Path:
    """Find the root of the repository from start directory."""
    cur = (start or Path.cwd()).resolve()
    for parent in [cur, *cur.parents]:
        if (parent / ".git").exists() or (parent / "pyproject.toml").is_file():
            return parent
    return cur


def _parse_bool(val: Any) -> bool:
    if isinstance(val, bool):
        return val
    s = str(val).strip().lower()
    return s in {"true", "1", "yes", "on", "enabled"}


def _parse_float(val: Any, default: float) -> float:
    try:
        f = float(val)
        return max(0.0, min(1.0, f))
    except (ValueError, TypeError):
        return default


def _extract_dict_from_yaml_block(text: str) -> dict[str, str]:
    """Extract flat key-value pairs from a fenced YAML block."""
    result: dict[str, str] = {}
    for match in _FENCE_PATTERN.finditer(text):
        content = match.group(1)
        for raw_line in content.splitlines():
            line = _COMMENT_PATTERN.sub("", raw_line).strip()
            if not line:
                continue
            kv = _KV_PATTERN.match(line)
            if kv:
                k, v = kv.group(1).strip().lower(), kv.group(2).strip().strip("'\"")
                result[k] = v
    return result


def _extract_dict_from_markdown(text: str) -> dict[str, str]:
    """Extract key-value pairs from yaml fences, markdown tables, or plain lines."""
    result = _extract_dict_from_yaml_block(text)
    for raw_line in text.splitlines():
        line = _COMMENT_PATTERN.sub("", raw_line).strip()
        if not line:
            continue
        table_match = _TABLE_ROW_PATTERN.match(line)
        if table_match:
            k, v = table_match.group(1).strip().lower(), table_match.group(2).strip().strip("'\"")
            if k not in {"key", "field", "setting", "parameter"}:
                result.setdefault(k, v)
            continue
        kv = _KV_PATTERN.match(line)
        if kv:
            k, v = kv.group(1).strip().lower(), kv.group(2).strip().strip("'\"")
            result.setdefault(k, v)
    return result


def resolve_prefilter_config(
    project_root: Path | None = None,
    *,
    overrides: Mapping[str, Any] | None = None,
) -> PrefilterConfig:
    """Resolve pre-filter configuration with local-first precedence.

    Resolution order:
      1. Explicit runtime ``overrides`` argument
      2. Environment variables:
         - ``MAGPIE_ENABLE_TYPED_DECISION_PREFILTER``
         - ``MAGPIE_TYPED_DECISION_CONFIDENCE_THRESHOLD``
         - ``MAGPIE_TYPED_DECISION_LOG_PATH``
      3. ``.apache-magpie-local/`` override files (personal, gitignored)
      4. ``.apache-magpie-overrides/`` override files (committed, project-wide)
      5. ``<project_root>/pr-management-config.md`` (adopter config)
      6. Framework defaults: ``enabled=False``, ``confidence_threshold=0.85``
    """
    root = _find_repo_root(project_root)
    found_kv: dict[str, str] = {}
    found_source: Path | None = None

    # Search override layers in order: personal local, then committed overrides
    for layer in OVERRIDE_DIRS:
        for fname in CONFIG_FILES:
            path = root / layer / fname
            if path.is_file():
                try:
                    text = path.read_text(encoding="utf-8")
                    extracted = _extract_dict_from_markdown(text)
                    if "enable_typed_decision_prefilter" in extracted or "confidence_threshold" in extracted:
                        found_kv.update(extracted)
                        found_source = path
                        break
                except OSError:
                    continue
        if found_source:
            break

    # Fallback to project root pr-management-config.md if neither override had it
    if not found_source:
        for fname in CONFIG_FILES:
            path = root / fname
            if path.is_file():
                try:
                    text = path.read_text(encoding="utf-8")
                    extracted = _extract_dict_from_markdown(text)
                    if "enable_typed_decision_prefilter" in extracted or "confidence_threshold" in extracted:
                        found_kv.update(extracted)
                        found_source = path
                        break
                except OSError:
                    continue

    # Env vars take precedence over on-disk files
    env_enabled = os.environ.get("MAGPIE_ENABLE_TYPED_DECISION_PREFILTER")
    if env_enabled is not None:
        found_kv["enable_typed_decision_prefilter"] = env_enabled

    env_threshold = os.environ.get("MAGPIE_TYPED_DECISION_CONFIDENCE_THRESHOLD")
    if env_threshold is not None:
        found_kv["confidence_threshold"] = env_threshold

    env_log_path = os.environ.get("MAGPIE_TYPED_DECISION_LOG_PATH")
    if env_log_path is not None:
        found_kv["log_path"] = env_log_path

    # Runtime overrides take highest precedence
    if overrides:
        for k, v in overrides.items():
            found_kv[k.lower()] = str(v)

    enabled = _parse_bool(found_kv.get("enable_typed_decision_prefilter", False))
    threshold = _parse_float(found_kv.get("confidence_threshold", DEFAULT_CONFIDENCE_THRESHOLD), DEFAULT_CONFIDENCE_THRESHOLD)

    raw_log = found_kv.get("log_path")
    if raw_log:
        log_path = Path(raw_log).resolve()
    else:
        # Default log path inside .apache-magpie-local/logs/
        local_logs = root / ".apache-magpie-local" / "logs"
        log_path = local_logs / "pr-triage-typed-decision.jsonl"

    return PrefilterConfig(
        enabled=enabled,
        confidence_threshold=threshold,
        options=DEFAULT_TRIAGE_BUCKETS,
        log_path=log_path,
        source_file=found_source,
    )


def build_triage_prompt(pr_data: Mapping[str, Any] | str) -> str:
    """Build the agent-facing triage classification prompt for a PR.

    Matches the format consumed by Step 2 decision-table evaluation.
    """
    if isinstance(pr_data, str):
        report = pr_data.strip()
    else:
        number = pr_data.get("number", "0")
        author_val = pr_data.get("author", "")
        author = author_val.get("login", "") if isinstance(author_val, dict) else str(author_val)
        assoc = pr_data.get("authorAssociation", "CONTRIBUTOR")
        rollup = pr_data.get("statusCheckRollup", "SUCCESS")
        failed = pr_data.get("failed_checks", pr_data.get("failedChecks", []))
        recent_failures = pr_data.get("recent_main_failures", pr_data.get("recentMainFailures", []))
        mergeable = pr_data.get("mergeable", "MERGEABLE")
        threads = pr_data.get("unresolved_threads", pr_data.get("unresolvedThreads", 0))
        is_draft = str(pr_data.get("isDraft", pr_data.get("is_draft", False))).lower()
        behind = pr_data.get("commits_behind", pr_data.get("commitsBehind", 0))
        real_ci = str(pr_data.get("real_ci_ran", pr_data.get("realCIRan", True))).lower()
        labels = pr_data.get("labels", [])
        title = pr_data.get("title", "")
        body = pr_data.get("body", "")
        commits = pr_data.get("commit_messages", pr_data.get("commitMessages", []))

        formatted_commits = "\n".join(f'- "{c}"' for c in commits) if commits else '- "Initial commit"'

        report = (
            f"PR #{number}\n"
            f"Author: {author}\n"
            f"AuthorAssociation: {assoc}\n"
            f"StatusCheckRollup: {rollup}\n"
            f"FailedChecks: {json.dumps(failed)}\n"
            f"RecentMainFailures: {json.dumps(recent_failures)}\n"
            f"Mergeable: {mergeable}\n"
            f"UnresolvedThreads: {threads}\n"
            f"IsDraft: {is_draft}\n"
            f"CommitsBehind: {behind}\n"
            f"RealCIRan: {real_ci}\n"
            f"Labels: {json.dumps(labels)}\n\n"
            f"Title: {title}\n"
            f"Body: {body}\n\n"
            f"Commit messages:\n"
            f"{formatted_commits}"
        )

    return f"## PR state\n\n{report}\n\nApply the decision table and return JSON only."


def log_prefilter_call(
    log_path: Path,
    *,
    predicted_label: str | None,
    confidence: float | None,
    latency_ms: float,
    used_or_fell_through: str,
    pr_identifier: Any = None,
    threshold: float | None = None,
    reason: str | None = None,
) -> None:
    """Append a structured JSON line logging the pre-filter call.

    Logs exactly: {predicted_label, confidence, latency_ms, used_or_fell_through}.
    """
    record: dict[str, Any] = {
        "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
        "pr": pr_identifier,
        "predicted_label": predicted_label,
        "confidence": confidence,
        "latency_ms": round(latency_ms, 2),
        "used_or_fell_through": used_or_fell_through,
    }
    if threshold is not None:
        record["threshold"] = threshold
    if reason:
        record["reason"] = reason

    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
    except OSError:
        # Fallback to temp directory if primary log path is not writable
        try:
            fallback = Path(tempfile.gettempdir()) / "pr-triage-typed-decision.jsonl"
            with open(fallback, "a", encoding="utf-8") as f:
                f.write(json.dumps(record) + "\n")
        except OSError:
            pass  # Never crash triage on logging errors


def prefilter_pr(
    pr: Mapping[str, Any] | str,
    *,
    config: PrefilterConfig | None = None,
    provider: DecisionProvider | None = None,
    project_root: Path | None = None,
    log_path: Path | None = None,
) -> PrefilterResult:
    """Execute the opt-in typed-decision pre-filter on a candidate PR.

    Returns:
        PrefilterResult indicating whether pre-fill was applied or fell through.
    """
    resolved_cfg = config or resolve_prefilter_config(project_root)
    effective_log_path = log_path or resolved_cfg.log_path or (
        _find_repo_root(project_root) / ".apache-magpie-local" / "logs" / "pr-triage-typed-decision.jsonl"
    )

    # 1. Flag off: behaves identically to today (no provider call, no prefill)
    if not resolved_cfg.enabled:
        return PrefilterResult(
            applied=False,
            predicted_label=None,
            confidence=None,
            latency_ms=0.0,
            used_or_fell_through="fell_through",
            reason="disabled",
        )

    pr_id = pr.get("number") if isinstance(pr, Mapping) else None
    prompt = build_triage_prompt(pr)
    options = list(resolved_cfg.options)

    t0 = time.perf_counter()
    try:
        # 2. Call typed_decision.choice()
        res = typed_decision.choice(prompt, options, provider=provider)
        latency_ms = (time.perf_counter() - t0) * 1000.0

        label = res.get("label")
        conf = float(res.get("confidence", 0.0))

        # Check threshold
        if conf >= resolved_cfg.confidence_threshold and label in options:
            log_prefilter_call(
                effective_log_path,
                predicted_label=label,
                confidence=conf,
                latency_ms=latency_ms,
                used_or_fell_through="used",
                pr_identifier=pr_id,
                threshold=resolved_cfg.confidence_threshold,
                reason="confidence_above_threshold",
            )
            return PrefilterResult(
                applied=True,
                predicted_label=label,
                confidence=conf,
                latency_ms=latency_ms,
                used_or_fell_through="used",
                reason="confidence_above_threshold",
            )
        else:
            # Low confidence or label not in options: fall through silently
            log_prefilter_call(
                effective_log_path,
                predicted_label=label,
                confidence=conf,
                latency_ms=latency_ms,
                used_or_fell_through="fell_through",
                pr_identifier=pr_id,
                threshold=resolved_cfg.confidence_threshold,
                reason="confidence_below_threshold" if label in options else "unknown_label",
            )
            return PrefilterResult(
                applied=False,
                predicted_label=label,
                confidence=conf,
                latency_ms=latency_ms,
                used_or_fell_through="fell_through",
                reason="confidence_below_threshold" if label in options else "unknown_label",
            )

    except (TypedDecisionUnavailable, Exception) as exc:
        # 4. Fail-open contract: catch TypedDecisionUnavailable / provider errors silently
        latency_ms = (time.perf_counter() - t0) * 1000.0
        log_prefilter_call(
            effective_log_path,
            predicted_label=None,
            confidence=None,
            latency_ms=latency_ms,
            used_or_fell_through="fell_through",
            pr_identifier=pr_id,
            threshold=resolved_cfg.confidence_threshold,
            reason=f"provider_unavailable: {exc}",
        )
        return PrefilterResult(
            applied=False,
            predicted_label=None,
            confidence=None,
            latency_ms=latency_ms,
            used_or_fell_through="fell_through",
            reason=f"provider_unavailable: {exc}",
        )


def main(argv: Sequence[str] | None = None) -> int:
    """CLI helper to evaluate pre-filter on a given PR JSON."""
    parser = argparse.ArgumentParser(description="Typed decision pre-filter for PR triage.")
    parser.add_argument("--pr-json", help="Raw JSON string containing PR attributes")
    parser.add_argument("--file", help="Path to JSON file containing PR attributes")
    parser.add_argument("--show-config", action="store_true", help="Print resolved config and exit")
    args = parser.parse_args(argv)

    cfg = resolve_prefilter_config()
    if args.show_config:
        print(f"Enabled: {cfg.enabled}")
        print(f"Confidence Threshold: {cfg.confidence_threshold}")
        print(f"Log Path: {cfg.log_path}")
        print(f"Config Source: {cfg.source_file}")
        return 0

    if not args.pr_json and not args.file:
        parser.error("Either --pr-json, --file, or --show-config is required.")

    if args.pr_json:
        data = json.loads(args.pr_json)
    else:
        data = json.loads(Path(args.file).read_text(encoding="utf-8"))

    result = prefilter_pr(data, config=cfg)
    print(json.dumps({
        "applied": result.applied,
        "predicted_label": result.predicted_label,
        "confidence": result.confidence,
        "latency_ms": result.latency_ms,
        "used_or_fell_through": result.used_or_fell_through,
        "reason": result.reason,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
