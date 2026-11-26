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

"""The mechanical checks of `setup-isolated-setup-verify`, as tests."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from setup_preflight import isolated_verify
from setup_preflight.isolated_verify import Context, Verifier

PIN = """\
[tools.bubblewrap]
version = "0.13.1"

[tools.socat]
version = "1.8.1.3"

[tools.claude-code]
min_version = "2.1.202"
min_version_no_telemetry = "2.1.281"
"""

USER_HOOKS = {
    "hooks": {
        "PreToolUse": [
            {
                "matcher": "Bash",
                "hooks": [{"type": "command", "command": "~/.claude/scripts/sandbox-bypass-warn.sh"}],
            }
        ],
        "PostToolUse": [
            {
                "matcher": "Bash",
                "hooks": [{"type": "command", "command": "~/.claude/scripts/sandbox-error-hint.sh"}],
            }
        ],
    },
    "statusLine": {"type": "command", "command": "~/.claude/scripts/sandbox-status-line.sh"},
}


def write(path: Path, data: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(data if isinstance(data, str) else json.dumps(data), encoding="utf-8")
    return path


def reference(root: Path, home: Path) -> dict:
    """The project settings of a complete install."""
    return {
        "sandbox": {
            "enabled": True,
            "excludedCommands": ["gh *"],
            "network": {"allowedDomains": ["github.com"]},
            "filesystem": {"denyRead": ["~/"], "allowRead": ["."], "allowWrite": ["~/.cache/"]},
        },
        "permissions": {"deny": ["Bash(curl *)"], "ask": ["Bash(git push *)"]},
    }


def local(root: Path, home: Path) -> dict:
    """The project-local grants `sandbox-add-project-root.sh` writes."""
    tools = [str(home / rel) for rel in isolated_verify.DEV_TOOL_PATHS]
    return {"sandbox": {"filesystem": {"allowRead": [str(root), *tools], "allowWrite": [str(root)]}}}


class Fake:
    """Stands in for `subprocess`: command line → output (None = fails or is missing)."""

    def __init__(self, outputs: dict[str, str | None] | None = None) -> None:
        self.outputs = {"claude --version": "2.1.210 (Claude Code)", **(outputs or {})}
        self.seen: list[str] = []

    def __call__(self, argv: list[str]) -> str | None:
        line = " ".join(argv)
        self.seen.append(line)
        for key, value in self.outputs.items():
            if line == key or line.endswith(" " + key):
                return value
        return None


@pytest.fixture
def setup(tmp_path: Path, isolated_home: Path, tmp_path_factory: pytest.TempPathFactory):
    """A complete install: a framework checkout as the project, every file in place."""
    root = tmp_path / "repo"
    (root / ".git").mkdir(parents=True)
    write(root / isolated_verify.PINNED, PIN)
    home = isolated_home
    write(root / ".claude" / "settings.json", reference(root, home))
    write(root / ".claude" / "settings.local.json", local(root, home))
    write(home / ".claude" / "settings.json", USER_HOOKS)
    for name in isolated_verify.HOOK_SCRIPTS:
        script = write(home / ".claude" / "scripts" / name, "#!/bin/sh\n")
        script.chmod(0o755)
    write(
        home / ".bashrc",
        "export PATH=$PATH\nsource ~/.claude/scripts/agent-iso.sh\nalias claude='claude-iso'\n",
    )
    managed = tmp_path_factory.mktemp("managed")
    return root, home, managed


def verifier(
    setup,
    *,
    system: str = "Darwin",
    env: dict | None = None,
    run: Fake | None = None,
    which=None,
    framework=None,
):
    root, home, managed = setup
    ctx = Context(
        root=root,
        home=home,
        env={"CLAUDECODE": "1"} if env is None else env,
        system=system,
        framework_arg=framework,
        managed_dirs=(managed,),
        run=run or Fake(),
        which=which or (lambda name: None),
    )
    return Verifier(ctx)


def finding(v: Verifier, n: str) -> dict:
    return next(f for f in v.run()["findings"] if f["check"] == n)


def unreadable(path: Path) -> None:
    path.chmod(0)
    try:
        path.read_bytes()
    except PermissionError:
        return
    pytest.skip("running as a user that ignores file modes")


# -- the whole report -------------------------------------------------------


def test_a_complete_install_passes_every_mechanical_check(setup) -> None:
    report = verifier(setup).run()
    statuses = {f["check"]: f["status"] for f in report["findings"]}
    assert [f["check"] for f in report["findings"]] == [str(n) for n in range(1, 20)]
    for n in ("1", "2", "3", "4", "5", "6", "8", "11"):
        assert statuses[n] == "pass", (n, finding(verifier(setup), n))
    assert statuses["7"] == statuses["18"] == statuses["14"] == "manual"
    assert report["facts"]["framework_found_via"] == "this repository"


def test_cli_prints_the_report(setup, capsys, monkeypatch) -> None:
    root, _, _ = setup
    monkeypatch.setattr(isolated_verify, "_run", Fake())
    assert isolated_verify.main(["check", "--project-root", str(root)]) == 0
    printed = json.loads(capsys.readouterr().out)
    assert len(printed["findings"]) == 19


# -- check 1 ----------------------------------------------------------------


def test_check_1_fails_without_a_home_deny_read(setup) -> None:
    root, home, _ = setup
    settings = reference(root, home)
    settings["sandbox"]["filesystem"]["denyRead"] = []
    write(root / ".claude" / "settings.json", settings)
    result = finding(verifier(setup), "1")
    assert result["status"] == "fail"
    assert "denyRead" in result["evidence"][0]


def test_check_1_accepts_the_absolute_home_and_names_the_carrying_file(setup) -> None:
    root, home, _ = setup
    settings = reference(root, home)
    settings["sandbox"]["filesystem"]["denyRead"] = [str(home)]
    (root / ".claude" / "settings.json").unlink()
    write(root / ".claude" / "settings.local.json", {**settings, **{"x": 1}})
    result = finding(verifier(setup), "1")
    assert result["status"] == "pass"
    assert any(".claude/settings.local.json" in line for line in result["evidence"])
    assert ".claude/settings.json: absent" in result["evidence"]


def test_check_1_is_unknown_when_the_gap_may_hide_in_an_unreadable_file(setup) -> None:
    root, home, _ = setup
    settings = reference(root, home)
    del settings["permissions"]["ask"]
    write(root / ".claude" / "settings.json", settings)
    unreadable(home / ".claude" / "settings.json")
    result = finding(verifier(setup), "1")
    assert result["status"] == "unknown"
    assert result["unreadable"] == ["~/.claude/settings.json (unreadable)"]
    assert result["see"] == "manual-checks.md#check-1--effective-settings-shape"


def test_check_1_fails_when_the_sandbox_is_disabled(setup) -> None:
    root, home, _ = setup
    settings = reference(root, home)
    settings["sandbox"]["enabled"] = False
    write(root / ".claude" / "settings.json", settings)
    assert finding(verifier(setup), "1")["status"] == "fail"


# -- check 2 ----------------------------------------------------------------


def test_check_2_missing_error_hint_hook_is_a_warning(setup) -> None:
    _, home, _ = setup
    hooks = json.loads(json.dumps(USER_HOOKS))
    del hooks["hooks"]["PostToolUse"]
    write(home / ".claude" / "settings.json", hooks)
    assert finding(verifier(setup), "2")["status"] == "warn"


def test_check_2_missing_bypass_warn_hook_fails(setup) -> None:
    _, home, _ = setup
    hooks = json.loads(json.dumps(USER_HOOKS))
    del hooks["hooks"]["PreToolUse"]
    write(home / ".claude" / "settings.json", hooks)
    assert finding(verifier(setup), "2")["status"] == "fail"


def test_check_2_custom_status_line_with_the_prefix_logic_is_a_warning(setup) -> None:
    _, home, _ = setup
    write(home / "bin" / "line.sh", 'echo "[sandbox] $PWD"\necho "[NO SANDBOX]"\n')
    write(home / ".claude" / "settings.json", {**USER_HOOKS, "statusLine": "~/bin/line.sh --flag"})
    result = finding(verifier(setup), "2")
    assert result["status"] == "warn"
    assert "custom" in result["evidence"][-1]


def test_check_2_custom_status_line_without_the_prefix_fails(setup) -> None:
    _, home, _ = setup
    write(home / "bin" / "line.sh", "echo hello\n")
    write(home / ".claude" / "settings.json", {**USER_HOOKS, "statusLine": "~/bin/line.sh"})
    assert finding(verifier(setup), "2")["status"] == "fail"


def test_check_2_absent_user_settings_fail_and_unreadable_ones_are_unknown(setup) -> None:
    _, home, _ = setup
    user = home / ".claude" / "settings.json"
    unreadable(user)
    assert finding(verifier(setup), "2")["status"] == "unknown"
    user.chmod(0o644)
    user.unlink()
    assert finding(verifier(setup), "2")["status"] == "fail"


# -- check 3 ----------------------------------------------------------------


def test_check_3_missing_error_hint_script_is_a_warning(setup) -> None:
    _, home, _ = setup
    (home / ".claude" / "scripts" / "sandbox-error-hint.sh").unlink()
    assert finding(verifier(setup), "3")["status"] == "warn"


@pytest.mark.parametrize("name", ["sandbox-bypass-warn.sh", "sandbox-status-line.sh"])
def test_check_3_missing_or_non_executable_hard_script_fails(setup, name: str) -> None:
    _, home, _ = setup
    script = home / ".claude" / "scripts" / name
    script.chmod(0o644)
    result = finding(verifier(setup), "3")
    assert result["status"] == "fail"
    assert f"{name}: not executable" in result["evidence"]
    script.unlink()
    assert f"{name}: missing" in finding(verifier(setup), "3")["evidence"]


def test_check_3_follows_a_symlink_into_a_sync_repo(setup) -> None:
    _, home, _ = setup
    target = write(home / ".claude-config" / "scripts" / "sandbox-status-line.sh", "#!/bin/sh\n")
    target.chmod(0o755)
    link = home / ".claude" / "scripts" / "sandbox-status-line.sh"
    link.unlink()
    link.symlink_to(target)
    result = finding(verifier(setup), "3")
    assert result["status"] == "pass"
    assert any("~/.claude-config/scripts" in line for line in result["evidence"])
    target.unlink()
    assert finding(verifier(setup), "3")["status"] == "fail"


# -- check 4 ----------------------------------------------------------------


def test_check_4_reports_the_source_line_and_the_alias(setup) -> None:
    result = finding(verifier(setup), "4")
    assert result["status"] == "pass"
    assert "~/.bashrc: source ~/.claude/scripts/agent-iso.sh" in result["evidence"]
    assert any("alias claude='claude-iso' set" in line for line in result["evidence"])


def test_check_4_never_prints_other_rc_lines(setup) -> None:
    _, home, _ = setup
    write(
        home / ".zshrc", "export GH_TOKEN=secret-value\n. /opt/magpie/tools/agent-isolation/claude-iso.sh\n"
    )
    result = finding(verifier(setup), "4")
    assert "secret-value" not in json.dumps(result)
    assert "~/.zshrc: source /opt/magpie/tools/agent-isolation/claude-iso.sh" in result["evidence"]


def test_check_4_fails_without_a_source_line(setup) -> None:
    _, home, _ = setup
    write(home / ".bashrc", "export PATH=$PATH\n# source agent-iso.sh is commented out\n")
    assert finding(verifier(setup), "4")["status"] == "fail"


def test_check_4_is_unknown_when_an_rc_file_is_read_denied(setup) -> None:
    _, home, _ = setup
    write(home / ".bashrc", "export PATH=$PATH\n")
    unreadable(write(home / ".zshrc", "source ~/x/agent-iso.sh\n"))
    result = finding(verifier(setup), "4")
    assert result["status"] == "unknown"
    assert result["unreadable"] == ["~/.zshrc (unreadable)"]


# -- check 5 ----------------------------------------------------------------


def test_check_5_below_the_floor_under_claude_code_is_a_hard_fail(setup) -> None:
    result = finding(verifier(setup, run=Fake({"claude --version": "2.1.100 (Claude Code)"})), "5")
    assert result["status"] == "fail"
    assert "below the min_version floor 2.1.202" in result["evidence"][0]


def test_check_5_below_the_floor_under_another_harness_is_a_warning(setup) -> None:
    run = Fake({"claude --version": "2.1.100"})
    assert finding(verifier(setup, env={"CODEX_SANDBOX": "seatbelt"}, run=run), "5")["status"] == "warn"


@pytest.mark.parametrize(
    "variable",
    [
        "CLAUDE_CODE_USE_BEDROCK",
        "CLAUDE_CODE_USE_VERTEX",
        "DISABLE_TELEMETRY",
        "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC",
    ],
)
def test_check_5_applies_the_stricter_floor_without_telemetry(setup, variable: str) -> None:
    env = {"CLAUDECODE": "1", variable: "1"}
    result = finding(verifier(setup, env=env, run=Fake({"claude --version": "2.1.277 (Claude Code)"})), "5")
    assert result["status"] == "fail"
    assert f"below the min_version floor 2.1.281 ({variable} is set" in result["evidence"][0]


def test_check_5_keeps_the_plain_floor_when_a_provider_variable_is_off(setup) -> None:
    env = {"CLAUDECODE": "1", "CLAUDE_CODE_USE_BEDROCK": "0"}
    result = finding(verifier(setup, env=env, run=Fake({"claude --version": "2.1.277 (Claude Code)"})), "5")
    assert result["status"] == "pass"
    assert "at or above the min_version floor 2.1.202" in result["evidence"][0]


def test_check_5_passes_the_stricter_floor_at_its_release(setup) -> None:
    env = {"CLAUDECODE": "1", "DISABLE_TELEMETRY": "0"}
    result = finding(verifier(setup, env=env, run=Fake({"claude --version": "2.1.281 (Claude Code)"})), "5")
    assert result["status"] == "pass"
    assert "floor 2.1.281 (DISABLE_TELEMETRY is set" in result["evidence"][0]


def test_check_5_compares_versions_numerically(setup) -> None:
    assert finding(verifier(setup, run=Fake({"claude --version": "2.1.1000"})), "5")["status"] == "pass"


def test_check_5_without_a_framework_checkout_warns_and_leaves_pins_unchecked(setup) -> None:
    root, _, _ = setup
    (root / isolated_verify.PINNED).unlink()
    run = Fake({"bwrap --version": "bubblewrap 0.13.1", "socat -V": "socat version 1.8.1.3 on Jan 1"})
    result = finding(verifier(setup, system="Linux", run=run), "5")
    assert result["status"] == "warn"
    assert "not enforced: no framework checkout" in result["evidence"][0]
    assert "claude-code 2.1.210" in result["evidence"][0]
    assert "bubblewrap 0.13.1: pin unchecked, no framework checkout" in result["evidence"]


def test_check_5_linux_pins_match_or_drift(setup) -> None:
    run = Fake(
        {"bwrap --version": "bubblewrap 0.13.1", "socat -V": "socat by Gerhard\nsocat version 1.8.1.3 on Jun"}
    )
    assert finding(verifier(setup, system="Linux", run=run), "5")["status"] == "pass"
    run = Fake({"bwrap --version": "bubblewrap 0.14.0", "socat -V": "socat version 1.8.1.3 on Jun"})
    result = finding(verifier(setup, system="Linux", run=run), "5")
    assert result["status"] == "warn"
    assert "bubblewrap 0.14.0 differs from the pin 0.13.1" in result["evidence"]


def test_check_5_finds_the_checkout_the_shell_rc_sources_from(setup, tmp_path: Path) -> None:
    root, home, _ = setup
    (root / isolated_verify.PINNED).unlink()
    checkout = tmp_path / "magpie"
    write(checkout / isolated_verify.PINNED, PIN)
    write(home / ".bashrc", f"source {checkout}/tools/agent-isolation/agent-iso.sh\n")
    v = verifier(setup)
    assert v.run()["facts"]["framework_checkout"] == str(checkout)
    assert finding(v, "5")["status"] == "pass"


def test_check_5_a_copy_under_the_home_is_not_a_checkout(setup) -> None:
    root, home, _ = setup
    (root / isolated_verify.PINNED).unlink()
    write(home / ".claude" / "agent-isolation" / "pinned-versions.toml", PIN)
    write(home / ".bashrc", "source ~/.claude/agent-isolation/agent-iso.sh\n")
    assert verifier(setup).run()["facts"]["framework_checkout"] is None


def test_check_5_an_explicit_framework_path_wins(setup, tmp_path: Path) -> None:
    other = tmp_path / "clone"
    write(other / isolated_verify.PINNED, PIN.replace("2.1.202", "9.0.0"))
    v = verifier(setup, framework=other)
    assert v.run()["facts"]["framework_found_via"] == "argument"
    assert finding(v, "5")["status"] == "fail"


# -- check 6 ----------------------------------------------------------------


def test_check_6_local_settings_take_precedence(setup) -> None:
    root, home, _ = setup
    write(root / ".claude" / "settings.local.json", {**local(root, home), "sandbox": {"enabled": False}})
    result = finding(verifier(setup), "6")
    assert result["status"] == "fail"
    assert "[NO SANDBOX]" in result["evidence"][0]


def test_check_6_sandbox_only_in_the_unloaded_user_local_file(setup) -> None:
    root, home, _ = setup
    settings = reference(root, home)
    del settings["sandbox"]["enabled"]
    write(root / ".claude" / "settings.json", settings)
    write(home / ".claude" / "settings.local.json", {"sandbox": {"enabled": True}})
    result = finding(verifier(setup), "6")
    assert result["status"] == "fail"
    assert "does not load" in result["evidence"][0]


def test_check_6_unknown_when_a_file_above_the_decider_is_unseen(setup) -> None:
    root, _, _ = setup
    unreadable(root / ".claude" / "settings.local.json")
    assert finding(verifier(setup), "6")["status"] == "unknown"


# -- check 8 ----------------------------------------------------------------


def test_check_8_relative_entries_do_not_count(setup) -> None:
    root, _, _ = setup
    write(
        root / ".claude" / "settings.local.json",
        {"sandbox": {"filesystem": {"allowRead": ["."], "allowWrite": ["."]}}},
    )
    result = finding(verifier(setup), "8")
    assert result["status"] == "fail"
    assert "missing from allowRead and allowWrite" in result["evidence"][0]
    assert result["manual"] == ["live probe"]


def test_check_8_missing_dev_tool_paths_are_a_warning(setup) -> None:
    root, _, _ = setup
    write(
        root / ".claude" / "settings.local.json",
        {"sandbox": {"filesystem": {"allowRead": [str(root)], "allowWrite": [str(root) + "/"]}}},
    )
    result = finding(verifier(setup), "8")
    assert result["status"] == "warn"
    assert "dev-tool paths missing" in result["evidence"][1]


def test_check_8_every_linked_worktree_needs_its_own_entry(setup, tmp_path: Path) -> None:
    root, home, _ = setup
    good, bad = tmp_path / "wt-good", tmp_path / "wt-bad"
    write(good / ".claude" / "settings.local.json", local(good, home))
    write(bad / ".claude" / "settings.local.json", local(root, home))
    listing = f"worktree {root}\nHEAD a\nbranch refs/heads/main\n\nworktree {good}\nHEAD b\n\nworktree {bad}\nHEAD c\n"
    result = finding(verifier(setup, run=Fake({"worktree list --porcelain": listing})), "8")
    assert result["status"] == "fail"
    assert (
        f"{bad}/.claude/settings.local.json: {bad} missing from allowRead and allowWrite"
        in result["evidence"]
    )
    assert f"{good}/.claude/settings.local.json: {good} in allowRead and allowWrite" in result["evidence"]


def test_check_8_a_worktree_not_visible_from_here_is_unknown(setup, tmp_path: Path) -> None:
    root, _, _ = setup
    listing = f"worktree {root}\nHEAD a\n\nworktree {tmp_path / 'gone'}\nHEAD b\nprunable gitdir file points to non-existent location\n"
    result = finding(verifier(setup, run=Fake({"worktree list --porcelain": listing})), "8")
    assert result["status"] == "unknown"
    assert "prunable or not visible" in result["unreadable"][0]


def test_check_8_detects_whole_user_scope(setup) -> None:
    _, home, _ = setup
    run = Fake({"config --global --get core.hooksPath": f"{home}/.claude/git-hooks\n"})
    result = finding(verifier(setup, run=run), "8")
    assert result["manual"] == ["live probe", "whole-user scope sub-checks"]
    assert result["see"].endswith("#check-8--whole-user-scope-detection")


# -- check 11 ---------------------------------------------------------------


@pytest.mark.parametrize(("system", "status"), [("Darwin", "fail"), ("Linux", "warn")])
def test_check_11_missing_gh_exclusion(setup, system: str, status: str) -> None:
    root, home, _ = setup
    settings = reference(root, home)
    settings["sandbox"]["excludedCommands"] = []
    write(root / ".claude" / "settings.json", settings)
    assert finding(verifier(setup, system=system), "11")["status"] == status


def test_check_11b_a_catch_all_gh_ask_rule_fails_in_any_scope(setup) -> None:
    _, home, _ = setup
    write(home / ".claude" / "settings.json", {**USER_HOOKS, "permissions": {"ask": ["Bash(gh *)"]}})
    result = finding(verifier(setup), "11")
    assert result["status"] == "fail"
    assert "~/.claude/settings.json: Bash(gh *)" in result["evidence"][-1]


def test_check_11b_specific_gh_ask_rules_are_fine(setup) -> None:
    _, home, _ = setup
    write(
        home / ".claude" / "settings.json", {**USER_HOOKS, "permissions": {"ask": ["Bash(gh pr create *)"]}}
    )
    assert finding(verifier(setup), "11")["status"] == "pass"


# -- gates ------------------------------------------------------------------


def test_closed_gates_are_not_applicable(setup) -> None:
    statuses = {f["check"]: f["status"] for f in verifier(setup).run()["findings"]}
    for n in ("9", "10", "13", "15", "16", "17"):
        assert statuses[n] == "n/a", n
    assert statuses["19"] == "manual"  # the sandbox is enabled


def test_open_gates_send_the_agent_to_the_conditional_checks(setup) -> None:
    root, home, _ = setup
    settings = reference(root, home)
    # A vetted-op rule opens the gate as the config file does (whose path the sandbox write-denies).
    settings["permissions"]["allow"] = ["Bash(uvx --from ~/.claude/magpie/vetted-ops vetted-op-read *)"]
    settings["permissions"]["blockReadsOutsideWorkingDirectories"] = True
    settings["sandbox"]["excludedCommands"].append(isolated_verify.EVALS_EXCLUSION)
    write(root / ".claude" / "settings.json", settings)
    v = verifier(
        setup,
        env={"CLAUDECODE": "1", "SSH_AUTH_SOCK": f"{home}/.gnupg/S.gpg-agent.ssh"},
        which=lambda name: f"/usr/bin/{name}" if name in ("roborev", "docker") else None,
    )
    found = {f["check"]: f for f in v.run()["findings"]}
    for n, anchor in (
        ("9", "check-9--the-vetted-ops-split-and-exclusion"),
        ("10", "check-10--hardware-key-touch-overlay-and-the-signing-key"),
        ("13", "check-13--eval-harness-exclusion-if-installed"),
        ("15", "check-15--working-directories-under-the-read-block"),
        ("16", "check-16--read-only-vetted-ops-never-prompt"),
        ("17", "check-17--roborev-exclusion-if-installed"),
    ):
        assert found[n]["status"] == "manual", n
        assert found[n]["see"] == f"conditional-checks.md#{anchor}"
    assert "docker" in found["12"]["evidence"][0]


def test_vetted_ops_allowed_without_a_sandbox_fails_check_9(setup) -> None:
    root, home, _ = setup
    settings = reference(root, home)
    settings["sandbox"]["enabled"] = False
    settings["permissions"]["allow"] = ["Bash(uvx --from ~/.claude/magpie/vetted-ops vetted-op-read *)"]
    write(root / ".claude" / "settings.json", settings)
    found = {f["check"]: f["status"] for f in verifier(setup).run()["findings"]}
    assert found["9"] == "fail"
    assert found["16"] == "n/a"
    assert found["19"] == "n/a"


def test_signing_opens_the_check_10_gate(setup) -> None:
    run = Fake({"config --get commit.gpgsign": "true\n"})
    assert finding(verifier(setup, run=run), "10")["status"] == "manual"


def test_the_checker_writes_nothing(setup) -> None:
    root, home, managed = setup

    def snapshot() -> dict[str, float]:
        return {
            str(path): path.lstat().st_mtime for base in (root, home, managed) for path in base.rglob("*")
        }

    before = snapshot()
    verifier(setup).run()
    assert snapshot() == before
    assert not os.listdir(managed)


def _anchors(doc: Path) -> set[str]:
    """GitHub's heading anchors in `doc`."""
    found = set()
    for line in doc.read_text(encoding="utf-8").splitlines():
        if line.startswith("#"):
            title = line.lstrip("#").strip().lower()
            found.add("".join(c for c in title if c.isalnum() or c in " -_").replace(" ", "-"))
    return found


def test_every_see_link_names_a_section_that_exists(setup) -> None:
    skill = Path(isolated_verify.__file__).resolve().parents[2] / "isolated-setup-verify"
    by_hand = _anchors(skill / isolated_verify.BY_HAND)
    conditional = _anchors(skill / isolated_verify.CONDITIONAL)
    assert set(isolated_verify.SECTIONS.values()) <= by_hand
    root, home, _ = setup
    write(
        root / ".claude" / "settings.json", {**reference(root, home), "permissions": {"allow": ["vetted-op"]}}
    )
    run = Fake(
        {
            "config --get commit.gpgsign": "true",
            "config --global --get core.hooksPath": f"{home}/.claude/git-hooks",
        }
    )
    for item in verifier(setup, run=run, which=lambda name: name).run()["findings"]:
        see = item.get("see")
        if see:
            doc, _, anchor = see.partition("#")
            assert anchor in (by_hand if doc == isolated_verify.BY_HAND else conditional), see
