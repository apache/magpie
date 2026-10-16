# SPDX-License-Identifier: Apache-2.0
# https://www.apache.org/licenses/LICENSE-2.0
from __future__ import annotations

import importlib.util
import io
import json
import os
import pwd
import shlex
import shutil
import subprocess
from pathlib import Path

import pytest

from vetted_ops.codex import render_hook, render_rules

HOOK = Path(__file__).resolve().parents[1] / "hooks" / "codex-expand-stable-path.py"
_spec = importlib.util.spec_from_file_location("codex_expand_stable_path", HOOK)
assert _spec and _spec.loader
hook = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hook)

ABS = "/home/alice/.claude/magpie/vetted-ops"


@pytest.mark.parametrize(
    "command,expected",
    [
        (
            "uv run --project ~/.claude/magpie/vetted-ops vetted-op-read pr-view --caller x 1",
            f"uv run --project {ABS} vetted-op-read pr-view --caller x 1",
        ),
        (
            "uvx --from ~/.claude/magpie/vetted-ops vetted-op-read q --title 'a b' --body \"c d\"",
            f"uvx --from {ABS} vetted-op-read q --title 'a b' --body \"c d\"",
        ),
        (
            "  uv run --project ~/.claude/magpie/vetted-ops vetted-op-read  ",
            f"uv run --project {ABS} vetted-op-read",
        ),
    ],
)
def test_rewrites_a_lone_read_call(command: str, expected: str) -> None:
    assert hook.rewrite(command, ABS) == expected


@pytest.mark.parametrize(
    "command",
    [
        # Write entry points must always prompt, so the hook never touches them.
        "uv run --project ~/.claude/magpie/vetted-ops vetted-op x",
        "uvx --from ~/.claude/magpie/vetted-ops vetted-op-tracker status",
        # Anything beyond one plain read call.
        "uv run --project ~/.claude/magpie/vetted-ops vetted-op-read x; rm -rf ~",
        "uv run --project ~/.claude/magpie/vetted-ops vetted-op-read x && touch /outside",
        "cd /repo && uv run --project ~/.claude/magpie/vetted-ops vetted-op-read x",
        "uv run --project ~/.claude/magpie/vetted-ops vetted-op-read x | sh",
        "uv run --project ~/.claude/magpie/vetted-ops vetted-op-read x > out",
        'uv run --project ~/.claude/magpie/vetted-ops vetted-op-read "$(id)"',
        "uv run --project ~/.claude/magpie/vetted-ops vetted-op-read `id`",
        "uv run --project ~/.claude/magpie/vetted-ops vetted-op-read $HOME",
        "uv run --project ~/.claude/magpie/vetted-ops vetted-op-read ~/x",
        "uv run --project ~/.claude/magpie/vetted-ops vetted-op-read x\nrm -rf ~",
        "cat > run.sh <<'EOF'\nuv run --project ~/.claude/magpie/vetted-ops vetted-op-read x\nEOF",
        # Other spellings of the path or launcher.
        "uv run --project '~/.claude/magpie/vetted-ops' vetted-op-read x",
        'uv run --project "~/.claude/magpie/vetted-ops" vetted-op-read x',
        'echo "uv run --project ~/.claude/magpie/vetted-ops vetted-op-read x"',
        "uv run --project \\~/.claude/magpie/vetted-ops vetted-op-read x",
        "uv run --project ~/.claude/magpie/vetted-ops-evil vetted-op-read x",
        "uv run --project ~/.claude/magpie/vetted-ops/../planted vetted-op-read x",
        "uv run --project=~/.claude/magpie/vetted-ops vetted-op-read x",
        "uv run --project ~other/.claude/magpie/vetted-ops vetted-op-read x",
        "xuv run --project ~/.claude/magpie/vetted-ops vetted-op-read x",
        "uv run --with evil --project ~/.claude/magpie/vetted-ops vetted-op-read x",
        "uv run --project ~/.claude/magpie/vetted-ops vetted-op-reader x",
    ],
)
def test_leaves_everything_else_alone(command: str) -> None:
    assert hook.rewrite(command, ABS) == command


def test_home_comes_from_passwd_not_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", "/tmp/planted")
    expected = os.path.join(pwd.getpwuid(os.getuid()).pw_dir, ".claude/magpie/vetted-ops")
    assert hook.stable_path() == expected
    assert "/tmp/planted" not in hook.rewrite("uv run --project ~/.claude/magpie/vetted-ops vetted-op-read x")


