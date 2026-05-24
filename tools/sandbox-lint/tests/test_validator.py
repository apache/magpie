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

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from sandbox_lint import (
    check_invariants,
    deep_diff,
    main,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
LIVE_SETTINGS = REPO_ROOT / ".claude" / "settings.json"
BASELINE = REPO_ROOT / "tools" / "sandbox-lint" / "expected.json"


def _load(p: Path) -> dict[str, Any]:
    return json.loads(p.read_text())


@pytest.fixture
def baseline() -> dict[str, Any]:
    return _load(BASELINE)


@pytest.fixture
def live_settings() -> dict[str, Any]:
    return _load(LIVE_SETTINGS)


# ---------------------------------------------------------------------------
# End-to-end: shipped baseline matches live settings and passes invariants
# ---------------------------------------------------------------------------


def test_baseline_file_matches_live_settings(baseline: dict[str, Any], live_settings: dict[str, Any]) -> None:
    diffs = deep_diff(live_settings, baseline)
    assert diffs == [], "live settings drifted from baseline:\n" + "\n".join(diffs)


def test_baseline_satisfies_invariants(baseline: dict[str, Any]) -> None:
    errors = check_invariants(baseline)
    assert errors == [], "baseline violates invariants:\n" + "\n".join(errors)


def test_live_settings_satisfy_invariants(live_settings: dict[str, Any]) -> None:
    errors = check_invariants(live_settings)
    assert errors == [], "live settings violate invariants:\n" + "\n".join(errors)


def test_main_exits_zero_on_repo(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(REPO_ROOT)
    assert main([]) == 0


# ---------------------------------------------------------------------------
# Diff: order/duplicates ignored on set-typed lists
# ---------------------------------------------------------------------------


def test_diff_set_lists_order_insensitive(baseline: dict[str, Any]) -> None:
    settings = copy.deepcopy(baseline)
    settings["sandbox"]["network"]["allowedDomains"] = list(
        reversed(settings["sandbox"]["network"]["allowedDomains"])
    )
    assert deep_diff(settings, baseline) == []


def test_diff_detects_added_allowed_domain(baseline: dict[str, Any]) -> None:
    settings = copy.deepcopy(baseline)
    settings["sandbox"]["network"]["allowedDomains"].append("sandbox-lint-test-extra-marker")
    diffs = deep_diff(settings, baseline)
    assert any("sandbox-lint-test-extra-marker" in d for d in diffs)


def test_diff_detects_removed_deny_entry(baseline: dict[str, Any]) -> None:
    settings = copy.deepcopy(baseline)
    settings["permissions"]["deny"].remove("Bash(curl *)")
    diffs = deep_diff(settings, baseline)
    assert any("Bash(curl *)" in d and "missing entry" in d for d in diffs)


def test_diff_detects_scalar_change(baseline: dict[str, Any]) -> None:
    settings = copy.deepcopy(baseline)
    settings["sandbox"]["enabled"] = False
    diffs = deep_diff(settings, baseline)
    assert any("sandbox.enabled" in d for d in diffs)


# ---------------------------------------------------------------------------
# Invariants: each forbidden / required check fires
# ---------------------------------------------------------------------------


def test_invariant_sandbox_disabled(baseline: dict[str, Any]) -> None:
    settings = copy.deepcopy(baseline)
    settings["sandbox"]["enabled"] = False
    errors = check_invariants(settings)
    assert any("sandbox.enabled" in e for e in errors)


def test_invariant_missing_deny_read_root(baseline: dict[str, Any]) -> None:
    settings = copy.deepcopy(baseline)
    settings["sandbox"]["filesystem"]["denyRead"] = []
    errors = check_invariants(settings)
    assert any("denyRead" in e for e in errors)


@pytest.mark.parametrize(
    "forbidden",
    [
        "~/.aws",
        "~/.aws/",
        "~/.ssh",
        "~/.netrc",
        "~/.docker/",
        "~/.kube",
        "~/.azure",
        "~/.config/gcloud",
        "/",
        "~/",
    ],
)
def test_invariant_allow_read_rejects_credential_paths(baseline: dict[str, Any], forbidden: str) -> None:
    settings = copy.deepcopy(baseline)
    settings["sandbox"]["filesystem"]["allowRead"].append(forbidden)
    errors = check_invariants(settings)
    assert any("allowRead" in e and forbidden.rstrip("/") in e for e in errors)


@pytest.mark.parametrize(
    "forbidden",
    [
        "~/",
        "~/.config/",
        "~/.config/gh",
        "~/.gnupg",
        "~/.ssh",
        "~/.aws/",
    ],
)
def test_invariant_allow_write_rejects_credential_paths(baseline: dict[str, Any], forbidden: str) -> None:
    settings = copy.deepcopy(baseline)
    fs = settings["sandbox"]["filesystem"]
    if forbidden not in fs["allowRead"]:
        fs["allowRead"].append(forbidden)
    fs["allowWrite"].append(forbidden)
    errors = check_invariants(settings)
    assert any("allowWrite" in e and forbidden.rstrip("/") in e for e in errors)


def test_invariant_allow_write_must_be_subset_of_allow_read(
    baseline: dict[str, Any],
) -> None:
    settings = copy.deepcopy(baseline)
    settings["sandbox"]["filesystem"]["allowWrite"].append("~/.local/share/uv-extra/")
    errors = check_invariants(settings)
    assert any("subset" in e for e in errors)


@pytest.mark.parametrize(
    "required",
    [
        "Read(~/.aws/**)",
        "Read(~/.ssh/**)",
        "Read(~/.netrc)",
        "Bash(curl *)",
        "Bash(wget *)",
        "Bash(aws *)",
    ],
)
def test_invariant_required_deny_entries(baseline: dict[str, Any], required: str) -> None:
    settings = copy.deepcopy(baseline)
    settings["permissions"]["deny"].remove(required)
    errors = check_invariants(settings)
    assert any(required in e for e in errors)


# ---------------------------------------------------------------------------
# CLI: non-zero exit on drift; non-zero on invariant violation
# ---------------------------------------------------------------------------


def _write_json(p: Path, data: dict[str, Any]) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2))


