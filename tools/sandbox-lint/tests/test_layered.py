# SPDX-License-Identifier: Apache-2.0
# https://www.apache.org/licenses/LICENSE-2.0
"""The committed floor, the local template, and the family MCP registry."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest

from sandbox_lint import (
    REQUIRED_VETTED_OP_READ_ALLOW,
    check_invariants,
    main,
    merge_layers,
    registry_errors,
    split_errors,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
FLOOR = REPO_ROOT / ".claude" / "settings.json"
LOCAL_TEMPLATE = REPO_ROOT / "tools" / "agent-isolation" / "claude-settings.local.template.json"
REGISTRY = REPO_ROOT / "plugins" / "magpie-setup" / "skills" / "setup" / "family-mcp-allows.json"


def _load(p: Path) -> dict[str, Any]:
    return json.loads(p.read_text())


def test_merge_concatenates_lists_and_recurses() -> None:
    floor = {"sandbox": {"enabled": True, "filesystem": {"allowRead": ["."]}}, "permissions": {"deny": ["a"]}}
    local = {"sandbox": {"filesystem": {"allowRead": [".", "~/x"]}}, "permissions": {"allow": ["b"]}}
    assert merge_layers(floor, local) == {
        "sandbox": {"enabled": True, "filesystem": {"allowRead": [".", "~/x"]}},
        "permissions": {"deny": ["a"], "allow": ["b"]},
    }


@pytest.mark.parametrize(
    "floor,local,needle",
    [
        ({"permissions": {"allow": ["Bash(ls *)"]}}, {}, "floor permissions.allow"),
        ({}, {"permissions": {"deny": ["Bash(rm *)"]}}, "permissions.deny"),
        ({}, {"permissions": {"ask": ["Bash(git push *)"]}}, "permissions.ask"),
        ({}, {"permissions": {"allow": ["mcp__ponymail__get_email"]}}, "is an MCP tool"),
        ({"sandbox": {"enabled": True}}, {"sandbox": {"enabled": False}}, "$.sandbox.enabled"),
    ],
)
def test_split_rules(floor: dict[str, Any], local: dict[str, Any], needle: str) -> None:
    errors = split_errors(floor, local)
    assert any(needle in e for e in errors), errors


def test_floor_may_hold_derived_mcp_and_the_vetted_op_read_pair() -> None:
    floor = {"permissions": {"allow": ["mcp__ponymail__get_email", *REQUIRED_VETTED_OP_READ_ALLOW]}}
    assert split_errors(floor, {}) == []


def test_the_shipped_split_is_clean() -> None:
    assert split_errors(_load(FLOOR), _load(LOCAL_TEMPLATE)) == []


def test_the_floor_alone_is_safe() -> None:
    # A contributor with no local file still gets every protective rule.
    assert check_invariants(_load(FLOOR)) == []


def test_floor_mcp_allows_are_the_registry_for_every_family() -> None:
    # The framework checkout links every family, so its committed MCP allows
    # are exactly what the registry derives for all of them.
    assert registry_errors(_load(FLOOR), _load(REGISTRY)) == []


def test_registry_drift_is_reported_both_ways() -> None:
    registry = {"servers": {"ponymail": {"families": ["security"], "tools": ["get_email", "get_thread"]}}}
    floor = {"permissions": {"allow": ["mcp__ponymail__get_email", "mcp__other__x"]}}
    errors = registry_errors(floor, registry)
    assert any("missing 'mcp__ponymail__get_thread'" in e for e in errors)
    assert any("'mcp__other__x' is not in" in e for e in errors)


def test_merge_handles_lists_of_objects() -> None:
    entry = {"name": "GH_TOKEN", "mode": "deny"}
    merged = merge_layers(
        {"c": {"envVars": [entry]}}, {"c": {"envVars": [entry, {"name": "X", "mode": "deny"}]}}
    )
    assert merged["c"]["envVars"] == [entry, {"name": "X", "mode": "deny"}]


def test_cli_lints_the_layered_view_by_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    settings, _ = _project_with(tmp_path, _load(LOCAL_TEMPLATE))
    expected = settings.parent.parent / "tools" / "sandbox-lint" / "expected.json"
    expected.parent.mkdir(parents=True)
    expected.write_text((REPO_ROOT / "tools" / "sandbox-lint" / "expected.json").read_text())
    monkeypatch.chdir(settings.parent.parent)
    assert main([]) == 0
    assert "claude-settings.local.template.json" in capsys.readouterr().out


def test_cli_without_a_template_lints_the_file_alone(tmp_path: Path) -> None:
    # A project that has no local template (any adopter) lints its own file.
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps(merge_layers(_load(FLOOR), _load(LOCAL_TEMPLATE))))
    expected = REPO_ROOT / "tools" / "sandbox-lint" / "expected.json"
    cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        assert main(["--settings", str(settings), "--expected", str(expected)]) == 0
    finally:
        os.chdir(cwd)


def _project_with(tmp_path: Path, template: dict[str, Any], *, registry: bool = True) -> tuple[Path, Path]:
    root = tmp_path / "project"
    (root / ".claude").mkdir(parents=True)
    (root / ".claude" / "settings.json").write_text(FLOOR.read_text())
    tpl = root / "tools" / "agent-isolation" / "claude-settings.local.template.json"
    tpl.parent.mkdir(parents=True)
    tpl.write_text(json.dumps(template))
    if registry:
        reg = root / "plugins" / "magpie-setup" / "skills" / "setup" / "family-mcp-allows.json"
        reg.parent.mkdir(parents=True)
        reg.write_text(REGISTRY.read_text())
    return root / ".claude" / "settings.json", tpl


@pytest.mark.parametrize(
    "extra,needle",
    [
        ({"permissions": {"deny": ["Bash(rm *)"]}}, "permissions.deny"),
        ({"sandbox": {"enabled": False}}, "$.sandbox.enabled"),
    ],
)
def test_cli_fails_on_a_split_violation(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], extra: dict[str, Any], needle: str
) -> None:
    template = merge_layers(_load(LOCAL_TEMPLATE), extra)
    settings, _ = _project_with(tmp_path, template)
    expected = REPO_ROOT / "tools" / "sandbox-lint" / "expected.json"
    assert main(["--settings", str(settings), "--expected", str(expected)]) == 1
    assert needle in capsys.readouterr().err


def test_cli_uses_an_explicit_local_template(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"permissions": {"ask": ["Bash(git push *)"]}}))
    expected = REPO_ROOT / "tools" / "sandbox-lint" / "expected.json"
    settings, _ = _project_with(tmp_path, _load(LOCAL_TEMPLATE))
    assert main(["--settings", str(settings), "--expected", str(expected), "--local-template", str(bad)]) == 1
    assert "permissions.ask" in capsys.readouterr().err


@pytest.mark.parametrize(
    "local,rc",
    [
        ({"permissions": {"allow": ["Bash(make *)", "mcp__other__read"]}}, 0),
        ({"permissions": {"deny": ["Bash(rm *)"]}}, 0),
        ({"sandbox": {"enabled": False}}, 1),
        ({"sandbox": {"filesystem": {"allowRead": ["~/.ssh"]}}}, 1),
    ],
)
def test_default_run_checks_the_live_local_layer(tmp_path: Path, local: dict[str, Any], rc: int) -> None:
    # The local file in force here may add things, but may not weaken a control.
    settings, _ = _project_with(tmp_path, _load(LOCAL_TEMPLATE))
    (settings.parent / "settings.local.json").write_text(json.dumps(local))
    expected = REPO_ROOT / "tools" / "sandbox-lint" / "expected.json"
    assert main(["--settings", str(settings), "--expected", str(expected)]) == rc


def test_an_equal_local_value_is_not_an_override() -> None:
    # /sandbox may write the same value into settings.local.json.
    assert split_errors({"sandbox": {"enabled": True}}, {"sandbox": {"enabled": True}}) == []


def test_a_missing_registry_beside_the_template_fails(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    settings, _ = _project_with(tmp_path, _load(LOCAL_TEMPLATE), registry=False)
    expected = REPO_ROOT / "tools" / "sandbox-lint" / "expected.json"
    assert main(["--settings", str(settings), "--expected", str(expected)]) == 1
    assert "family-mcp-allows.json is missing" in capsys.readouterr().err


@pytest.mark.parametrize(
    "addition,needle",
    [
        ({"sandbox": {"excludedCommands": ["*"]}}, "arbitrary commands outside the sandbox"),
        ({"sandbox": {"excludedCommands": ["bash *"]}}, "arbitrary commands outside the sandbox"),
        ({"sandbox": {"excludedCommands": ["python3 *"]}}, "arbitrary commands outside the sandbox"),
        ({"permissions": {"allow": ["Bash(*)"]}}, "approves every shell command"),
        ({"permissions": {"allow": ["Bash"]}}, "approves every shell command"),
        ({"permissions": {"defaultMode": "bypassPermissions"}}, "bypassPermissions"),
        ({"sandbox": {"network": {"allowedDomains": ["*"]}}}, "egress to every host"),
        ({"sandbox": {"excludedCommands": ["/bin/bash *"]}}, "arbitrary commands outside the sandbox"),
        ({"sandbox": {"excludedCommands": ["/usr/bin/env *"]}}, "arbitrary commands outside the sandbox"),
        ({"sandbox": {"excludedCommands": ["uv run *"]}}, "arbitrary commands outside the sandbox"),
        ({"sandbox": {"excludedCommands": ["uvx *"]}}, "arbitrary commands outside the sandbox"),
        ({"sandbox": {"excludedCommands": ["npx *"]}}, "arbitrary commands outside the sandbox"),
        ({"sandbox": {"excludedCommands": ["pipx run *"]}}, "arbitrary commands outside the sandbox"),
        ({"permissions": {"allow": ["Bash(bash *)"]}}, "approves every shell command"),
        ({"permissions": {"allow": ["Bash(sh -c *)"]}}, "approves every shell command"),
        ({"permissions": {"allow": ["Bash(/usr/bin/python3 *)"]}}, "approves every shell command"),
        ({"permissions": {"allow": ["Bash(bash:*)"]}}, "approves every shell command"),
        ({"permissions": {"allow": ["Bash(python3:*)"]}}, "approves every shell command"),
        ({"sandbox": {"excludedCommands": ["pipx *"]}}, "arbitrary commands outside the sandbox"),
        (
            {"sandbox": {"excludedCommands": ["uv run --project . *"]}},
            "arbitrary commands outside the sandbox",
        ),
        ({"sandbox": {"excludedCommands": ["uvx --from . *"]}}, "arbitrary commands outside the sandbox"),
        (
            {"sandbox": {"excludedCommands": ["uv run --project . python *"]}},
            "arbitrary commands outside the sandbox",
        ),
        (
            {"sandbox": {"excludedCommands": ["uv run --project . bash *"]}},
            "arbitrary commands outside the sandbox",
        ),
        (
            {"sandbox": {"excludedCommands": ["uv run --project ~/.claude/magpie/vetted-ops -- bash *"]}},
            "arbitrary commands outside the sandbox",
        ),
        (
            {"sandbox": {"excludedCommands": ["uvx --from . node *"]}},
            "arbitrary commands outside the sandbox",
        ),
        ({"sandbox": {"excludedCommands": ["uv tool run *"]}}, "arbitrary commands outside the sandbox"),
        ({"permissions": {"allow": ["Bash(python3.12 *)"]}}, "approves every shell command"),
        ({"permissions": {"allow": ["Bash(osascript *)"]}}, "approves every shell command"),
        ({"permissions": {"allow": ["Bash(awk *)"]}}, "approves every shell command"),
        ({"permissions": {"allow": ["Bash(bash*)"]}}, "approves every shell command"),
        ({"permissions": {"allow": ["Bash(python*)"]}}, "approves every shell command"),
        ({"permissions": {"allow": ["Bash(b*)"]}}, "approves every shell command"),
        ({"sandbox": {"excludedCommands": ["uv run*"]}}, "arbitrary commands outside the sandbox"),
        ({"sandbox": {"excludedCommands": ["uvx*"]}}, "arbitrary commands outside the sandbox"),
        ({"sandbox": {"excludedCommands": ["npx*"]}}, "arbitrary commands outside the sandbox"),
        ({"sandbox": {"excludedCommands": ["uv --offline run *"]}}, "arbitrary commands outside the sandbox"),
        ({"permissions": {"allow": ["Bash(uv -q run bash *)"]}}, "approves every shell command"),
        (
            {"sandbox": {"excludedCommands": ["uv tool --quiet run *"]}},
            "arbitrary commands outside the sandbox",
        ),
        (
            {"sandbox": {"excludedCommands": ["pipx --verbose run *"]}},
            "arbitrary commands outside the sandbox",
        ),
    ],
)
def test_wholesale_weakenings_fail_in_any_layer(addition: dict[str, Any], needle: str) -> None:
    errors = check_invariants(merge_layers(merge_layers(_load(FLOOR), _load(LOCAL_TEMPLATE)), addition))
    assert any(needle in e for e in errors), errors


def test_a_live_local_wholesale_weakening_fails_the_lint(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    settings, _ = _project_with(tmp_path, _load(LOCAL_TEMPLATE))
    (settings.parent / "settings.local.json").write_text(json.dumps({"sandbox": {"excludedCommands": ["*"]}}))
    expected = REPO_ROOT / "tools" / "sandbox-lint" / "expected.json"
    assert main(["--settings", str(settings), "--expected", str(expected)]) == 1
    assert "arbitrary commands outside the sandbox" in capsys.readouterr().err


@pytest.mark.parametrize(
    "command",
    [
        "uv run --project ~/.claude/magpie/vetted-ops vetted-op-read *",
        "uvx --from ~/.claude/magpie/vetted-ops vetted-op-tracker *",
        "gh *",
        "~/.claude/scripts/magpie-run-evals.sh *",
        "zizmor *",
        "uv --version",
        "gh auth status*",
        "uv run --project ~/.claude/magpie/vetted-ops vetted-op-tracker *",
        "uvx --from ~/.claude/magpie/adversarial-review adversarial-review *",
        "npm --version",
        "pipx list",
    ],
)
def test_pinned_runners_and_named_tools_stay_legal(command: str) -> None:
    from sandbox_lint import _runs_anything

    assert not _runs_anything(command)


@pytest.mark.parametrize(
    "command",
    [
        "uv run --project . vetted-op-read *",
        "uvx --from ./x tool *",
        "uv run --project ~/../x vetted-op-read *",
        "uv sync *",
        "uv lock *",
        "uv pip install *",
        "uv build *",
        "uv self update *",
    ],
)
def test_relative_pins_and_building_uv_subcommands_run_code(command: str) -> None:
    from sandbox_lint import _runs_anything

    assert _runs_anything(command)


@pytest.mark.parametrize(
    "command",
    [
        "uv run --project ~/.cache/x tool *",
        "uvx --from ~/.local/share/uv/x tool *",
        "uv run --project /work/repo/sub tool *",
        "./scripts/run.sh *",
        "tools/foo/run.sh *",
        "~/.cache/run.sh *",
        "/work/repo/scripts/run.sh *",
        "uv run --project ~/.claude/magpie/vetted-ops ./evil.py *",
        "/tmp/claude/run.sh *",
        "uv run --project /tmp/claude/p tool *",
        "FOO=1 *",
        "X=1 bash *",
        "source *",
        ". *",
        "npm exec *",
        "npm run *",
        "pnpm dlx *",
        "yarn dlx *",
        "pipx install *",
        "pipx runpip *",
        "pipx --verbose run *",
    ],
)
def test_paths_the_agent_can_write_run_code(command: str) -> None:
    from sandbox_lint import _runs_anything, _writable_roots

    writable = _writable_roots(["~/.cache/", "~/.local/share/uv/"], Path("/work/repo"))
    assert _runs_anything(command, writable)


def test_a_script_under_a_local_allow_write_fails_the_invariants() -> None:
    addition = {
        "sandbox": {
            "filesystem": {"allowWrite": ["~/.claude/scripts/"], "allowRead": ["~/.claude/scripts/"]},
        }
    }
    settings = merge_layers(merge_layers(_load(FLOOR), _load(LOCAL_TEMPLATE)), addition)
    errors = check_invariants(settings, project_root=REPO_ROOT)
    assert any("magpie-run-evals.sh" in e and "arbitrary commands" in e for e in errors), errors


@pytest.mark.parametrize("work_dir", ["~/.claude/magpie", "~/.claude/", "~/"])
def test_a_working_dir_over_vetted_ops_fails_the_invariants(work_dir: str) -> None:
    addition = {"permissions": {"additionalDirectories": [work_dir]}}
    settings = merge_layers(merge_layers(_load(FLOOR), _load(LOCAL_TEMPLATE)), addition)
    errors = check_invariants(settings, project_root=REPO_ROOT)
    assert any(e.startswith("permissions.additionalDirectories:") for e in errors), errors
    assert any("vetted-op-read" in e and "arbitrary commands" in e for e in errors), errors


def test_a_working_dir_elsewhere_passes_the_invariants() -> None:
    addition = {"permissions": {"additionalDirectories": [f"/tmp/claude-{os.getuid()}", "/opt/data"]}}
    settings = merge_layers(merge_layers(_load(FLOOR), _load(LOCAL_TEMPLATE)), addition)
    assert check_invariants(settings, project_root=REPO_ROOT) == []


@pytest.mark.parametrize("work_dir", ["~/.claude/magpie/vetted-ops", "~/.claude/magpie/adversarial-review/"])
def test_a_working_dir_inside_the_checkout_fails_the_invariants(work_dir: str) -> None:
    addition = {"permissions": {"additionalDirectories": [work_dir]}}
    settings = merge_layers(merge_layers(_load(FLOOR), _load(LOCAL_TEMPLATE)), addition)
    errors = check_invariants(settings, project_root=REPO_ROOT)
    assert any(e.startswith(f"permissions.additionalDirectories: {work_dir!r}") for e in errors), errors


def _with_exclusions(*entries: str) -> dict[str, Any]:
    return merge_layers(
        merge_layers(_load(FLOOR), _load(LOCAL_TEMPLATE)), {"sandbox": {"excludedCommands": list(entries)}}
    )


@pytest.mark.parametrize("entry", ["roborev *", "gh auth *", "gh", "gh auth status", "gh:*", "roborev:*"])
def test_allowlisted_exclusions_and_their_narrowings_pass(entry: str) -> None:
    assert check_invariants(_with_exclusions(entry), project_root=REPO_ROOT) == []


@pytest.mark.parametrize(
    "entry", ["find *", "git *", "make *", "docker *", "zizmor *", "ghx *", "roborevx *"]
)
def test_an_exclusion_off_the_allowlist_fails(entry: str) -> None:
    errors = check_invariants(_with_exclusions(entry), project_root=REPO_ROOT)
    assert any(f"{entry!r} is not on the exclusion allowlist" in e for e in errors), errors


def test_a_project_can_extend_the_allowlist(tmp_path: Path) -> None:
    from sandbox_lint import PROJECT_EXCLUSION_ALLOWLIST

    extension = tmp_path / PROJECT_EXCLUSION_ALLOWLIST
    extension.parent.mkdir(parents=True)
    extension.write_text("# reviewed in #123\nzizmor *\n\nbash *\n")
    errors = check_invariants(_with_exclusions("zizmor *", "bash *"), project_root=tmp_path)
    assert not any("'zizmor *'" in e for e in errors), errors
    # An extension still has to pass the runs-anything check.
    assert any("'bash *' would run arbitrary commands" in e for e in errors), errors
    assert not any("'bash *' is not on the exclusion allowlist" in e for e in errors), errors


def test_an_unreadable_extension_is_reported(tmp_path: Path) -> None:
    from sandbox_lint import PROJECT_EXCLUSION_ALLOWLIST

    (tmp_path / PROJECT_EXCLUSION_ALLOWLIST).mkdir(parents=True)
    errors = check_invariants(_with_exclusions(), project_root=tmp_path)
    assert any(e.startswith(f"{PROJECT_EXCLUSION_ALLOWLIST}: cannot be read") for e in errors), errors
