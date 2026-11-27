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
        "permissions": {
            "deny": [
                "Bash(curl *)",
                *isolated_verify.UV_DENIES,
                isolated_verify.PREK_DENY,
                isolated_verify.PNPM_DENY,
            ],
            "ask": ["Bash(git push *)"],
        },
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
    write(home / isolated_verify.UV_CONFIG, f'cache-dir = "{home}/.local/share/uv-host/cache"\n')
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
    implicit_writable: tuple[str, ...] = (),
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
        # The temporary home sits under /var/folders on macOS; the tests that need these roots pass them.
        implicit_writable=implicit_writable,
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
    assert [f["check"] for f in report["findings"]] == [str(n) for n in range(1, 22)]
    for n in ("1", "2", "3", "4", "5", "6", "8", "11", "19"):
        assert statuses[n] == "pass", (n, finding(verifier(setup), n))
    assert statuses["7"] == statuses["18"] == statuses["14"] == statuses["20"] == statuses["21"] == "manual"
    assert report["facts"]["framework_found_via"] == "this repository"


def test_cli_prints_the_report(setup, capsys, monkeypatch) -> None:
    root, _, _ = setup
    monkeypatch.setattr(isolated_verify, "_run", Fake())
    assert isolated_verify.main(["check", "--project-root", str(root)]) == 0
    printed = json.loads(capsys.readouterr().out)
    assert len(printed["findings"]) == 21


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


# -- check 19 ---------------------------------------------------------------


def part(result: dict, prefix: str) -> list[str]:
    return [line for line in result["evidence"] if line.startswith(prefix)]


def with_settings(setup, change) -> None:
    """Rewrite the project settings with `change` applied to them."""
    root, home, _ = setup
    settings = reference(root, home)
    change(settings)
    write(root / ".claude" / "settings.json", settings)


def test_check_19_passes_and_lists_the_live_probes(setup) -> None:
    result = finding(verifier(setup), "19")
    assert result["status"] == "pass", result
    assert {line[:3] for line in result["evidence"]} == {"19a", "19b", "19c", "19d", "19e"}
    assert any("uv cache dir" in item for item in result["manual"])
    assert not any("write into ~/.cache/prek" in item for item in result["manual"])  # no prek here
    assert result["see"] == "manual-checks.md#check-19--host-only-uv-and-prek-state"


def test_check_19_is_not_applicable_without_a_sandbox(setup) -> None:
    with_settings(setup, lambda s: s["sandbox"].update(enabled=False))
    assert finding(verifier(setup), "19")["status"] == "n/a"


@pytest.mark.parametrize(
    "key, entry",
    [
        (("sandbox", "filesystem", "allowWrite"), "~/.local/share/uv/"),
        (("permissions", "additionalDirectories"), "~/.local"),
        (("sandbox", "filesystem", "allowWrite"), "$HOME/.local/share/uv"),
    ],
)
def test_check_19a_a_write_grant_covering_the_uv_data_dir_fails(setup, key, entry) -> None:
    def change(settings: dict) -> None:
        node = settings
        for name in key[:-1]:
            node = node.setdefault(name, {})
        node.setdefault(key[-1], []).append(entry)

    with_settings(setup, change)
    result = finding(verifier(setup), "19")
    assert result["status"] == "fail"
    assert part(result, "19a") == [
        f"19a: ~/.local/share/uv writable: .claude/settings.json: {'.'.join(key)} {entry!r}"
    ]


def test_check_19a_a_read_grant_is_fine(setup) -> None:
    with_settings(setup, lambda s: s["sandbox"]["filesystem"]["allowRead"].append("~/.local/share/uv"))
    assert part(finding(verifier(setup), "19"), "19a")[0].startswith("19a: no allowWrite")


def test_check_19_is_unknown_when_a_settings_file_is_unreadable(setup) -> None:
    _, home, _ = setup
    unreadable(home / ".claude" / "settings.json")
    result = finding(verifier(setup), "19")
    assert result["status"] == "unknown"
    assert result["unreadable"] == ["~/.claude/settings.json (unreadable)"]
    assert result["see"] == "manual-checks.md#check-19--host-only-uv-and-prek-state"


