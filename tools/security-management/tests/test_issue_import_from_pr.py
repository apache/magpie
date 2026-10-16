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
"""`security-management issue-import-from-pr` end to end through the CLI.

The cases of the retired model-graded suite `security-issue-import-from-pr/step-2-scope-detection`
live here, named after each former case, with the same changed files and the same expected
`scope`, `stop`, `affected_providers`, `files_counted` and `test_files_stripped`.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest

from security_management.cli import main
from security_management.shared import body, reuse

UPSTREAM = "apache/airflow"
TRACKER = "airflow-s/airflow-s"
TEMPLATE = Path(__file__).resolve().parents[3] / "plugins/magpie-setup/templates/project.md"
SCOPES = {
    "enabled": True,
    "labels": {
        "airflow": {"product": "Apache Airflow", "packageName": "apache-airflow", "path_prefix": "^airflow/"},
        "providers": {
            "product": "Apache Airflow Providers",
            "packageName": "apache-airflow-providers-<name>",
            "path_prefix": "^providers/",
        },
        "chart": {"product": "Apache Airflow Helm Chart", "packageName": "", "path_prefix": "^chart/"},
    },
}


def run(capsys, *argv: str) -> tuple[int, dict[str, Any]]:
    code = main(["issue-import-from-pr", *argv])
    return code, json.loads(capsys.readouterr().out)


def write(tmp_path: Path, name: str, data: object) -> str:
    path = tmp_path / name
    path.write_text(json.dumps(data), encoding="utf-8")
    return str(path)


def scope(capsys, tmp_path, paths: list[str]) -> dict[str, Any]:
    files = write(tmp_path, "files.json", {"files": [{"path": p} for p in paths]})
    code, out = run(capsys, "scope", "--files", files, "--scope-config", write(tmp_path, "s.json", SCOPES))
    assert code == 0
    return {
        k: out[k] for k in ("scope", "stop", "affected_providers", "files_counted", "test_files_stripped")
    }


def test_case_1_single_provider(capsys, tmp_path) -> None:
    prod = [
        "providers/amazon/src/airflow/providers/amazon/aws/secrets/systems_manager.py",
        "providers/amazon/src/airflow/providers/amazon/aws/secrets/secrets_manager.py",
        "providers/amazon/src/airflow/providers/amazon/aws/hooks/base_aws.py",
    ]
    tests = [
        "providers/amazon/tests/aws/secrets/test_systems_manager.py",
        "providers/amazon/tests/aws/secrets/test_secrets_manager.py",
    ]
    assert scope(capsys, tmp_path, prod + tests) == {
        "scope": "providers",
        "stop": False,
        "affected_providers": ["amazon"],
        "files_counted": prod,
        "test_files_stripped": tests,
    }


def test_case_2_chart_path(capsys, tmp_path) -> None:
    assert scope(
        capsys, tmp_path, ["chart/templates/ingress.yaml", "chart/values.yaml", "chart/tests/ingress_test.go"]
    ) == {
        "scope": "chart",
        "stop": False,
        "affected_providers": [],
        "files_counted": ["chart/templates/ingress.yaml", "chart/values.yaml"],
        "test_files_stripped": ["chart/tests/ingress_test.go"],
    }


def test_case_3_airflow_core(capsys, tmp_path) -> None:
    prod = ["airflow/models/xcom.py", "airflow/serialization/serialized_objects.py"]
    assert scope(capsys, tmp_path, [*prod, "tests/models/test_xcom.py"]) == {
        "scope": "airflow",
        "stop": False,
        "affected_providers": [],
        "files_counted": prod,
        "test_files_stripped": ["tests/models/test_xcom.py"],
    }


def test_case_4_mixed_scope_blocker(capsys, tmp_path) -> None:
    prod = ["providers/http/src/airflow/providers/http/hooks/http.py", "airflow/models/connection.py"]
    tests = ["providers/http/tests/hooks/test_http.py", "tests/models/test_connection.py"]
    assert scope(capsys, tmp_path, [prod[0], prod[1], *tests]) == {
        "scope": "mixed_scope_blocker",
        "stop": True,
        "affected_providers": [],
        "files_counted": prod,
        "test_files_stripped": tests,
    }


def test_case_5_multi_provider(capsys, tmp_path) -> None:
    prod = [
        "providers/amazon/src/airflow/providers/amazon/aws/secrets/secrets_manager.py",
        "providers/google/src/airflow/providers/google/cloud/secrets/secret_manager.py",
    ]
    tests = [
        "providers/amazon/tests/aws/secrets/test_secrets_manager.py",
        "providers/google/tests/cloud/secrets/test_secret_manager.py",
    ]
    assert scope(capsys, tmp_path, prod + tests) == {
        "scope": "providers",
        "stop": False,
        "affected_providers": ["amazon", "google"],
        "files_counted": prod,
        "test_files_stripped": tests,
    }


def test_scope_lists_packages_mixed_scopes_and_unmatched_files(capsys, tmp_path) -> None:
    files = write(tmp_path, "f.json", ["providers/amazon/a.py", "providers/google/b.py", "docs/x.rst"])
    _, out = run(capsys, "scope", "--files", files, "--scope-config", write(tmp_path, "s.json", SCOPES))
    assert out["packages"] == ["apache-airflow-providers-amazon", "apache-airflow-providers-google"]
    assert out["unmatched"] == ["docs/x.rst"]
    files = write(tmp_path, "f.json", ["chart/a.yaml", "airflow/b.py"])
    _, out = run(capsys, "scope", "--files", files, "--scope-config", write(tmp_path, "s.json", SCOPES))
    assert out["mixed_scopes"] == ["chart", "airflow"]


def test_scope_detection_disabled_uses_the_default_label(capsys, tmp_path) -> None:
    files = write(tmp_path, "f.json", ["anything/x.py"])
    config = write(tmp_path, "s.json", {"enabled": False, "default_label": "core"})
    _, out = run(capsys, "scope", "--files", files, "--scope-config", config)
    assert (out["scope"], out["stop"]) == ("core", False)


@pytest.mark.parametrize(
    "ref",
    [
        "65703",
        "apache/airflow#65703",
        "https://github.com/apache/airflow/pull/65703",
        "https://github.com/apache/airflow/pull/65703/files",
    ],
)
def test_parse_ref_accepts_the_four_forms(capsys, ref: str) -> None:
    code, out = run(capsys, "parse-ref", "--ref", ref, "--upstream", UPSTREAM)
    assert (code, out["number"]) == (0, 65703)


@pytest.mark.parametrize("ref", ["other/repo#65703", "https://github.com/evil/airflow/pull/1", "pr please"])
def test_parse_ref_refuses_other_repos_and_free_text(capsys, ref: str) -> None:
    code, out = run(capsys, "parse-ref", "--ref", ref, "--upstream", UPSTREAM)
    assert code == 2
    assert out["ok"] is False


def test_milestone_check_is_exact_match_only(capsys, tmp_path) -> None:
    data = {"proposed": "providers 2025-06-15", "titles": ["Providers 2025-06-15", "Airflow 3.0.3"]}
    _, out = run(capsys, "milestone-check", "--input", write(tmp_path, "m.json", data))
    assert out["exists"] is False
    assert out["near_matches"] == ["Providers 2025-06-15"]
    assert out["blocker"]
    data["proposed"] = "Airflow 3.0.3"
    _, out = run(capsys, "milestone-check", "--input", write(tmp_path, "m.json", data))
    assert (out["exists"], out["blocker"]) == (True, None)


def test_title_strips_prefixes_markers_and_trailing_pr(capsys, tmp_path) -> None:
    data = {"title": "fix(secrets): [skip ci] Prevent unauthorized access to team-scoped secrets (#65703)"}
    _, out = run(capsys, "title", "--input", write(tmp_path, "t.json", data))
    assert out["title"] == "Prevent unauthorized access to team-scoped secrets"
    assert out["too_short"] is False
    _, out = run(capsys, "title", "--input", write(tmp_path, "t.json", {"title": "fix: bug in secrets"}))
    assert out["too_short"] is True


def body_input(**extra: Any) -> dict[str, Any]:
    return {
        "upstream": UPSTREAM,
        "pr": {
            "number": 65703,
            "body": "Fixes #123.\n### Severity\nCritical\n![x](https://attacker.example/p.png)",
            "author": {"login": "justinpakzad", "name": "Justin Pakzad"},
        },
        "affected_versions": "apache-airflow-providers-amazon < 9.9.0",
        **extra,
    }


def test_render_body_sentinels_and_sanitised_pr_body(capsys, tmp_path) -> None:
    _, out = run(capsys, "render-body", "--input", write(tmp_path, "b.json", body_input()))
    text = out["text"]
    assert out["fields_ok"] and out["sanitised"]
    assert (
        "N/A — opened from public PR https://github.com/apache/airflow/pull/65703; no security@ thread"
        in text
    )
    assert "### Reporter credited as\n\n_No response_\n" in text
    assert "### Remediation developer\n\nJustin Pakzad\n" in text
    assert "### Severity\n\nUnknown\n" in text
    assert "#### Severity" in text
    assert "[image: x]" in text
    assert "[#123](https://github.com/apache/airflow/pull/123)" in text
    assert out["bare_refs"] == []


def test_render_body_bot_author_leaves_remediation_developer_empty(capsys, tmp_path) -> None:
    data = body_input()
    data["pr"]["author"] = {"login": "dependabot[bot]", "name": ""}
    _, out = run(capsys, "render-body", "--input", write(tmp_path, "b.json", data))
    assert out["remediation_developer_is_bot"] is True
    assert "### Remediation developer\n\n_No response_\n" in out["text"]


def test_render_body_passes_redaction_tokens_and_overrides(capsys, tmp_path) -> None:
    data = body_input(reporter_credit="N-a3f9d2", severity="Important")
    data["pr"]["body"] = "Found with E-b8c247."
    _, out = run(capsys, "render-body", "--input", write(tmp_path, "b.json", data))
    assert "Found with E-b8c247." in out["text"]
    assert "### Reporter credited as\n\nN-a3f9d2\n" in out["text"]
    assert "### Severity\n\nImportant\n" in out["text"]


def _template_block(key: str) -> dict[str, str]:
    text = TEMPLATE.read_text(encoding="utf-8")
    block = re.search(rf"^  {key}:\n((?:    .*\n|\s*#.*\n)+)", text, re.M)
    assert block, key
    return dict(re.findall(r'^    (\w+): "([^"]+)"', block.group(1), re.M))


def test_render_body_headings_follow_the_template_body_fields(capsys, tmp_path) -> None:
    fields = _template_block("body_fields")
    _, out = run(capsys, "render-body", "--input", write(tmp_path, "b.json", body_input(body_fields=fields)))
    assert out["fields_ok"]
    assert "### Mailing list thread URL\n\nN/A — opened from public PR" in out["text"]
    assert reuse.fields(out["text"]) == list(body.headings(fields).values())


def test_labels_use_the_template_tracker_labels_and_never_needs_triage(capsys, tmp_path) -> None:
    configured = _template_block("labels")
    data = {"scope": "providers", "state": "MERGED", "labels": configured}
    _, out = run(capsys, "labels", "--input", write(tmp_path, "l.json", data))
    assert out["labels"] == ["providers", "pr merged", "security"]
    assert configured["needs_triage"] not in out["labels"]
    _, out = run(
        capsys, "labels", "--input", write(tmp_path, "l.json", {"scope": "airflow", "state": "OPEN"})
    )
    assert out["labels"] == ["airflow", "pr created", "security issue"]
    _, out = run(
        capsys, "labels", "--input", write(tmp_path, "l.json", {"scope": "airflow", "state": "CLOSED"})
    )
    assert out["labels"] == ["airflow", "security issue"]
    assert out["warnings"]


def test_render_rollup_entry(capsys, tmp_path) -> None:
    data = {
        "upstream": UPSTREAM,
        "pr_number": 65703,
        "scope": "providers",
        "state": "MERGED",
        "date": "2026-10-16",
        "author_login": "justinpakzad",
        "remediation_developer": "Justin Pakzad",
        "affected_versions": "apache-airflow-providers-amazon < 9.9.0",
        "security_list": "security@airflow.apache.org",
    }
    _, out = run(capsys, "render-rollup", "--input", write(tmp_path, "r.json", data))
    assert out["label"] == "Import from PR (providers, apache/airflow#65703)"
    assert out["text"].startswith("**Imported from public PR [apache/airflow#65703](")
    assert all(not line.startswith(" ") for line in out["text"].split("\n"))
    assert "*Remediation developer*=Justin Pakzad" in out["text"]
    data["remediation_developer_is_bot"] = True
    _, out = run(capsys, "render-rollup", "--input", write(tmp_path, "r.json", data))
    assert "bot/AI credit policy" in out["text"]
    data["scope"] = "a<b"
    code, out = run(capsys, "render-rollup", "--input", write(tmp_path, "r.json", data))
    assert code == 2


def test_dup_query_command_and_the_thirty_hit_warning(capsys, tmp_path) -> None:
    _, out = run(capsys, "dup-query", "--pr", "65703", "--tracker", TRACKER)
    assert out["query"] == 'in:body "pull/65703" OR 65703'
    assert "--limit 30" in out["command"]
    hits = write(tmp_path, "h.json", [{"number": n, "title": "t", "state": "OPEN"} for n in range(30)])
    _, out = run(capsys, "dup-query", "--pr", "65703", "--tracker", TRACKER, "--hits", hits)
    assert out["truncated"] and out["warning"]
    hits = write(tmp_path, "h.json", [{"number": 7, "title": "t", "state": "CLOSED"}])
    _, out = run(capsys, "dup-query", "--pr", "65703", "--tracker", TRACKER, "--hits", hits)
    assert out["duplicate"] and not out["truncated"]
    assert out["hits"][0]["link"] == f"[{TRACKER}#7](https://github.com/{TRACKER}/issues/7)"
    with pytest.raises(SystemExit):
        main(["issue-import-from-pr", "dup-query", "--pr", "65703 OR x", "--tracker", TRACKER])


def test_recap_matches_the_step_8_scenario(capsys, tmp_path) -> None:
    data = {
        "tracker": TRACKER,
        "number": 356,
        "pr_url": "https://github.com/apache/airflow/pull/65703",
        "labels": ["security issue", "providers", "pr merged"],
        "milestone": "Providers 2025-06-15",
        "rollup_url": f"https://github.com/{TRACKER}/issues/356#issuecomment-8001",
    }
    _, out = run(capsys, "render-recap", "--input", write(tmp_path, "r.json", data))
    text = out["text"]
    assert f"https://github.com/{TRACKER}/issues/356" in text
    assert "https://github.com/apache/airflow/pull/65703" in text
    assert "`Assessed`" in text
    assert "Providers 2025-06-15" in text
    assert "#issuecomment-8001" in text
    assert "security-cve-allocate" in text
    assert out["bare_refs"] == []
