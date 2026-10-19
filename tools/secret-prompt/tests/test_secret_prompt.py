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

"""Tests for secret-prompt: backend choice, the run gates, and the secret staying out of output."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import textwrap
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from secret_prompt import (
    _DENIED_NAMES,
    ASKERS,
    PromptBackendError,
    PromptCancelledError,
    ask_kdialog,
    ask_osascript,
    ask_pinentry,
    ask_zenity,
    candidate_backends,
    is_credential_name,
    main,
)

SRC = Path(__file__).parent.parent / "src"


def _which(*present: str) -> Callable[[str], str | None]:
    return lambda name: f"/usr/bin/{name}" if name in present else None


@pytest.mark.parametrize(
    ("system", "env", "tty", "present", "expected"),
    [
        ("Darwin", {}, True, ("osascript",), ["tty", "osascript"]),
        ("Linux", {"DISPLAY": ":0"}, True, ("zenity",), ["tty", "zenity"]),
        ("Darwin", {}, False, ("osascript", "pinentry"), ["osascript", "pinentry"]),
        ("Linux", {"DISPLAY": ":0"}, False, ("zenity", "kdialog"), ["zenity", "kdialog"]),
        ("Linux", {"WAYLAND_DISPLAY": "wayland-0"}, False, ("kdialog",), ["kdialog"]),
        ("Linux", {}, False, ("zenity", "pinentry"), ["pinentry"]),
        ("Darwin", {}, False, ("pinentry",), ["pinentry"]),
    ],
)
def test_candidate_backends(
    system: str, env: dict[str, str], tty: bool, present: tuple[str, ...], expected: list[str]
) -> None:
    assert candidate_backends(system, env, tty, _which(*present)) == expected


def test_candidate_backends_with_no_way_to_ask() -> None:
    with pytest.raises(PromptBackendError, match="no terminal"):
        candidate_backends("Linux", {}, False, _which())


@pytest.mark.parametrize(
    ("argv", "message"),
    [
        (["--env", "TOKEN"], "after --"),
        (["--env", "NOT-VALID", "--", "true"], "not a valid environment variable"),
        (["--env", "TOKEN", "--set", "NOEQUALS", "--", "true"], "not NAME=VALUE"),
    ],
)
def test_bad_arguments(argv: list[str], message: str, capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        main(argv)
    assert message in capsys.readouterr().err


@pytest.fixture
def exec_calls(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, list[str], dict[str, str]]]:
    calls: list[tuple[str, list[str], dict[str, str]]] = []
    monkeypatch.setattr(os, "execve", lambda file, args, env: calls.append((file, args, env)))
    return calls


def _answer(
    monkeypatch: pytest.MonkeyPatch, value: str | None = None, error: Exception | None = None
) -> None:
    def ask(prompt: str, title: str) -> str | None:
        if error:
            raise error
        return value

    monkeypatch.setitem(ASKERS, "tty", ask)


def test_runs_command_with_secret_and_extra_variables(
    monkeypatch: pytest.MonkeyPatch, exec_calls: list[tuple[str, list[str], dict[str, str]]]
) -> None:
    _answer(monkeypatch, "  pypi-abc123\n")
    main(
        [
            "--env",
            "TWINE_PASSWORD",
            "--set",
            "TWINE_USERNAME=__token__",
            "--backend",
            "tty",
            "--",
            "sh",
            "-c",
            "true",
        ]
    )
    [(file, args, env)] = exec_calls
    sh = os.path.abspath(shutil.which("sh") or "")
    assert (file, args) == (sh, [sh, "-c", "true"])
    assert env["TWINE_PASSWORD"] == "pypi-abc123"
    assert env["TWINE_USERNAME"] == "__token__"


@pytest.mark.parametrize(
    ("value", "error", "reason"),
    [
        ("wrong-abc123", None, "does not start with 'pypi-'"),
        ("   ", None, "no secret entered"),
        (None, PromptCancelledError("prompt cancelled"), "prompt cancelled"),
    ],
)
def test_nothing_runs_unless_a_good_secret_arrives(
    monkeypatch: pytest.MonkeyPatch,
    exec_calls: list[tuple[str, list[str], dict[str, str]]],
    capsys: pytest.CaptureFixture[str],
    value: str | None,
    error: Exception | None,
    reason: str,
) -> None:
    _answer(monkeypatch, value, error)
    rc = main(["--env", "TWINE_PASSWORD", "--prefix", "pypi-", "--backend", "tty", "--", "true"])
    err = capsys.readouterr().err
    assert rc == 1
    assert exec_calls == []
    assert reason in err
    assert "true was not run" in err
    assert "wrong-abc123" not in err


def test_missing_command_is_reported_before_asking(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _answer(monkeypatch, error=AssertionError("must not ask"))
    assert main(["--env", "T", "--backend", "tty", "--", "/nonexistent/secret-prompt-cmd"]) == 127
    assert (
        "cannot run /nonexistent/secret-prompt-cmd: not found; nothing was asked" in capsys.readouterr().err
    )


def _completed(returncode: int, stdout: str = "", stderr: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(["x"], returncode, stdout=stdout, stderr=stderr)


@pytest.mark.parametrize(
    ("result", "error"),
    [
        (_completed(1, stderr="execution error: User canceled. (-128)"), PromptCancelledError),
        (
            _completed(1, stderr="execution error: Not authorized to send Apple events. (-1743)"),
            PromptBackendError,
        ),
    ],
)
def test_osascript_tells_cancel_from_failure(
    monkeypatch: pytest.MonkeyPatch, result: subprocess.CompletedProcess[str], error: type[Exception]
) -> None:
    monkeypatch.setattr(subprocess, "run", lambda cmd, **kwargs: result)
    with pytest.raises(error):
        ask_osascript("Paste it", "PyPI upload")


def test_auto_falls_back_when_a_dialog_cannot_show(
    monkeypatch: pytest.MonkeyPatch, exec_calls: list[tuple[str, list[str], dict[str, str]]]
) -> None:
    def broken(prompt: str, title: str) -> str:
        raise PromptBackendError("osascript failed: Not authorized to send Apple events")

    monkeypatch.setattr("secret_prompt.candidate_backends", lambda *args: ["osascript", "pinentry"])
    monkeypatch.setitem(ASKERS, "osascript", broken)
    monkeypatch.setitem(ASKERS, "pinentry", lambda prompt, title: "pypi-fallback")
    main(["--env", "T", "--", "true"])
    [(_, _, env)] = exec_calls
    assert env["T"] == "pypi-fallback"


def test_auto_stops_at_a_real_cancel(
    monkeypatch: pytest.MonkeyPatch,
    exec_calls: list[tuple[str, list[str], dict[str, str]]],
    capsys: pytest.CaptureFixture[str],
) -> None:
    def cancelled(prompt: str, title: str) -> str:
        raise PromptCancelledError("prompt cancelled")

    asked: list[str] = []
    monkeypatch.setattr("secret_prompt.candidate_backends", lambda *args: ["osascript", "pinentry"])
    monkeypatch.setitem(ASKERS, "osascript", cancelled)

    def never_asked(prompt: str, title: str) -> str:
        asked.append("pinentry")
        return "x"

    monkeypatch.setitem(ASKERS, "pinentry", never_asked)
    assert main(["--env", "T", "--", "true"]) == 1
    assert asked == []
    assert exec_calls == []
    assert "prompt cancelled" in capsys.readouterr().err


def test_forced_backend_that_is_not_installed(
    monkeypatch: pytest.MonkeyPatch,
    exec_calls: list[tuple[str, list[str], dict[str, str]]],
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("PATH", "/nonexistent")
    assert main(["--env", "T", "--backend", "zenity", "--", sys.executable]) == 1
    err = capsys.readouterr().err
    assert "could not ask for the secret (zenity: cannot run zenity" in err
    assert exec_calls == []


def test_osascript_gets_the_prompt_as_an_argument(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[list[str]] = []

    def fake_run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        seen.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, stdout="pypi-xyz\n", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    prompt = 'Paste "it" here'
    assert ask_osascript(prompt, "PyPI upload") == "pypi-xyz\n"
    [cmd] = seen
    assert cmd[-2:] == [prompt, "PyPI upload"]
    assert prompt not in cmd[2]


FAKE_PINENTRY = textwrap.dedent(
    """\
    #!/usr/bin/env bash
    echo "OK Pleased to meet you"
    while read -r line; do
      case "$line" in
        GETPIN) {reply} ;;
        BYE) echo "OK closing connection"; exit 0 ;;
        *) echo OK ;;
      esac
    done
    """
)


def _fake_pinentry(tmp_path: Path, reply: str) -> Path:
    path = tmp_path / "pinentry"
    path.write_text(FAKE_PINENTRY.replace("{reply}", reply))
    path.chmod(0o755)
    return path


def test_pinentry_decodes_the_pin(tmp_path: Path) -> None:
    program = _fake_pinentry(tmp_path, 'echo "D pypi-a%25b"; echo OK')
    assert ask_pinentry("Paste it", "PyPI upload", program=str(program)) == "pypi-a%b"


def test_pinentry_failure_is_not_a_cancel(tmp_path: Path) -> None:
    program = _fake_pinentry(tmp_path, 'echo "ERR 83918950 Inappropriate ioctl for device"')
    with pytest.raises(PromptBackendError, match="Inappropriate ioctl"):
        ask_pinentry("Paste it", "PyPI upload", program=str(program))


def test_pinentry_cancel(tmp_path: Path) -> None:
    program = _fake_pinentry(tmp_path, 'echo "ERR 83886179 Operation cancelled <Pinentry>"')
    with pytest.raises(PromptCancelledError):
        ask_pinentry("Paste it", "PyPI upload", program=str(program))


def test_secret_reaches_only_the_child_environment(tmp_path: Path) -> None:
    _fake_pinentry(tmp_path, 'echo "D pypi-end-to-end"; echo OK')
    env = {**os.environ, "PATH": f"{tmp_path}{os.pathsep}{os.environ['PATH']}", "PYTHONPATH": str(SRC)}
    check = "import os; print(os.environ['UPLOAD_TOKEN'] == 'pypi-end-to-end')"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "secret_prompt",
            "--env",
            "UPLOAD_TOKEN",
            "--prefix",
            "pypi-",
            "--backend",
            "pinentry",
            "--",
            sys.executable,
            "-c",
            check,
        ],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "True"
    assert "pypi-end-to-end" not in result.stdout + result.stderr


def _captured_prompt(monkeypatch: pytest.MonkeyPatch, argv: list[str]) -> str:
    prompts: list[str] = []

    def ask(prompt: str, title: str) -> str:
        prompts.append(prompt)
        return "pypi-abc"

    monkeypatch.setitem(ASKERS, "tty", ask)
    monkeypatch.setattr(os, "execve", lambda file, args, env: None)
    main([*argv[:-1], "--backend", "tty", "--", *argv[-1].split("|")])
    [prompt] = prompts
    return prompt


def test_every_prompt_names_the_resolved_command_and_variables(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TWINE_REPOSITORY_URL", "https://example.invalid/legacy/")
    prompt = _captured_prompt(
        monkeypatch,
        [
            "--env",
            "TWINE_PASSWORD",
            "--prompt",
            "Paste the PyPI token",
            "--set",
            "TWINE_USERNAME=__token__",
            "sh|-c|echo $TWINE_PASSWORD",
        ],
    )
    sh = os.path.abspath(shutil.which("sh") or "")
    assert prompt.splitlines() == [
        "Paste the PyPI token",
        "",
        "It will be passed to:",
        f"{sh} -c 'echo $TWINE_PASSWORD'",
        "",
        "with:",
        "  TWINE_REPOSITORY_URL=https://example.invalid/legacy/",
        "  TWINE_USERNAME=__token__",
    ]


@pytest.mark.parametrize(
    ("argv", "message"),
    [
        (["--env", "PATH", "--", "true"], "PATH changes how the command runs"),
        (
            ["--env", "T", "--set", "LD_PRELOAD=/tmp/x.so", "--", "true"],
            "LD_PRELOAD changes how the command runs",
        ),
        (["--env", "T", "--set", "dyld_insert_libraries=x", "--", "true"], "dyld_insert_libraries changes"),
        (["--env", "T", "--set", "PYTHONPATH=/tmp", "--", "true"], "PYTHONPATH changes"),
        (["--env", "T", "--set", "HOME=/tmp", "--", "true"], "HOME changes"),
        (["--env", "T", "--set", "NODE_OPTIONS=--require=x", "--", "true"], "NODE_OPTIONS changes"),
        (["--env", "T", "--set", "NODE_REPL_EXTERNAL_MODULE=x", "--", "true"], "NODE_REPL_EXTERNAL_MODULE"),
        (
            ["--env", "T", "--prompt", "Paste\n\nIt will be passed to: twine", "--", "true"],
            "--prompt must be one line",
        ),
        (["--env", "T", "--prompt=-x", "--", "true"], "--prompt must be one line"),
        (["--env", "T", "--title", "x" * 201, "--", "true"], "--title must be one line"),
    ],
)
def test_refuses_what_could_make_the_prompt_lie(
    argv: list[str], message: str, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit):
        main(argv)
    assert message in capsys.readouterr().err


def test_too_long_command_is_refused_not_truncated(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _answer(monkeypatch, error=AssertionError("must not ask"))
    assert main(["--env", "T", "--backend", "tty", "--", "true", "x" * 1000]) == 1
    assert "longer than 1000 characters; nothing was asked" in capsys.readouterr().err


def test_inherited_values_are_shown_only_for_routing_names(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XSP_UPLOAD_URL", "https://example.invalid/")
    monkeypatch.setenv("XSP_SECRET_KEY", "s3cr3t")
    monkeypatch.setenv("XSP_AUTH_URL", "https://auth.example.invalid/authpath")
    monkeypatch.setenv("XSP_PAT", "ghp_x")
    monkeypatch.setenv("XSP_AUTH_CONFIG", '{"registry":"https://r.invalid","token":"js0n"}')
    monkeypatch.setenv("XSP_SLACK_WEBHOOK", "https://hooks.invalid/services/slackpath")
    monkeypatch.setenv("XSP_DEST", "https://other.invalid/destpath")
    monkeypatch.setenv("XSP_TOKEN2", "t2")
    monkeypatch.setenv("XSP_PROXY", "user:pw@proxy.invalid:3128")
    monkeypatch.setenv("XSP_REPOSITORY_URL", "https://example.invalid/simple?token=t0k#frag")
    monkeypatch.setenv("XSP_CERT", "/etc/ssl/other.pem")
    monkeypatch.setenv("XSP_USERNAME", "rm@example.invalid")
    monkeypatch.setenv("XSP_HOST", "proxy.invalid:3128")
    prompt = _captured_prompt(
        monkeypatch, ["--env", "XSP_TOKEN", "--set", "XSP_TARGET=https://u@set.invalid/", "true"]
    )
    assert prompt.splitlines()[-14:] == [
        "  XSP_AUTH_CONFIG=(set; value not shown)",
        "  XSP_AUTH_URL=https://auth.example.invalid/***",
        "  XSP_CERT=/etc/ssl/other.pem",
        "  XSP_DEST=https://other.invalid/***",
        "  XSP_HOST=proxy.invalid:3128",
        "  XSP_PAT=(set; value not shown)",
        "  XSP_PROXY=(set; value not shown)",
        "  XSP_REPOSITORY_URL=https://example.invalid/simple?***#***",
        "  XSP_SECRET_KEY=(set; value not shown)",
        "  XSP_SLACK_WEBHOOK=https://hooks.invalid/***",
        "  XSP_TARGET=https://u@set.invalid/",
        "  XSP_TOKEN2=(set; value not shown)",
        "  XSP_UPLOAD_URL=https://example.invalid/",
        "  XSP_USERNAME=rm@example.invalid",
    ]
    for leaked in (
        "s3cr3t",
        "ghp_x",
        "t0k",
        "frag",
        "js0n",
        "authpath",
        "slackpath",
        "destpath",
        "t2",
        "pw@",
    ):
        assert leaked not in prompt


@pytest.mark.parametrize(
    ("name", "value", "message"),
    [
        (
            "XSP_INDEX_URL",
            "https://__token__:pypi-Ag/E@upload.invalid/",
            "XSP_INDEX_URL is a URL with a user",
        ),
        ("XSP_ASKPASS", "/tmp/grab.sh", "XSP_ASKPASS changes how the command runs"),
        (
            "XSP_INDEX_URL",
            "'https://host.invalid/simple?token=t0k'",
            "XSP_INDEX_URL is not a URL it can show",
        ),
        ("XSP_HOST", "tok@proxy.invalid:3128", "XSP_HOST may hold a user, password or token; unset it"),
        ("XSP_USER", "user:pw@proxy.invalid", "XSP_USER may hold a user, password or token"),
        ("XSP_USER", "alice:s3cret", "XSP_USER may hold a user, password or token"),
        ("XSP_INDEX", "host.invalid/simple?token=t0k", "XSP_INDEX may hold a user, password or token"),
        (
            "XSP_API_TOKEN",
            "https://u:p/w@host.invalid/",
            "XSP_API_TOKEN is a URL with a user or password; unset it, or remove",
        ),
    ],
)
def test_inherited_variable_that_cannot_be_shown_safely_is_refused(
    name: str,
    value: str,
    message: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv(name, value)
    monkeypatch.setattr("secret_prompt._DENIED_NAMES", {*_DENIED_NAMES, "XSP_ASKPASS"})
    _answer(monkeypatch, error=AssertionError("must not ask"))
    assert main(["--env", "XSP_TOKEN", "--backend", "tty", "--", "true"]) == 1
    assert message in capsys.readouterr().err


@pytest.mark.parametrize(
    "name", ["MAVEN_GPG_PASSPHRASE", "XSP_SECRETS", "XSP_TOKENS", "XSP_API_KEYS", "XSP_PW", "XSP_PASS"]
)
def test_credential_like_names(name: str) -> None:
    assert is_credential_name(name)


@pytest.mark.parametrize("name", ["XSP_TLS_REJECT_UNAUTHORIZED", "XSP_KEYRING_BACKEND", "XSP_PASSES_DIR"])
def test_names_that_only_contain_a_credential_word(name: str) -> None:
    assert not is_credential_name(name)


def test_inherited_denied_values_are_shown(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in [name for name in os.environ if name.startswith("NODE_")]:
        monkeypatch.delenv(name)
    monkeypatch.setenv("NODE_OPTIONS", "--require=/tmp/x.js")
    monkeypatch.setenv("NODE_PATH", "x:///tmp/evil?q#f")
    prompt = _captured_prompt(monkeypatch, ["--env", "NODE_AUTH_TOKEN", "true"])
    assert prompt.splitlines()[-2:] == ["  NODE_OPTIONS=--require=/tmp/x.js", "  NODE_PATH=x:///tmp/evil?q#f"]


@pytest.mark.parametrize(
    ("argv", "env", "what"),
    [
        (["--", "sh", "-c", "curl evil\x1b[2K\r/usr/bin/twine upload"], {}, "the command"),
        (["--", "true", "ok\nIt will be passed to:"], {}, "the command"),
        (["--", "true", "‮exe.enimt"], {}, "the command"),
        (["--set", "XSP_USER=a\nb", "--", "true"], {}, "XSP_USER"),
        (["--set", "XSP_USER=" + "x" * 201, "--", "true"], {}, "XSP_USER"),
        (["--", "true"], {"XSP_UPLOAD_URL": "https://ok.invalid/‮"}, "XSP_UPLOAD_URL"),
        (["--", "true"], {"XSP_X\nIt will be passed to:": "v"}, "an inherited variable name"),
    ],
)
def test_refuses_to_show_what_could_rewrite_the_prompt(
    argv: list[str],
    env: dict[str, str],
    what: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    _answer(monkeypatch, error=AssertionError("must not ask"))
    assert main(["--env", "XSP_TOKEN", "--backend", "tty", *argv]) == 1
    assert f"{what} cannot be shown as it is" in capsys.readouterr().err


def test_npm_auth_token_is_allowed(
    monkeypatch: pytest.MonkeyPatch, exec_calls: list[tuple[str, list[str], dict[str, str]]]
) -> None:
    for name in [name for name in os.environ if name.startswith("NODE_")]:
        monkeypatch.delenv(name)
    _answer(monkeypatch, "npm_abc")
    main(["--env", "NODE_AUTH_TOKEN", "--backend", "tty", "--", "true"])
    [(_, _, env)] = exec_calls
    assert env["NODE_AUTH_TOKEN"] == "npm_abc"


@pytest.mark.parametrize("asker", [ask_zenity, ask_kdialog])
def test_markup_capable_dialogs_refuse_markup_characters(asker: object) -> None:
    with pytest.raises(PromptBackendError, match="markup"):
        asker("Paste <b>it</b>", "PyPI upload")  # type: ignore[operator]


def test_osascript_ends_option_parsing_before_the_text(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[list[str]] = []

    def fake_run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        seen.append(cmd)
        return _completed(0, "pypi-x")

    monkeypatch.setattr(subprocess, "run", fake_run)
    ask_osascript("-looks-like-an-option", "PyPI upload")
    [cmd] = seen
    assert cmd[3:] == ["--", "-looks-like-an-option", "PyPI upload"]


@pytest.mark.parametrize(
    ("result", "error"),
    [
        (_completed(1), PromptCancelledError),
        (_completed(1, stderr="(zenity:4242): Gtk-WARNING **: cannot open display: :0"), PromptBackendError),
    ],
)
def test_zenity_tells_cancel_from_a_missing_display(
    monkeypatch: pytest.MonkeyPatch, result: subprocess.CompletedProcess[str], error: type[Exception]
) -> None:
    monkeypatch.setattr(subprocess, "run", lambda cmd, **kwargs: result)
    with pytest.raises(error):
        ask_zenity("Paste it", "PyPI upload")
