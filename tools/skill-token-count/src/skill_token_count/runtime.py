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

"""Explicit, opt-in Claude Code replay benchmark and reported-usage summaries."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def percentile(values: list[int], fraction: float) -> float:
    """Linear interpolation, inclusive endpoints (Hyndman-Fan type 7)."""
    if not values or not 0 <= fraction <= 1:
        raise ValueError("Percentile requires samples and a fraction in [0, 1]")
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lower = math.floor(position)
    upper = math.ceil(position)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def extract_result(payload: Any) -> dict[str, Any]:
    events = payload if isinstance(payload, list) else [payload]
    results = [event for event in events if isinstance(event, dict) and event.get("type") == "result"]
    if len(results) != 1:
        raise ValueError("Expected exactly one terminal CLI result")
    return results[0]


def usage_totals(result: dict[str, Any]) -> dict[str, int]:
    """Use modelUsage totals, including auxiliary CLI calls; never add thinking twice."""
    models = result.get("modelUsage")
    if not isinstance(models, dict) or not models:
        raise ValueError("Missing per-model usage; cannot treat missing telemetry as zero")
    fields = ("inputTokens", "cacheReadInputTokens", "cacheCreationInputTokens", "outputTokens")
    totals = dict.fromkeys(fields, 0)
    for usage in models.values():
        for field in fields:
            value = usage.get(field)
            if type(value) is not int or value < 0:
                raise ValueError(f"Invalid or missing usage field: {field}")
            totals[field] += value
    totals["totalTokens"] = sum(totals.values())
    return totals


def summarize(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    summaries = []
    for mode, skill in sorted({(record["mode"], record["skill"]) for record in records}):
        attempts = [record for record in records if (record["mode"], record["skill"]) == (mode, skill)]
        complete = [record for record in attempts if record["status"] == "success"]
        values = [record["usage"]["totalTokens"] for record in complete]
        summaries.append(
            {
                "mode": mode,
                "skill": skill,
                "attempts": len(attempts),
                "completed": len(complete),
                "failed": len(attempts) - len(complete),
                "distinct_cases": len({record["case"] for record in complete}),
                "p50_total_tokens": percentile(values, 0.5) if values else None,
                "p90_total_tokens": percentile(values, 0.9) if values else None,
                "min_total_tokens": min(values) if values else None,
                "max_total_tokens": max(values) if values else None,
            }
        )
    return summaries


def validate_case_mode(root: Path, case: dict[str, Any]) -> None:
    """Reject mislabeled samples before making a paid model call."""
    entrypoint = root / "skills" / case["skill"] / "SKILL.md"
    source = entrypoint.read_text(encoding="utf-8")
    frontmatter = source.split("---", 2)
    match = (
        re.search(r"^mode:\s*([A-Za-z]+)\s*$", frontmatter[1], re.MULTILINE)
        if len(frontmatter) == 3
        else None
    )
    if match is None or match.group(1) != case["mode"]:
        raise ValueError(f"Mode mismatch for {case['skill']}: fixture={case['mode']}")


def build_prompt(root: Path, corpus: dict[str, Any], case: dict[str, Any]) -> tuple[str, dict[str, str]]:
    validate_case_mode(root, case)
    sources = sorted((root / "skills" / case["skill"]).glob("*.md"))
    if not any(path.name == "SKILL.md" for path in sources):
        raise ValueError("Missing skill entrypoint")
    hashes = {}
    context = []
    for path in sources:
        name = path.relative_to(root).as_posix()
        source = path.read_text(encoding="utf-8")
        hashes[name] = hashlib.sha256(source.encode()).hexdigest()
        context.append(f"DOCUMENT {name}\n{source}")
    prompt = (
        "Execute this synthetic benchmark replay from intake to its final draft/report. "
        "All external tool observations are captured in the fixture below; use those observations "
        "instead of live tools. No tools are enabled and no external action is authorized. "
        "The captured preflight and configuration are benchmark inputs. "
        "Apply the supplied skill's checks and produce its full decision and final artifact, "
        "stopping at the human confirmation boundary. Do not claim to have posted, modified, "
        "or independently fetched anything. If essential data is absent, report the limitation.\n\n"
        + "\n\n".join(context)
        + "\n\nCAPTURED PROJECT CONTEXT\n"
        + json.dumps(corpus["common"], indent=2)
        + "\n\nTASK AND CAPTURED OBSERVATIONS\n"
        + case["input"]
    )
    return prompt, hashes


def markdown_report(document: dict[str, Any]) -> str:
    records = document["records"]
    lines = [
        "<!-- SPDX-License-Identifier: Apache-2.0 -->",
        "",
        "# Runtime replay measurements",
        "",
        f"CLI: `{document['cli_version']}`. Requested model: `{document['model_requested']}`.",
        f"First attempt: `{min(record['started_at'] for record in records)}`.",
        f"Skill source revision: `{document['source_commit']}` (per-file hashes in records).",
        f"Corpus SHA-256: `{document['corpus_sha256']}`.",
        "",
        "Synthetic full-entrypoint replays, ending at the draft/report approval boundary.",
        "Each prompt includes the full SKILL.md and sibling Markdown references, with",
        "project configuration and external tool observations supplied by fixtures.",
        "No live tools, MCP calls, posting, or repository mutations are part of the workload.",
        "These are actual CLI-reported token counts, not cl100k_base file estimates.",
        "",
        "## Sample percentiles",
        "",
        "Sample sizes and distinct cases are shown below. p50/p90 use inclusive linear",
        "interpolation (type 7). These small samples are a pilot, not a population estimate",
        "or an SLA. Repetitions of a scenario are not independent workloads.",
        "Success here means CLI completion, not a correctness grade. Failed attempts",
        "are counted separately and excluded from the completion percentiles.",
        "",
        "| Mode / skill | Attempts | Completed | Failed | Cases | p50 tokens | p90 tokens | Min | Max |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    if document.get("metadata_correction"):
        lines[4:4] = ["Metadata correction: " + document["metadata_correction"]["reason"], ""]
    for row in summarize(records):

        def number(value: Any) -> str:
            return "N/A" if value is None else f"{value:,.1f}".removesuffix(".0")

        lines.append(
            f"| {row['mode']} / {row['skill']} | {row['attempts']} | {row['completed']} | {row['failed']} | "
            f"{row['distinct_cases']} | {number(row['p50_total_tokens'])} | {number(row['p90_total_tokens'])} | "
            f"{number(row['min_total_tokens'])} | {number(row['max_total_tokens'])} |"
        )
    lines += [
        "",
        "## Worked examples",
        "",
        "The first scenario's first attempt for each skill is shown without selection",
        "by cost or quality. Totals include auxiliary CLI calls via `modelUsage`.",
        "Thinking tokens are already in output; cache reads are counted once.",
        "",
        "| Mode / case | Workload | Uncached input | Cache creation | Cache read | Output | Total |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for record in records:
        if record["case"].endswith("-1") and record["repetition"] == 1 and record["status"] == "success":
            usage = record["usage"]
            lines.append(
                f"| {record['mode']} / {record['case']} | {record['workload']} | "
                + " | ".join(
                    f"{usage[key]:,}"
                    for key in (
                        "inputTokens",
                        "cacheCreationInputTokens",
                        "cacheReadInputTokens",
                        "outputTokens",
                        "totalTokens",
                    )
                )
                + " |"
            )
    lines += [
        "",
        "## Interpretation limits",
        "",
        "No tool latency, production issue diversity, follow-up conversation, full code-fix",
        "workflow, or multi-agent pipeline is measured. User/admin CLI configuration and",
        "provider cache behavior can affect overhead. Do not transfer these values to other",
        "models, harnesses, or the planning ranges elsewhere on the mode-economics page.",
        "The CLI's cost fields are list-price telemetry, not a billing record.",
        "",
    ]
    return "\n".join(lines)


def run_case(
    root: Path, corpus: dict[str, Any], case: dict[str, Any], repetition: int, model: str
) -> dict[str, Any]:
    prompt, sources = build_prompt(root, corpus, case)
    command = [
        "claude",
        "-p",
        "--model",
        model,
        "--tools",
        "",
        "--strict-mcp-config",
        "--mcp-config",
        '{"mcpServers":{}}',
        "--no-session-persistence",
        "--output-format",
        "json",
    ]
    record: dict[str, Any] = {
        "case": case["id"],
        "mode": case["mode"],
        "skill": case["skill"],
        "workload": case["workload"],
        "repetition": repetition,
        "started_at": datetime.now(UTC).isoformat(),
        "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
        "sources": sources,
        "status": "error",
    }
    # A fresh directory prevents repository instruction/plugin auto-discovery.
    # User/admin CLI configuration may still apply; this is recorded as a limit.
    with tempfile.TemporaryDirectory(prefix="magpie-runtime-") as directory:
        try:
            process = subprocess.run(
                command, input=prompt, capture_output=True, text=True, cwd=directory, timeout=180
            )
            result = extract_result(json.loads(process.stdout))
            record.update(
                {
                    "status": "success"
                    if process.returncode == 0
                    and not result.get("is_error", True)
                    and result.get("subtype") == "success"
                    else "error",
                    "usage": usage_totals(result),
                    "model_usage": result["modelUsage"],
                    "conversation_usage": result.get("usage"),
                    "duration_ms": result.get("duration_ms"),
                    "turns": result.get("num_turns"),
                    "response": result.get("result", ""),
                }
            )
        except (ValueError, OSError, subprocess.TimeoutExpired) as exc:
            record["error"] = str(exc)
    return record


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--corpus", type=Path, help="Replay corpus; defaults to benchmarks/replay-v1.json")
    parser.add_argument("--run", action="store_true", help="Opt in to paid model calls")
    parser.add_argument("--records", type=Path, required=True)
    parser.add_argument("--model", default="claude-haiku-4-5-20251001")
    parser.add_argument("--repetitions", type=int, default=2)
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    args = parser.parse_args()
    if args.repetitions < 1:
        parser.error("repetitions must be positive")
    if args.run:
        if args.records.exists():
            parser.error("records file already exists; preserve previous measurements")
        root = args.root.resolve()
        corpus_path = args.corpus or root / "tools/skill-token-count/benchmarks/replay-v1.json"
        corpus = json.loads(corpus_path.read_text())
        for case in corpus["cases"]:
            validate_case_mode(root, case)
        records = []
        jobs = [
            (case, repetition) for repetition in range(1, args.repetitions + 1) for case in corpus["cases"]
        ]
        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = [
                pool.submit(run_case, root, corpus, case, repetition, args.model) for case, repetition in jobs
            ]
            for future in futures:
                record = future.result()
                records.append(record)
                print(f"{record['case']} repeat {record['repetition']}: {record['status']}", flush=True)
        document = {
            "schema": 1,
            "kind": "synthetic-full-entrypoint-replay",
            "model_requested": args.model,
            "cli_version": subprocess.check_output(["claude", "--version"], text=True).strip(),
            "source_commit": subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=root, text=True
            ).strip(),
            "corpus_file": corpus_path.name,
            "corpus_sha256": hashlib.sha256(corpus_path.read_bytes()).hexdigest(),
            "records": records,
        }
        args.records.parent.mkdir(parents=True, exist_ok=True)
        args.records.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    else:
        document = json.loads(args.records.read_text())
        records = document["records"]
    print(
        markdown_report(document) if args.format == "markdown" else json.dumps(summarize(records), indent=2),
        end="" if args.format == "markdown" else "\n",
    )
    return int(any(record["status"] != "success" for record in records))


if __name__ == "__main__":
    raise SystemExit(main())