def test_check_19_a_gap_found_beats_an_unreadable_file(setup) -> None:
    _, home, _ = setup
    with_settings(setup, lambda s: s["sandbox"]["filesystem"]["allowWrite"].append("~/.local/share/uv"))
    unreadable(home / ".claude" / "settings.json")
    assert finding(verifier(setup), "19")["status"] == "fail"


def test_check_19b_an_unreadable_uv_config_is_unknown(setup) -> None:
    _, home, _ = setup
    unreadable(home / isolated_verify.UV_CONFIG)
    result = finding(verifier(setup), "19")
    assert result["status"] == "unknown"
    assert result["unreadable"] == ["~/.config/uv/uv.toml (unreadable)"]


@pytest.mark.parametrize(
    "content, wording",
    [
        (None, "missing"),
        ("not = [toml", "not valid TOML"),
        ("python-preference = 'managed'\n", "sets no cache-dir"),
        ('cache-dir = "~/.local/share/uv-host/cache"\n', "not absolute"),
        ('cache-dir = "uv-host/cache"\n', "not absolute"),
    ],
)
def test_check_19b_a_missing_or_relative_host_cache_fails(setup, content, wording) -> None:
    _, home, _ = setup
    config = home / isolated_verify.UV_CONFIG
    if content is None:
        config.unlink()
    else:
        write(config, content)
    result = finding(verifier(setup), "19")
    assert result["status"] == "fail"
    assert wording in part(result, "19b")[0]


def test_check_19b_a_cache_inside_a_writable_directory_fails(setup) -> None:
    _, home, _ = setup
    write(home / isolated_verify.UV_CONFIG, f'cache-dir = "{home}/.cache/uv-host"\n')
    result = finding(verifier(setup), "19")
    assert result["status"] == "fail"
    assert "~/.cache" in part(result, "19b")[0]


def test_check_19b_a_writable_root_inside_the_cache_fails(setup) -> None:
    with_settings(
        setup,
        lambda s: s["sandbox"]["filesystem"]["allowWrite"].append("~/.local/share/uv-host/cache/sandbox"),
    )
    assert "overlaps" in part(finding(verifier(setup), "19"), "19b")[0]


def test_check_19b_resolves_symlinks_and_the_project_root(setup) -> None:
    root, home, _ = setup
    (home / "link").symlink_to(root)
    write(home / isolated_verify.UV_CONFIG, f'cache-dir = "{home}/link/uv-cache"\n')
    result = finding(verifier(setup), "19")
    assert result["status"] == "fail"
    assert "project root" in part(result, "19b")[0]


def test_check_19b_the_sandbox_writes_temporary_roots_without_a_grant(setup) -> None:
    _, home, _ = setup
    write(home / isolated_verify.UV_CONFIG, 'cache-dir = "/tmp/uv-host"\n')
    v = verifier(setup, implicit_writable=isolated_verify.IMPLICIT_WRITABLE)
    assert "/tmp" in part(finding(v, "19"), "19b")[0]
    write(home / isolated_verify.UV_CONFIG, 'cache-dir = "/srv/uv-host"\n')
    tmpdir = verifier(setup, env={"CLAUDECODE": "1", "TMPDIR": "/srv"})
    assert "$TMPDIR" in part(finding(tmpdir, "19"), "19b")[0]


@pytest.mark.parametrize(
    "rule, sub",
    [
        ("Read(~/.config/uv/uv.toml)", "19c"),
        ("Edit(~/.config/uv/**)", "19c"),
        (isolated_verify.PREK_DENY, "19d"),
        (isolated_verify.PNPM_DENY, "19e"),
    ],
)
def test_check_19_a_missing_deny_rule_fails(setup, rule, sub) -> None:
    with_settings(setup, lambda s: s["permissions"]["deny"].remove(rule))
    result = finding(verifier(setup), "19")
    assert result["status"] == "fail"
    assert rule in part(result, sub)[0] and "lacks" in part(result, sub)[0]


def test_check_19_a_broader_deny_rule_covers_a_narrower_one(setup) -> None:
    def change(settings: dict) -> None:
        settings["permissions"]["deny"].remove("Edit(~/.config/uv/**)")
        settings["permissions"]["deny"].append("Edit(~/.config/**)")

    with_settings(setup, change)
    assert finding(verifier(setup), "19")["status"] == "pass"