def test_cli_fails_on_drift(tmp_path: Path, baseline: dict[str, Any]) -> None:
    settings_path = tmp_path / "settings.json"
    expected_path = tmp_path / "expected.json"
    drifted = copy.deepcopy(baseline)
    drifted["sandbox"]["network"]["allowedDomains"].append("sandbox-lint-test-extra-marker")
    _write_json(settings_path, drifted)
    _write_json(expected_path, baseline)
    rc = main(["--settings", str(settings_path), "--expected", str(expected_path)])
    assert rc == 1


def test_cli_fails_on_invariant_violation(tmp_path: Path, baseline: dict[str, Any]) -> None:
    settings_path = tmp_path / "settings.json"
    expected_path = tmp_path / "expected.json"
    bad = copy.deepcopy(baseline)
    bad["sandbox"]["filesystem"]["allowRead"].append("~/.aws")
    _write_json(settings_path, bad)
    _write_json(expected_path, bad)
    rc = main(["--settings", str(settings_path), "--expected", str(expected_path)])
    assert rc == 1


def test_cli_passes_on_match(tmp_path: Path, baseline: dict[str, Any]) -> None:
    settings_path = tmp_path / "settings.json"
    expected_path = tmp_path / "expected.json"
    _write_json(settings_path, baseline)
    _write_json(expected_path, baseline)
    rc = main(["--settings", str(settings_path), "--expected", str(expected_path)])
    assert rc == 0


# ---------------------------------------------------------------------------
# deep_diff: additional structural cases
# ---------------------------------------------------------------------------


def test_diff_type_mismatch_reported() -> None:
    diffs = deep_diff({"key": "string"}, {"key": 42})
    assert any("type mismatch" in d for d in diffs)


def test_diff_key_missing_in_settings_reported() -> None:
    diffs = deep_diff({}, {"key": "value"})
    assert any("missing in settings" in d for d in diffs)


def test_diff_extra_key_in_settings_reported() -> None:
    diffs = deep_diff({"extra": "value"}, {})
    assert any("extra in settings" in d for d in diffs)


def test_diff_nested_scalar_change_reported() -> None:
    actual = {"a": {"b": {"c": 1}}}
    expected = {"a": {"b": {"c": 2}}}
    diffs = deep_diff(actual, expected)
    assert len(diffs) == 1
    assert "$.a.b.c" in diffs[0]


def test_diff_non_set_list_mismatch_reported() -> None:
    # Lists whose key is not in SET_LIST_KEYS are compared positionally.
    actual = {"hooks": [1, 2, 3]}
    expected = {"hooks": [1, 2, 4]}
    diffs = deep_diff(actual, expected)
    assert any("list mismatch" in d for d in diffs)


def test_diff_identical_trees_return_empty() -> None:
    data = {"sandbox": {"enabled": True, "network": {"allowedDomains": ["a", "b"]}}}
    assert deep_diff(data, data) == []


def test_diff_empty_dicts_match() -> None:
    assert deep_diff({}, {}) == []


# ---------------------------------------------------------------------------
# check_invariants: missing top-level keys
# ---------------------------------------------------------------------------


def test_invariant_missing_sandbox_key() -> None:
    errors = check_invariants({})
    assert any("sandbox" in e for e in errors)


def test_invariant_missing_filesystem_key(baseline: dict[str, Any]) -> None:
    settings = copy.deepcopy(baseline)
    del settings["sandbox"]["filesystem"]
    errors = check_invariants(settings)
    assert any("filesystem" in e for e in errors)


def test_invariant_missing_permissions_key(baseline: dict[str, Any]) -> None:
    settings = copy.deepcopy(baseline)
    del settings["permissions"]
    errors = check_invariants(settings)
    assert any("permissions" in e for e in errors)


# ---------------------------------------------------------------------------
# CLI: malformed / missing file error paths
# ---------------------------------------------------------------------------


def test_cli_exits_on_missing_settings_file(tmp_path: Path, baseline: dict[str, Any]) -> None:
    expected_path = tmp_path / "expected.json"
    _write_json(expected_path, baseline)
    with pytest.raises(SystemExit):
        main(["--settings", str(tmp_path / "nonexistent.json"), "--expected", str(expected_path)])


def test_cli_exits_on_missing_expected_file(tmp_path: Path, baseline: dict[str, Any]) -> None:
    settings_path = tmp_path / "settings.json"
    _write_json(settings_path, baseline)
    with pytest.raises(SystemExit):
        main(["--settings", str(settings_path), "--expected", str(tmp_path / "nonexistent.json")])


def test_cli_exits_on_malformed_json(tmp_path: Path, baseline: dict[str, Any]) -> None:
    settings_path = tmp_path / "settings.json"
    settings_path.write_text("{ not valid json }")
    expected_path = tmp_path / "expected.json"
    _write_json(expected_path, baseline)
    with pytest.raises(SystemExit):
        main(["--settings", str(settings_path), "--expected", str(expected_path)])


def test_cli_exits_when_top_level_value_is_not_object(tmp_path: Path, baseline: dict[str, Any]) -> None:
    settings_path = tmp_path / "settings.json"
    settings_path.write_text("[1, 2, 3]")
    expected_path = tmp_path / "expected.json"
    _write_json(expected_path, baseline)
    with pytest.raises(SystemExit):
        main(["--settings", str(settings_path), "--expected", str(expected_path)])
