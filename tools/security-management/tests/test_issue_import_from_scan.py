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
"""`security-management issue-import-from-scan` end to end through the CLI.

The `step-c-bucket` suite stays a model eval (bucketing is judgement); its
`creates_tracker` rule — Golden rule 3 — is pinned here for every bucket.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from security_management.cli import main

TRACKER = "airflow-s/airflow-s"


def run(capsys, *argv: str) -> tuple[int, dict[str, Any]]:
    code = main(["issue-import-from-scan", *argv])
    return code, json.loads(capsys.readouterr().out)


def write(tmp_path: Path, name: str, data: object) -> str:
    path = tmp_path / name
    path.write_text(data if isinstance(data, str) else json.dumps(data), encoding="utf-8")
    return str(path)


@pytest.mark.parametrize(
    ("name", "creates", "action"),
    [
        ("import-as-tracker", True, "tracker"),
        ("PR-worth", False, "pr-or-skip"),
        ("defense-in-depth", False, "pr-or-skip"),
        ("by-design", False, "none"),
        ("INVALID", False, "none"),
        ("duplicate", False, "none"),
        ("already-fixed", False, "none"),
    ],
)
def test_only_import_as_tracker_creates_a_tracker(capsys, name: str, creates: bool, action: str) -> None:
    code, out = run(capsys, "bucket-action", "--bucket", name)
    assert code == 0
    assert (out["creates_tracker"], out["action"]) == (creates, action)


def test_an_unknown_bucket_is_refused(capsys) -> None:
    code, out = run(capsys, "bucket-action", "--bucket", "critical")
    assert code == 2
    assert out["ok"] is False


FINDINGS = [
    {"id": "F-1", "title": "SSRF via connection test", "severity": "Medium"},
    {"id": "F-2", "title": "Unauthenticated RCE | pipe", "severity": "High"},
    {"id": "F-3", "title": "Missing header", "severity": "Low"},
    {"id": "F-4", "title": "Old bug ![x](https://a.example/p)", "severity": "High"},
]
BUCKETS = {
    "F-1": {"bucket": "by-design", "grounding": "Security Model: connection-configuration users are trusted"},
    "F-2": {"bucket": "import-as-tracker", "grounding": "unauthenticated network client reaches the sink"},
    "F-3": {"bucket": "PR-worth", "grounding": ""},
    "F-4": {"bucket": "already-fixed", "grounding": "apache/airflow#61105"},
}


def test_render_report_for_one_scan(capsys, tmp_path) -> None:
    code, out = run(
        capsys,
        "render-report",
        "--findings",
        write(tmp_path, "f.json", FINDINGS),
        "--buckets",
        write(tmp_path, "b.json", BUCKETS),
    )
    assert code == 0
    text = out["text"]
    assert "4 findings: 1 import-as-tracker, 1 PR-worth, 1 by-design, 1 already-fixed." in text
    assert "### import-as-tracker (1)" in text
    assert "| F-2 | Unauthenticated RCE \\| pipe | High |" in text
    assert "[image: x]" in text
    assert "Cross-scan" not in text
    assert out["trackers_possible"] == 1


def test_render_report_refuses_a_disposition_without_grounding(capsys, tmp_path) -> None:
    buckets = {**BUCKETS, "F-1": {"bucket": "by-design", "grounding": ""}}
    code, _ = run(
        capsys,
        "render-report",
        "--findings",
        write(tmp_path, "f.json", FINDINGS),
        "--buckets",
        write(tmp_path, "b.json", buckets),
    )
    assert code == 2


def test_render_report_across_scans_has_percentages_and_severity_analysis(capsys, tmp_path) -> None:
    scans = {"scans": [{"name": "core", "findings": FINDINGS[:2]}, {"name": "ui", "findings": FINDINGS[2:]}]}
    buckets = {"core": {k: BUCKETS[k] for k in ("F-1", "F-2")}, "ui": {k: BUCKETS[k] for k in ("F-3", "F-4")}}
    _, out = run(
        capsys,
        "render-report",
        "--findings",
        write(tmp_path, "f.json", scans),
        "--buckets",
        write(tmp_path, "b.json", buckets),
    )
    text = out["text"]
    assert "## Cross-scan processing report" in text
    assert "| core | 2 | 1 | 0 | 0 | 1 | 0 | 0 |" in text
    assert "| import-as-tracker | 1 | 25% |" in text
    assert "| High | 2 | 1 | 0 |" in text
    assert out["percentages"]["PR-worth"] == "25%"


NUMBERED = [
    {"n": 1, "bucket": "by-design"},
    {"n": 2, "bucket": "import-as-tracker"},
    {"n": 3, "bucket": "PR-worth"},
    {"n": 4, "bucket": "defense-in-depth"},
]


def decide(capsys, tmp_path, reply: str) -> dict[str, Any]:
    _, out = run(
        capsys, "parse-decision", "--input", write(tmp_path, "d.json", {"reply": reply, "findings": NUMBERED})
    )
    return out


def test_all_confirms_only_actionable_findings(capsys, tmp_path) -> None:
    out = decide(capsys, tmp_path, "all")
    assert out["action"] == "apply"
    assert [(c["n"], c["creates_tracker"]) for c in out["confirmed"]] == [(2, True), (3, False), (4, False)]


def test_numbers_and_buckets(capsys, tmp_path) -> None:
    out = decide(capsys, tmp_path, "3, bucket:defense-in-depth")
    assert [c["n"] for c in out["confirmed"]] == [3, 4]
    assert out["skipped"] == [2]


@pytest.mark.parametrize("reply", ["1", "bucket:by-design", "import everything now", "9"])
def test_a_reply_that_names_nothing_actionable_holds_everything(capsys, tmp_path, reply: str) -> None:
    out = decide(capsys, tmp_path, reply)
    assert (out["action"], out["confirmed"]) == ("ambiguous", [])


def test_skip_and_cancel(capsys, tmp_path) -> None:
    assert decide(capsys, tmp_path, "skip")["action"] == "skip"
    assert decide(capsys, tmp_path, "cancel")["action"] == "cancel"


def test_scrub_finds_and_never_rewrites(capsys, tmp_path) -> None:
    report = (
        f"See https://github.com/{TRACKER}/issues/12 and {TRACKER}#13.\n"
        "Allocated CVE-2026-1111; public CVE-2025-0001.\n"
        "This is embargoed until the release. Fixed by apache/airflow#61105, also #14.\n"
        "Reported with N-a3f9d2.\n"
    )
    path = write(tmp_path, "r.md", report)
    _, out = run(
        capsys,
        "scrub",
        "--text",
        path,
        "--tracker",
        TRACKER,
        "--allowed-cves",
        write(tmp_path, "c.json", ["CVE-2025-0001"]),
    )
    kinds = [(h["kind"], h["match"], h["line"]) for h in out["hits"]]
    assert ("private-tracker-ref", f"https://github.com/{TRACKER}/issues/12", 1) in kinds
    assert ("private-tracker-ref", f"{TRACKER}#13", 1) in kinds
    assert ("cve-id", "CVE-2026-1111", 2) in kinds
    assert ("embargo-term", "embargoed", 3) in kinds
    assert ("bare-ref", "#14", 3) in kinds
    assert all(h["match"] != "CVE-2025-0001" for h in out["hits"])
    assert all("61105" not in h["match"] for h in out["hits"])
    assert out["clean"] is False
    assert Path(path).read_text() == report
    _, out = run(
        capsys,
        "scrub",
        "--text",
        write(tmp_path, "ok.md", "All public: apache/airflow#61105.\n"),
        "--tracker",
        TRACKER,
    )
    assert out == {"clean": True, "hits": []}