def test_a_home_with_spaces_is_quoted() -> None:
    rewritten = hook.rewrite("uv run --project ~/.claude/magpie/vetted-ops vetted-op-read x", "/home/a b/v")
    assert shlex.split(rewritten)[3] == "/home/a b/v"


def _run_main(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], stdin: str) -> str:
    monkeypatch.setattr("sys.stdin", io.StringIO(stdin))
    assert hook.main([]) == 0
    return capsys.readouterr().out


def test_hook_output_carries_only_the_rewrite(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    command = "uv run --project ~/.claude/magpie/vetted-ops vetted-op-read x"
    event = {
        "tool_name": "Bash",
        "turn_id": "turn-1",
        "model": "gpt",
        "tool_input": {"command": command},
    }
    out = json.loads(_run_main(monkeypatch, capsys, json.dumps(event)))
    specific = out["hookSpecificOutput"]
    assert set(out) == {"hookSpecificOutput"}
    assert specific["hookEventName"] == "PreToolUse"
    assert specific["permissionDecision"] == "allow"
    assert specific["updatedInput"] == {"command": hook.rewrite(command)}


@pytest.mark.parametrize(
    "stdin",
    [
        json.dumps({"turn_id": "t", "model": "m", "tool_input": {"command": "ls ~/.claude"}}),
        # A Claude Code event (no turn_id/model): never emit, since Claude Code
        # would read the "allow" as a permission grant for the whole command.
        json.dumps(
            {
                "session_id": "s",
                "transcript_path": "/t",
                "permission_mode": "default",
                "tool_name": "Bash",
                "tool_input": {
                    "command": "uv run --project ~/.claude/magpie/vetted-ops vetted-op-read x; rm -rf ~"
                },
            }
        ),
        json.dumps({"tool_input": {"command": ["uv", "run"]}}),
        json.dumps({"tool_name": "Bash"}),
        "not json",
    ],
)
def test_hook_is_silent_when_there_is_nothing_to_rewrite(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], stdin: str
) -> None:
    assert _run_main(monkeypatch, capsys, stdin) == ""


def test_rendered_stable_path_is_what_the_hook_writes(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    root = tmp_path / "home" / ".claude/magpie/vetted-ops"
    argv = shlex.split(render_hook(root).split("command = ", 1)[1].splitlines()[0].strip('"'))[2:]
    assert argv == ["--stable-path", str(root)]
    monkeypatch.setattr(
        "sys.stdin",
        io.StringIO(
            json.dumps(
                {
                    "turn_id": "t",
                    "model": "m",
                    "tool_input": {"command": "uvx --from ~/.claude/magpie/vetted-ops vetted-op-read x"},
                }
            )
        ),
    )
    assert hook.main(argv) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["hookSpecificOutput"]["updatedInput"] == {"command": f"uvx --from {root} vetted-op-read x"}


def test_render_hook_names_the_absolute_script(tmp_path: Path) -> None:
    text = render_hook(tmp_path / "stable path")
    assert str(tmp_path / "stable path" / "hooks" / "codex-expand-stable-path.py") in text
    assert '"^Bash$"' in text
    assert "~" not in text.replace("# ", "")


def test_render_hook_refuses_a_relative_root() -> None:
    with pytest.raises(ValueError):
        render_hook(Path("relative"))


@pytest.mark.skipif(shutil.which("codex") is None, reason="native Codex evaluator unavailable")
@pytest.mark.parametrize("launcher", ["uv run --project", "uvx --from"])
def test_rewritten_read_matches_the_absolute_allow_rule(tmp_path: Path, launcher: str) -> None:
    base = tmp_path / ".claude/magpie/vetted-ops"
    rules = tmp_path / "vetted.rules"
    rules.write_text(render_rules(base))
    skill_command = f"{launcher} ~/.claude/magpie/vetted-ops vetted-op-read --caller test viewer"

    def check(tokens: list[str]) -> str | None:
        proc = subprocess.run(
            ["codex", "execpolicy", "check", "--rules", str(rules), "--", *tokens],
            text=True,
            capture_output=True,
            check=True,
        )
        return json.loads(proc.stdout).get("decision")

    assert check(shlex.split(skill_command)) is None
    assert check(shlex.split(hook.rewrite(skill_command, str(base)))) == "allow"
