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

"""Evaluation harness comparing typed-decision pre-filter against rule-derived reference labels.

Loads a sample of historical PRs, applies the canonical prompt-construction logic
used by pr-management-triage, calls typed_decision.choice(), and calculates:
  - Overall agreement rate vs the dataset's rule-derived reference labels
  - High-confidence agreement rate (>= confidence threshold)
  - Per-class precision, recall, and F1 metrics
  - Confusion matrix
  - Latency percentiles (p50, p90, p95, p99)
  - Cost economics per 100 calls
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
import time
import urllib.error
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

# Ensure typed_decision, privacy-llm/checker, and pr-triage prefilter are importable
_cur = Path(__file__).resolve()
for _parent in [_cur, *_cur.parents]:
    _td_src = _parent / "tools" / "typed-decision" / "src"
    _checker_src = _parent / "tools" / "privacy-llm" / "checker" / "src"
    _prefilter_src = _parent / "plugins" / "magpie-pr-management" / "skills" / "pr-triage" / "scripts"
    if _td_src.is_dir() and str(_td_src) not in sys.path:
        sys.path.insert(0, str(_td_src))
    if _checker_src.is_dir() and str(_checker_src) not in sys.path:
        sys.path.insert(0, str(_checker_src))
    if _prefilter_src.is_dir() and str(_prefilter_src) not in sys.path:
        sys.path.insert(0, str(_prefilter_src))
    if _td_src.is_dir() and _checker_src.is_dir() and _prefilter_src.is_dir():
        break

try:
    import typed_decision  # type: ignore[import-untyped,import-not-found]
    from typed_decision.exceptions import (  # type: ignore[import-untyped,import-not-found]
        TypedDecisionUnavailable,
    )
    from typed_decision.interface import DecisionProvider  # type: ignore[import-untyped,import-not-found]
except ImportError:
    typed_decision = None  # type: ignore[assignment]
    DecisionProvider = object  # type: ignore[misc,assignment]

    class TypedDecisionUnavailable(Exception):  # type: ignore[misc,no-redef]
        pass


PROVIDER_CALL_ERRORS = (
    TypedDecisionUnavailable,
    urllib.error.URLError,
    TimeoutError,
    ConnectionError,
    OSError,
)

from typed_decision_prefilter import (  # type: ignore[import-untyped,import-not-found]  # noqa: E402
    DEFAULT_CONFIDENCE_THRESHOLD,
    DEFAULT_TRIAGE_BUCKETS,
    build_triage_prompt,
)


@dataclass
class EvalSampleResult:
    pr_number: int
    title: str
    ground_truth: str
    predicted: str
    confidence: float
    latency_ms: float
    agreed: bool
    high_confidence: bool
    outcome: str  # "high_confidence" | "low_confidence" | "fell_through"
    error: str | None = None


@dataclass
class ClassMetrics:
    support: int
    true_positive: int
    false_positive: int
    false_negative: int
    precision: float
    recall: float
    f1_score: float


@dataclass
class EvaluationSummary:
    provider_name: str
    total_samples: int
    overall_agreed: int
    overall_accuracy: float
    high_conf_total: int
    high_conf_agreed: int
    high_conf_accuracy: float
    fallthrough_total: int
    fallthrough_rate: float
    error_total: int
    error_rate: float
    latency_p50_ms: float
    latency_p90_ms: float
    latency_p95_ms: float
    latency_p99_ms: float
    latency_mean_ms: float
    cost_per_100: str
    per_class: dict[str, ClassMetrics]
    confusion_matrix: dict[str, dict[str, int]]
    all_classes: list[str]


def evaluate_dataset(
    samples: list[dict[str, Any]],
    provider: DecisionProvider,
    confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
) -> tuple[list[EvalSampleResult], EvaluationSummary]:
    """Run typed_decision evaluation against a list of sample PRs."""
    options = list(DEFAULT_TRIAGE_BUCKETS)
    provider_name = getattr(provider, "name", type(provider).__name__)
    if callable(provider_name):
        provider_name = provider_name()

    results: list[EvalSampleResult] = []
    latencies: list[float] = []

    for item in samples:
        pr_number = item.get("number", 0)
        title = item.get("title", "")
        ground_truth = item.get("ground_truth_label", "passing")

        prompt = build_triage_prompt(item)

        t0 = time.perf_counter()
        error_msg: str | None = None
        predicted = ""
        confidence = 0.0
        try:
            if typed_decision is not None:
                resp = typed_decision.choice(prompt, options, provider=provider)
            else:
                resp = provider.choice(prompt, options)
        except PROVIDER_CALL_ERRORS as exc:
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            error_msg = str(exc)
            resp = None
        else:
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            predicted = resp.get("label", "")
            confidence = float(resp.get("confidence", 0.0))

        if error_msg is not None:
            outcome = "error"
            agreed = False
            high_conf = False
        elif confidence >= confidence_threshold:
            outcome = "high_confidence"
            agreed = predicted == ground_truth
            high_conf = True
        else:
            outcome = "low_confidence"
            agreed = predicted == ground_truth
            high_conf = False

        res = EvalSampleResult(
            pr_number=pr_number,
            title=title,
            ground_truth=ground_truth,
            predicted=predicted,
            confidence=confidence,
            latency_ms=round(elapsed_ms, 2),
            agreed=agreed,
            high_confidence=high_conf,
            outcome=outcome,
            error=error_msg,
        )
        results.append(res)
        if error_msg is None:
            latencies.append(elapsed_ms)

    # Compute overall statistics
    total = len(results)
    overall_agreed = sum(1 for r in results if r.agreed)
    overall_accuracy = (overall_agreed / total) if total > 0 else 0.0

    high_conf_items = [r for r in results if r.high_confidence]
    high_conf_total = len(high_conf_items)
    high_conf_agreed = sum(1 for r in high_conf_items if r.agreed)
    high_conf_accuracy = (high_conf_agreed / high_conf_total) if high_conf_total > 0 else 0.0

    low_conf_items = [r for r in results if r.outcome == "low_confidence"]
    fallthrough_total = len(low_conf_items)
    fallthrough_rate = (fallthrough_total / total) if total > 0 else 0.0

    error_items = [r for r in results if r.outcome == "error"]
    error_total = len(error_items)
    error_rate = (error_total / total) if total > 0 else 0.0

    # Latency percentiles
    sorted_lat = sorted(latencies)
    p50 = float(statistics.median(sorted_lat)) if sorted_lat else 0.0
    p90 = _percentile(sorted_lat, 0.90) if sorted_lat else 0.0
    p95 = _percentile(sorted_lat, 0.95) if sorted_lat else 0.0
    p99 = _percentile(sorted_lat, 0.99) if sorted_lat else 0.0
    mean_lat = float(statistics.mean(sorted_lat)) if sorted_lat else 0.0

    # Classes in ground truth and predictions (excluding empty fall-throughs)
    present_classes = sorted(
        {r.ground_truth for r in results} | {r.predicted for r in results if r.predicted}
    )

    # Confusion matrix: [ground_truth][predicted] -> count
    confusion_matrix: dict[str, dict[str, int]] = {
        gt: dict.fromkeys(present_classes, 0) for gt in present_classes
    }
    for r in results:
        if r.predicted and r.predicted in confusion_matrix[r.ground_truth]:
            confusion_matrix[r.ground_truth][r.predicted] += 1

    # Per-class metrics
    per_class: dict[str, ClassMetrics] = {}
    for cls_name in present_classes:
        tp = confusion_matrix[cls_name][cls_name]
        fn = sum(confusion_matrix[cls_name][p] for p in present_classes if p != cls_name)
        fp = sum(confusion_matrix[g][cls_name] for g in present_classes if g != cls_name)
        support = tp + fn

        precision = (tp / (tp + fp)) if (tp + fp) > 0 else 0.0
        recall = (tp / (tp + fn)) if (tp + fn) > 0 else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0

        per_class[cls_name] = ClassMetrics(
            support=support,
            true_positive=tp,
            false_positive=fp,
            false_negative=fn,
            precision=round(precision, 4),
            recall=round(recall, 4),
            f1_score=round(f1, 4),
        )

    summary = EvaluationSummary(
        provider_name=provider_name,
        total_samples=total,
        overall_agreed=overall_agreed,
        overall_accuracy=round(overall_accuracy, 4),
        high_conf_total=high_conf_total,
        high_conf_agreed=high_conf_agreed,
        high_conf_accuracy=round(high_conf_accuracy, 4),
        fallthrough_total=fallthrough_total,
        fallthrough_rate=round(fallthrough_rate, 4),
        error_total=error_total,
        error_rate=round(error_rate, 4),
        latency_p50_ms=round(p50, 1),
        latency_p90_ms=round(p90, 1),
        latency_p95_ms=round(p95, 1),
        latency_p99_ms=round(p99, 1),
        latency_mean_ms=round(mean_lat, 1),
        cost_per_100="TBD (early-access pricing not public)",
        per_class=per_class,
        confusion_matrix=confusion_matrix,
        all_classes=present_classes,
    )

    return results, summary


def _percentile(data: list[float], p: float) -> float:
    """Calculate percentile value from sorted data."""
    if not data:
        return 0.0
    k = (len(data) - 1) * p
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return data[int(k)]
    d0 = data[int(f)] * (c - k)
    d1 = data[int(c)] * (k - f)
    return float(d0 + d1)


def generate_markdown_report(
    summary: EvaluationSummary,
    *,
    sample_size: int,
    date_range: str,
    pr_range: str,
    methodology_notes: str | None = None,
) -> str:
    """Format full markdown evaluation report conforming to Magpie documentation standards."""
    notes = methodology_notes or (
        "Ground truth labels in this dataset were derived from rule-based heuristics over historical "
        "PR attributes (CI check rollup, mergeability state, failed checks, unresolved review threads, "
        "draft status, and security keyword patterns in title/commit messages/body) according to the "
        "decision taxonomy in `tools/pr-management/src/pr_management/triage/classify.py`."
    )

    # Format confusion matrix markdown table
    classes = summary.all_classes
    cm_header = "| True \\ Pred | " + " | ".join(classes) + " |"
    cm_sep = "|---|" + "|".join("---" for _ in classes) + "|"
    cm_rows = []
    for gt in classes:
        row_vals = [str(summary.confusion_matrix[gt][pred]) for pred in classes]
        cm_rows.append(f"| **{gt}** | " + " | ".join(row_vals) + " |")
    cm_table = "\n".join([cm_header, cm_sep, *cm_rows])

    # Format per-class metrics markdown table
    pc_header = "| Triage Class | Support | Precision | Recall | F1-Score |"
    pc_sep = "|---|---|---|---|---|"
    pc_rows = []
    for cls_name, m in summary.per_class.items():
        pc_rows.append(
            f"| `{cls_name}` | {m.support} | {m.precision * 100:.1f}% | {m.recall * 100:.1f}% | {m.f1_score:.3f} |"
        )
    pc_table = "\n".join([pc_header, pc_sep, *pc_rows])

    overall_pct = summary.overall_accuracy * 100
    high_conf_accuracy_pct = summary.high_conf_accuracy * 100
    high_conf_share_pct = (
        (summary.high_conf_total / summary.total_samples * 100) if summary.total_samples > 0 else 0.0
    )
    fallthrough_pct = summary.fallthrough_rate * 100
    error_pct = summary.error_rate * 100

    error_bullet = (
        f"\n- **Provider Errors:** **{summary.error_total}** ({error_pct:.2f}%)"
        if summary.error_total > 0
        else ""
    )

    return f"""<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Typed-Decision PR Triage Evaluation](#typed-decision-pr-triage-evaluation)
  - [Executive Summary](#executive-summary)
  - [Methodology](#methodology)
    - [1. Sample Selection](#1-sample-selection)
    - [2. Ground Truth Definition](#2-ground-truth-definition)
    - [3. Prompt Construction & Classifier Execution](#3-prompt-construction--classifier-execution)
  - [Evaluation Results](#evaluation-results)
    - [Overall Performance](#overall-performance)
    - [Per-Class Precision and Recall](#per-class-precision-and-recall)
    - [Confusion Matrix](#confusion-matrix)
  - [Latency and Cost Economics](#latency-and-cost-economics)
    - [Latency Distribution](#latency-distribution)
    - [Cost Estimation](#cost-estimation)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

# Typed-Decision PR Triage Evaluation

Evaluation report comparing the `typed-decision` pre-filter (`typed_decision.choice()`)
against sample dataset ground truth labels on `apache/magpie`.

## Executive Summary

- **Provider:** {summary.provider_name}
- **Sample Size:** {sample_size} historical pull requests
- **Date Range:** {date_range} (PRs {pr_range})
- **Overall Agreement Rate:** **{overall_pct:.2f}%** ({summary.overall_agreed}/{summary.total_samples})
- **High-Confidence Agreement Rate (>= {DEFAULT_CONFIDENCE_THRESHOLD}):** **{high_conf_accuracy_pct:.2f}%** ({summary.high_conf_agreed}/{summary.high_conf_total})
- **Fall-Through Rate (< {DEFAULT_CONFIDENCE_THRESHOLD}):** **{fallthrough_pct:.2f}%** ({summary.fallthrough_total}/{summary.total_samples}){error_bullet}
- **Latency (p50 / p95):** **{summary.latency_p50_ms:.1f}ms** / **{summary.latency_p95_ms:.1f}ms**
- **Estimated Cost per 100 Calls:** **{summary.cost_per_100}**

---

## Methodology

### 1. Sample Selection
A sample of **{sample_size} pull requests** was extracted from `apache/magpie`
spanning the date range **{date_range}** (PRs **{pr_range}**).
The dataset captures diverse contributor associations (`MEMBER`, `CONTRIBUTOR`, `COLLABORATOR`, `NONE`),
mergeability states, CI status check rollups, and author review interactions.

### 2. Ground Truth Definition
{notes}
- **`passing`**: All CI checks green, branch mergeable (`MERGEABLE`), zero unresolved review threads.
- **`deterministic_flag`**: Merge conflicts (`CONFLICTING`), failed CI test runs, static check failures, or unresolved threads.
- **`author_confirmed_ready`**: Explicit contributor confirmation following maintainer engagement.
- **`security_language_signal`**: Matches canonical vulnerability disclosure patterns (CVE IDs, exploit, RCE).
- **`stale_review`**: Author pushed new commits following a `CHANGES_REQUESTED` review.
- **`stale_draft`**: Inactive draft PR with extended author silence.

### 3. Prompt Construction & Classifier Execution
Each sample was formatted into the exact agent-facing prompt specified by
`plugins/magpie-pr-management/skills/pr-triage/scripts/typed_decision_prefilter.py`.
External contributor-authored content (`<pr-title>`, `<pr-body>`, `<commit-messages>`)
was enclosed in `<untrusted-external-data>` XML tags with HTML entity escaping to prevent prompt injection.
The candidate choice taxonomy was provided as `DEFAULT_TRIAGE_BUCKETS`.

---

## Evaluation Results

### Overall Performance

| Metric | Value |
|---|---|
| Total Evaluated Samples | **{summary.total_samples}** |
| Overall Agreement Rate | **{overall_pct:.2f}%** ({summary.overall_agreed}/{summary.total_samples}) |
| High-Confidence Submissions (>= {DEFAULT_CONFIDENCE_THRESHOLD}) | **{summary.high_conf_total}** ({high_conf_share_pct:.1f}%) |
| High-Confidence Agreement Rate | **{high_conf_accuracy_pct:.2f}%** ({summary.high_conf_agreed}/{summary.high_conf_total}) |
| Fall-Through Rate (< {DEFAULT_CONFIDENCE_THRESHOLD}) | **{fallthrough_pct:.2f}%** ({summary.fallthrough_total}/{summary.total_samples}) |
| Provider Errors | **{summary.error_total}** ({error_pct:.1f}%) |

### Per-Class Precision and Recall

{pc_table}

### Confusion Matrix

{cm_table}

*Rows represent dataset ground truth; columns represent model predictions.*

---

## Latency and Cost Economics

### Latency Distribution

| Percentile | Latency (ms) |
|---|---|
| **p50 (Median)** | **{summary.latency_p50_ms:.1f} ms** |
| **p90** | **{summary.latency_p90_ms:.1f} ms** |
| **p95** | **{summary.latency_p95_ms:.1f} ms** |
| **p99** | **{summary.latency_p99_ms:.1f} ms** |
| **Mean** | **{summary.latency_mean_ms:.1f} ms** |

### Cost Estimation
- **Estimated Cost per 100 Calls:** **{summary.cost_per_100}**
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run evaluation comparing typed-decision pre-filter against rule-derived reference labels."
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path("tools/skill-evals/evals/pr-management-triage/historical-sample.json"),
        help="Path to JSON dataset of sampled PRs with ground truth labels.",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=DEFAULT_CONFIDENCE_THRESHOLD,
        help=f"Confidence threshold (default: {DEFAULT_CONFIDENCE_THRESHOLD}).",
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=None,
        help="Optional path to write full evaluation output results as JSON.",
    )
    parser.add_argument(
        "--output-markdown",
        type=Path,
        default=None,
        help="Optional path to write generated markdown report.",
    )
    parser.add_argument(
        "--provider",
        type=str,
        default=None,
        help="Decision provider name to use (defaults to configured live provider).",
    )
    args = parser.parse_args(argv)

    if not args.dataset.exists():
        print(f"Dataset file not found: {args.dataset}", file=sys.stderr)
        return 1

    with open(args.dataset, encoding="utf-8") as f:
        samples = json.load(f)

    if typed_decision is None:
        print(
            "Error: typed_decision package is not available. Please ensure typed-decision is installed.",
            file=sys.stderr,
        )
        return 1

    try:
        provider = (
            typed_decision.get_provider(args.provider) if args.provider else typed_decision.get_provider()
        )
    except Exception as e:
        print(
            f"Error: Unable to initialize live DecisionProvider ({e}).\n"
            "A live provider (e.g. TYPESAFE_API_KEY) is required by default to run evaluations. "
            "For unit testing, pass a test double provider directly to evaluate_dataset().",
            file=sys.stderr,
        )
        return 1

    results, summary = evaluate_dataset(samples, provider=provider, confidence_threshold=args.threshold)

    if summary.total_samples > 0 and summary.error_total == summary.total_samples:
        print(
            f"Error: All {summary.total_samples} samples encountered provider errors. Evaluation failed.",
            file=sys.stderr,
        )
        return 1

    dates = [s["createdAt"][:10] for s in samples if s.get("createdAt")]
    date_range = f"{min(dates)} to {max(dates)}" if dates else "2026-08-04 to 2026-10-04"
    numbers = [s["number"] for s in samples if s.get("number")]
    pr_range = f"#{min(numbers)} to #{max(numbers)}" if numbers else "#1068 to #1507"

    report_md = generate_markdown_report(
        summary,
        sample_size=len(samples),
        date_range=date_range,
        pr_range=pr_range,
    )

    if args.output_markdown:
        args.output_markdown.parent.mkdir(parents=True, exist_ok=True)
        args.output_markdown.write_text(report_md, encoding="utf-8")
        print(f"Wrote report to {args.output_markdown}")

    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        dump_data = {
            "summary": asdict(summary),
            "results": [asdict(r) for r in results],
        }
        with open(args.output_json, "w", encoding="utf-8") as f:
            json.dump(dump_data, f, indent=2)
        print(f"Wrote JSON results to {args.output_json}")

    print("\n--- Evaluation Summary ---")
    print(f"Total samples: {summary.total_samples}")
    print(
        f"Overall agreement rate: {summary.overall_accuracy * 100:.2f}% ({summary.overall_agreed}/{summary.total_samples})"
    )
    print(
        f"High-confidence agreement: {summary.high_conf_accuracy * 100:.2f}% ({summary.high_conf_agreed}/{summary.high_conf_total})"
    )
    print(
        f"Fall-through (low confidence): {summary.fallthrough_total} ({summary.fallthrough_rate * 100:.1f}%)"
    )
    if summary.error_total > 0:
        print(f"Provider errors: {summary.error_total} ({summary.error_rate * 100:.1f}%)")
    print(f"Latency p50 / p95: {summary.latency_p50_ms:.1f}ms / {summary.latency_p95_ms:.1f}ms")
    return 0


if __name__ == "__main__":
    sys.exit(main())
