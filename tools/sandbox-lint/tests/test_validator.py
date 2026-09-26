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


def test_baseline_excludes_gh_from_sandbox(baseline: dict[str, Any]) -> None:
    # gh authenticates via the OS keyring, which is unreachable inside the
    # sandbox; excluding it lets gh run against the real host auth. The `ask`
    # rules still gate its write/destructive subcommands.
    assert "gh *" in baseline["sandbox"].get("excludedCommands", [])


def test_baseline_asks_on_gh_writes_not_on_reads(baseline: dict[str, Any]) -> None:
    # Claude Code evaluates deny, then ask, then allow, and "a matching ask
    # rule prompts even when a more specific allow rule also matches", so a
    # catch-all `Bash(gh *)` in ask would silently defeat every read-only
    # allow below it. The write subcommands are listed one by one instead.
    ask = baseline["permissions"]["ask"]
    assert "Bash(gh *)" not in ask
    for rule in (
        "Bash(gh api *)",
        "Bash(gh pr merge *)",
        "Bash(gh issue close *)",
        "Bash(gh release delete *)",
        "Bash(gh repo delete *)",
    ):
        assert rule in ask, rule
    assert "Bash(gh pr view *)" in baseline["permissions"]["allow"]


VETTED_OP_READ = "~/.claude/plugins/cache/apache-magpie/magpie-vetted-ops/*/tools/vetted-ops vetted-op-read *"


@pytest.mark.parametrize("form", ["uv run --project", "uvx --from"])
def test_baseline_allows_and_excludes_every_vetted_op_read_form(baseline: dict[str, Any], form: str) -> None:
    # Skills invoke the read dispatcher with `uv run --project`, read-only
    # gatherer agents with `uvx --from`. A rule for only one form leaves every
    # call in the other form prompting (a bulk sync makes hundreds of them) or
    # failing inside the sandbox, where it cannot reach gh or the network.
    assert f"{form} {VETTED_OP_READ}" in baseline["sandbox"]["excludedCommands"]
    assert f"Bash({form} {VETTED_OP_READ})" in baseline["permissions"]["allow"]


def test_baseline_never_allows_the_vetted_op_write_dispatcher(baseline: dict[str, Any]) -> None:
    # `--caller` is an argv string the caller picks, so an allow on the write
    # dispatcher would grant the whole catalogue. It stays on ask.
    write = VETTED_OP_READ.replace("vetted-op-read", "vetted-op")
    for form in ("uv run --project", "uvx --from"):
        assert f"Bash({form} {write})" not in baseline["permissions"]["allow"]


def test_catch_all_gh_ask_rule_is_an_invariant_error(baseline: dict[str, Any]) -> None:
    weakened = copy.deepcopy(baseline)
    weakened["permissions"]["ask"].append("Bash(gh *)")
    errors = check_invariants(weakened)
    assert any("Bash(gh *)" in e for e in errors), errors


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


def test_diff_excluded_commands_order_insensitive(baseline: dict[str, Any]) -> None:
    settings = copy.deepcopy(baseline)
    settings["sandbox"]["excludedCommands"] = [
        *reversed(settings["sandbox"]["excludedCommands"]),
        *settings["sandbox"]["excludedCommands"],
    ]
    assert deep_diff(settings, baseline) == []


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
        "~/.ssh//",
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
        "~/.aws//",
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


# ---------------------------------------------------------------------------
# Container gateway: every setting that points a CLI or a sandboxed Bash at a
# gateway socket needs that socket's ABSOLUTE path, which is per-machine, so
# none of them belongs in this committed baseline.
# ---------------------------------------------------------------------------


def test_baseline_carries_no_gateway_env(baseline: dict[str, Any]) -> None:
    # CONTAINER_HOST / DOCKER_HOST used to be committed here with a
    # project-relative "unix://./.apache-magpie-local/run/podman.sock" value,
    # on the assumption that the CLIs resolve it against the cwd. They do not:
    # podman parses the URL authority as a host component, so "unix://./x"
    # dials "/.//x" and "unix://x" dials "/x/" -- no relative spelling reaches
    # the socket. Only "unix:///abs/path" works, and an absolute path is
    # per-machine, so both vars live in .claude/settings.local.json next to
    # the allowUnixSockets entries below (see
    # docs/setup/secure-agent-setup.md#container-gateway).
    env = baseline.get("env", {})
    assert "CONTAINER_HOST" not in env
    assert "DOCKER_HOST" not in env


def test_baseline_has_no_gateway_socket_entries(baseline: dict[str, Any]) -> None:
    # Same reason as above, for the other half of the wiring: the absolute
    # allowUnixSockets entries a sandboxed Bash needs to connect(2) to the
    # gateway sockets are per-project, local settings -- written into
    # .claude/settings.local.json, never into this committed baseline.
    sockets = baseline["sandbox"]["network"].get("allowUnixSockets", [])
    assert not any(s.endswith("podman.sock") or s.endswith("docker.sock") for s in sockets)