def test_check_19_a_missing_deny_may_hide_in_an_unreadable_file(setup) -> None:
    _, home, _ = setup
    with_settings(setup, lambda s: s["permissions"]["deny"].remove(isolated_verify.PNPM_DENY))
    unreadable(home / ".claude" / "settings.json")
    assert finding(verifier(setup), "19")["status"] == "unknown"


@pytest.mark.parametrize(
    "prek_home, status",
    [
        (None, "fail"),
        ("~/.cache/prek", "fail"),
        ("~/.cache/prek/sandbox", "fail"),
        ("~/.cache", "fail"),
        ("~/.cache/prek-sandbox", "pass"),
    ],
)
def test_check_19d_a_prek_project_needs_its_own_home(setup, prek_home, status) -> None:
    root, _, _ = setup
    write(root / "prek.toml", "")
    if prek_home is not None:
        with_settings(setup, lambda s: s.setdefault("env", {}).update(PREK_HOME=prek_home))
    result = finding(verifier(setup), "19")
    assert result["status"] == status, result
    assert "PREK_HOME" in part(result, "19d")[1]
    assert any("write into ~/.cache/prek" in item for item in result["manual"])


def test_check_19d_detects_prek_through_an_installed_git_hook(setup) -> None:
    root, _, _ = setup
    write(root / ".git" / "hooks" / "pre-commit", "#!/bin/sh\nexec prek hook-impl\n")
    assert "env.PREK_HOME missing" in part(finding(verifier(setup), "19"), "19d")[1]


def test_check_19d_the_local_file_overrides_the_project_home(setup) -> None:
    root, home, _ = setup
    write(root / "prek.toml", "")
    with_settings(setup, lambda s: s.setdefault("env", {}).update(PREK_HOME="~/.cache/prek-sandbox"))
    write(
        root / ".claude" / "settings.local.json", {**local(root, home), "env": {"PREK_HOME": "~/.cache/prek"}}
    )
    assert "overlaps" in part(finding(verifier(setup), "19"), "19d")[1]


PNPM_PROJECT: dict[str, str | None] = {
    "ls-files -- :(glob)**/pnpm-lock.yaml :(glob)**/pnpm-workspace.yaml": "pnpm-lock.yaml\n"
}


def pnpm_ready(setup, **env: str | None) -> None:
    """A pnpm project wired as install Step U proposes, with `env` overriding the env entries."""
    _, home, _ = setup
    pnpm_home = "~/.local/share/pnpm-sandbox/demo"
    values = {
        "PNPM_HOME": pnpm_home,
        "npm_config_cache_dir": f"{pnpm_home}/cache",
        "npm_config_cache": f"{pnpm_home}/npm-cache",
        **env,
    }

    def change(settings: dict) -> None:
        settings["env"] = {key: value for key, value in values.items() if value is not None}
        settings["sandbox"]["filesystem"]["allowRead"].append(f"{pnpm_home}/")
        settings["sandbox"]["filesystem"]["allowWrite"].append(f"{pnpm_home}/")

    with_settings(setup, change)
    (home / ".local" / "share" / "pnpm-sandbox" / "demo").mkdir(parents=True, exist_ok=True)


def test_check_19e_a_wired_pnpm_project_passes(setup) -> None:
    pnpm_ready(setup)
    result = finding(verifier(setup, run=Fake(PNPM_PROJECT)), "19")
    assert result["status"] == "pass", result
    assert any("exists" in line for line in part(result, "19e"))


def test_check_19e_the_absolute_home_spelling_is_accepted(setup) -> None:
    _, home, _ = setup
    absolute = f"{home}/.local/share/pnpm-sandbox/demo"
    pnpm_ready(
        setup,
        PNPM_HOME=absolute,
        npm_config_cache_dir=f"{absolute}/cache",
        npm_config_cache=f"{absolute}/npm-cache",
    )
    assert finding(verifier(setup, run=Fake(PNPM_PROJECT)), "19")["status"] == "pass"