@pytest.mark.parametrize(
    "entry",
    [
        "/var/run/docker.sock",
        "~/.docker/run/docker.sock",
        "/run/user/1000/podman/podman.sock",
        "/var/folders/ab/T/podman/podman-machine-default-api.sock",
    ],
)
def test_daemon_sockets_in_allow_unix_sockets_are_rejected(baseline: dict[str, Any], entry: str) -> None:
    settings = copy.deepcopy(baseline)
    settings["sandbox"]["network"].setdefault("allowUnixSockets", []).append(entry)
    errors = check_invariants(settings)
    assert any("names a container daemon socket" in e and entry in e for e in errors), errors


def test_gateway_sockets_pass_the_invariant(baseline: dict[str, Any]) -> None:
    settings = copy.deepcopy(baseline)
    settings["sandbox"]["network"]["allowUnixSockets"] = [
        "./.apache-magpie-local/run/podman.sock",
        "/Users/x/proj/.apache-magpie-local/run/docker.sock",
    ]
    assert not [e for e in check_invariants(settings) if "daemon socket" in e]


@pytest.mark.parametrize(
    "entry", ["/var/run/Docker.sock", "~/.docker/run/DOCKER.SOCK", "/run/podman/PODMAN.SOCK"]
)
def test_daemon_socket_names_are_matched_case_insensitively(baseline: dict[str, Any], entry: str) -> None:
    # macOS's filesystem is case-insensitive, so the check must not miss a
    # daemon socket entry just because its case differs from the canonical
    # "docker.sock" / "podman.sock" spelling.
    settings = copy.deepcopy(baseline)
    settings["sandbox"]["network"].setdefault("allowUnixSockets", []).append(entry)
    errors = check_invariants(settings)
    assert any("names a container daemon socket" in e and entry in e for e in errors), errors


def test_bare_socket_name_entry_is_rejected(baseline: dict[str, Any]) -> None:
    # An entry with no directory component at all cannot possibly sit under
    # .apache-magpie-local/run, so it must never be exempted.
    settings = copy.deepcopy(baseline)
    settings["sandbox"]["network"]["allowUnixSockets"] = ["podman.sock"]
    errors = check_invariants(settings)
    assert any("names a container daemon socket" in e for e in errors), errors


def test_decoy_apache_magpie_local_run_path_is_rejected_with_a_project_root(
    baseline: dict[str, Any], tmp_path: Path
) -> None:
    # The bare suffix match ("parent.endswith('.apache-magpie-local/run')")
    # cannot tell a legitimate project-scoped socket from a decoy sitting
    # under an unrelated directory that happens to end the same way -- both
    # end in ".apache-magpie-local/run". Passing project_root closes that:
    # the decoy is outside it and must be rejected.
    project_root = tmp_path / "real-project"
    settings = copy.deepcopy(baseline)
    settings["sandbox"]["network"]["allowUnixSockets"] = [
        str(tmp_path / "evil" / ".apache-magpie-local" / "run" / "podman.sock")
    ]
    errors = check_invariants(settings, project_root=project_root)
    assert any("names a container daemon socket" in e for e in errors), errors


def test_gateway_socket_under_the_given_project_root_passes(baseline: dict[str, Any], tmp_path: Path) -> None:
    project_root = tmp_path / "real-project"
    settings = copy.deepcopy(baseline)
    settings["sandbox"]["network"]["allowUnixSockets"] = [
        str(project_root / ".apache-magpie-local" / "run" / "podman.sock"),
        "./.apache-magpie-local/run/docker.sock",  # relative to project_root, per the committed convention
    ]
    errors = check_invariants(settings, project_root=project_root)
    assert not [e for e in errors if "daemon socket" in e], errors


def test_infer_project_root_from_dot_claude_settings_path(tmp_path: Path) -> None:
    from sandbox_lint import _infer_project_root

    settings_path = tmp_path / "proj" / ".claude" / "settings.json"
    settings_path.parent.mkdir(parents=True)
    settings_path.write_text("{}")
    assert _infer_project_root(settings_path) == (tmp_path / "proj").resolve()


def test_infer_project_root_is_none_outside_a_dot_claude_directory(tmp_path: Path) -> None:
    from sandbox_lint import _infer_project_root

    settings_path = tmp_path / "settings.json"
    settings_path.write_text("{}")
    assert _infer_project_root(settings_path) is None


def test_cli_rejects_a_decoy_daemon_socket_using_the_inferred_project_root(
    tmp_path: Path, baseline: dict[str, Any]
) -> None:
    project_dir = tmp_path / "proj"
    dot_claude = project_dir / ".claude"
    dot_claude.mkdir(parents=True)
    settings = copy.deepcopy(baseline)
    settings["sandbox"]["network"]["allowUnixSockets"] = [
        str(tmp_path / "evil" / ".apache-magpie-local" / "run" / "podman.sock")
    ]
    settings_path = dot_claude / "settings.json"
    _write_json(settings_path, settings)
    expected_path = tmp_path / "expected.json"
    _write_json(expected_path, baseline)
    rc = main(["--settings", str(settings_path), "--expected", str(expected_path)])
    assert rc == 1