@pytest.mark.parametrize(
    "env, wording",
    [
        ({"PNPM_HOME": None}, "env.PNPM_HOME is missing"),
        ({"PNPM_HOME": "~/.cache/pnpm-sandbox/demo"}, "is not exactly"),
        ({"PNPM_HOME": "~/.local/share/./pnpm-sandbox/demo"}, "is not exactly"),
        ({"PNPM_HOME": "~/.local/share/pnpm-sandbox/Demo"}, "is not exactly"),
        ({"npm_config_cache_dir": None}, "npm_config_cache_dir missing"),
        ({"npm_config_cache_dir": "~/.cache/pnpm"}, "is not ~/.local/share/pnpm-sandbox/demo/cache"),
    ],
)
def test_check_19e_a_pnpm_project_home_spelled_or_set_wrong_fails(setup, env, wording) -> None:
    pnpm_ready(setup, **env)
    result = finding(verifier(setup, run=Fake(PNPM_PROJECT)), "19")
    assert result["status"] == "fail", result
    assert any(wording in line for line in part(result, "19e")), result["evidence"]


def test_check_19e_a_home_not_granted_or_not_created_fails(setup) -> None:
    root, home, _ = setup
    pnpm_ready(setup)
    settings = json.loads((root / ".claude" / "settings.json").read_text())
    settings["sandbox"]["filesystem"]["allowWrite"].remove("~/.local/share/pnpm-sandbox/demo/")
    write(root / ".claude" / "settings.json", settings)
    (home / ".local" / "share" / "pnpm-sandbox" / "demo").rmdir()
    result = finding(verifier(setup, run=Fake(PNPM_PROJECT)), "19")
    assert result["status"] == "fail"
    lines = part(result, "19e")
    assert any("not in sandbox.filesystem.allowWrite" in line for line in lines)
    assert any("does not exist on disk" in line for line in lines)


@pytest.mark.parametrize(
    "env, wording",
    [
        ({"npm_config_cache": None}, "npm_config_cache missing"),
        ({"npm_config_cache": "~/.npm"}, "is not ~/.local/share/pnpm-sandbox/demo/npm-cache"),
        ({"npm_config_enable_global_virtual_store": "true"}, "npm_config_enable_global_virtual_store = true"),
    ],
)
def test_check_19e_npm_cache_and_global_virtual_store_are_drift(setup, env, wording) -> None:
    pnpm_ready(setup, **env)
    result = finding(verifier(setup, run=Fake(PNPM_PROJECT)), "19")
    assert result["status"] == "warn", result
    assert any(wording in line for line in part(result, "19e")), result["evidence"]


def test_check_19e_a_project_without_pnpm_needs_no_home(setup) -> None:
    assert "does not use pnpm" in part(finding(verifier(setup), "19"), "19e")[-1]


@pytest.mark.parametrize("entry", ["~/.local/share/pnpm-sandbox/", "~/.local/share"])
def test_check_19e_granting_every_pnpm_home_fails_in_any_project(setup, entry) -> None:
    with_settings(setup, lambda s: s["sandbox"]["filesystem"]["allowWrite"].append(entry))
    result = finding(verifier(setup), "19")
    assert result["status"] == "fail"
    assert any("grants ~/.local/share/pnpm-sandbox/ itself" in line for line in part(result, "19e"))


@pytest.mark.parametrize(
    "key", ["npm_config_store_dir", "npm-config-state-dir", "npm_config_virtual_store_dir"]
)
def test_check_19e_moving_pnpm_store_or_state_fails_in_any_project(setup, key) -> None:
    with_settings(setup, lambda s: s.setdefault("env", {}).update({key: "~/.cache/pnpm-store"}))
    result = finding(verifier(setup), "19")
    assert result["status"] == "fail"
    assert any(f"env.{key}" in line for line in part(result, "19e"))


# -- gates ------------------------------------------------------------------


def test_closed_gates_are_not_applicable(setup) -> None:
    statuses = {f["check"]: f["status"] for f in verifier(setup).run()["findings"]}
    for n in ("9", "10", "13", "15", "16", "17"):
        assert statuses[n] == "n/a", n
    assert statuses["19"] == "pass"  # the sandbox is enabled, so check 19 applies


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
