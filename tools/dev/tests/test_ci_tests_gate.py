# SPDX-License-Identifier: Apache-2.0
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

"""Exercise the actual tests-ok shell gate, including discovery failures.

The field reader supports literal needs lists (inline or block), scalar
conditions, quotes, and comments. It is not a general YAML parser: aliases,
tags, and folded scalars are outside this workflow test's supported syntax.
"""

from __future__ import annotations

import os
import re
import shlex
import shutil
import subprocess
from pathlib import Path
from textwrap import dedent
from typing import NoReturn

import pytest

_WORKFLOW = Path(__file__).resolve().parents[3] / ".github/workflows/tests.yml"
_RESULTS = ("success", "failure", "cancelled", "skipped")
_BASH_FLAGS = ("--noprofile", "--norc", "-e", "-o", "pipefail")


def _field(job: str, name: str, indent: int = 4) -> str:
    lines = job.splitlines()
    for index, line in enumerate(lines):
        match = re.fullmatch(rf" {{{indent}}}{re.escape(name)}:[ \t]*(.*)", line)
        if match is None:
            continue
        value = [match[1]]
        for following in lines[index + 1 :]:
            stripped = following.lstrip()
            if not stripped or stripped.startswith("#"):
                continue
            depth = len(following) - len(stripped)
            if depth < indent or (depth == indent and not stripped.startswith("- ")):
                break
            value.append(stripped)
        return "\n".join(value)
    raise AssertionError(f"tests-ok is missing {name}")


def _tokens(value: str, sequence: bool = False) -> list[str]:
    lexer = shlex.shlex(value, posix=True)
    lexer.whitespace_split = True
    if sequence:
        lexer.whitespace += ",[]"
    return list(lexer)


def _expression(value: str, require_wrapper: bool = False) -> str:
    value = " ".join(_tokens(value)).strip()
    wrapped = value.startswith("${{") and value.endswith("}}")
    if require_wrapper:
        assert wrapped, "the environment value must evaluate an Actions expression"
    if wrapped:
        value = value[3:-2].strip()
    return value


def _assert_dependencies(job: str) -> None:
    needs = [token for token in _tokens(_field(job, "needs"), sequence=True) if token != "-"]
    assert set(needs) == {"members", "pytest"}
    assert _expression(_field(job, "if")) == "always()"


def _unusable_bash(reason: str) -> NoReturn:
    # Skip only off CI: on the Linux runner a broken Bash must fail, or every
    # gate test would quietly skip and the required check would stay green.
    message = f"the workflow gate needs a working Bash ({reason})"
    if os.environ.get("CI"):
        pytest.fail(message)
    pytest.skip(message)


def _working_bash() -> str:
    executable = shutil.which("bash")
    if executable is None:
        _unusable_bash("not found")
    try:
        probe = subprocess.run(
            [executable, *_BASH_FLAGS, "-c", '[ "${BATCHES:-}" = "[]" ]'],
            env={**os.environ, "BATCHES": "[]"},
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        _unusable_bash(type(error).__name__)
    else:
        if probe.returncode != 0:
            _unusable_bash(f"probe exit {probe.returncode}")
    return executable


@pytest.fixture(scope="module")
def gate_job() -> str:
    # Read only this job's literal block; no YAML dependency is needed.
    match = re.search(r"(?ms)^  tests-ok:\n(.*?)(?=^  \S|\Z)", _WORKFLOW.read_text(encoding="utf-8"))
    assert match is not None, "tests-ok job is missing"
    return match[1]


@pytest.fixture(scope="module")
def bash() -> str:
    return _working_bash()


def test_gate_waits_for_both_jobs_and_runs_after_failure(gate_job: str) -> None:
    _assert_dependencies(gate_job)


def test_gate_reads_batches_from_discovery(gate_job: str) -> None:
    value = _field(gate_job, "BATCHES", indent=10)
    assert _expression(value, require_wrapper=True) == "needs.members.outputs.batches"


def _run_gate(
    gate_job: str, bash: str, members_result: str, pytest_result: str, batches: str | None = "[]"
) -> subprocess.CompletedProcess[str]:
    # The assert step's own `run: |` block, found by its name, so a step added
    # before it can never be the script under test.
    run = re.search(
        r"(?ms)^      - name: Assert member discovery and pytest matrix results\n.*?^        run: \|\n((?:          .*\n|\n)+)",
        gate_job,
    )
    assert run is not None, "tests-ok shell assertion is missing"
    script = dedent(run[1])
    for job, result in (("members", members_result), ("pytest", pytest_result)):
        script = script.replace("${{ needs." + job + ".result }}", result)
    assert "${{" not in script, "unresolved Actions expression in the gate"
    env = os.environ.copy()
    env.pop("BATCHES", None)
    if batches is not None:
        env["BATCHES"] = batches
    return subprocess.run(
        [bash, *_BASH_FLAGS, "-c", script],
        env=env,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )


def _assert_result(completed: subprocess.CompletedProcess[str], code: int, diagnostic: str) -> None:
    details = f"exit={completed.returncode}\n{completed.stdout}{completed.stderr}"
    assert completed.returncode == code, details
    assert diagnostic in completed.stdout, details


@pytest.mark.parametrize("members_result", _RESULTS)
@pytest.mark.parametrize("pytest_result", _RESULTS)
def test_gate_results(gate_job: str, bash: str, members_result: str, pytest_result: str) -> None:
    completed = _run_gate(gate_job, bash, members_result, pytest_result)
    if members_result != "success":
        _assert_result(completed, 1, f"workspace member discovery result: {members_result}")
    elif pytest_result not in ("success", "skipped"):
        _assert_result(completed, 1, f"pytest matrix result: {pytest_result}")
    else:
        _assert_result(completed, 0, f"pytest gate satisfied (matrix result: {pytest_result})")


@pytest.mark.parametrize(
    "batches",
    [None, "", "[ ]", '[{"name":"dev"}]', "not-json", "$(exit 23)", "`exit 24`"],
    ids=["missing", "empty", "noncanonical-empty", "nonempty", "malformed", "substitution", "backticks"],
)
def test_skipped_matrix_needs_a_confirmed_empty_selection(
    gate_job: str, bash: str, batches: str | None
) -> None:
    completed = _run_gate(gate_job, bash, "success", "skipped", batches)
    _assert_result(completed, 1, "pytest matrix skipped without an empty selection")


@pytest.mark.parametrize("members_result", ["failure", "cancelled", "skipped"])
def test_discovery_failure_is_reported_before_invalid_skip(
    gate_job: str, bash: str, members_result: str
) -> None:
    completed = _run_gate(gate_job, bash, members_result, "skipped", '[{"name":"dev"}]')
    _assert_result(completed, 1, f"workspace member discovery result: {members_result}")


def test_successful_matrix_accepts_a_nonempty_selection(gate_job: str, bash: str) -> None:
    completed = _run_gate(gate_job, bash, "success", "success", '[{"name":"dev"}]')
    _assert_result(completed, 0, "pytest gate satisfied (matrix result: success)")


@pytest.mark.parametrize(
    ("needs", "condition"),
    [
        ("[members, pytest]", "always()"),
        ("[members, pytest]  # comment", "always()"),
        ("['members', 'pytest']", "always()"),
        ('["members", "pytest"]', "always()"),
        ("\n      - members\n      - pytest", "always()"),
        ("\n      - 'members'\n      - 'pytest'  # comment", "${{ always() }}"),
        ("[members, pytest]", "${{ always() }}"),
        ("[members, pytest]", "'${{ always() }}'  # comment"),
    ],
)
def test_equivalent_dependency_declarations(needs: str, condition: str) -> None:
    _assert_dependencies(f"    needs: {needs}\n    if: {condition}\n")


@pytest.mark.parametrize(
    ("needs", "condition"),
    [
        ("[pytest]", "always()"),
        ("[members]", "always()"),
        ("[members, pytest]", "success()"),
        ("[members, pytest]", "al ways()"),
        ("[members, pytest, other]", "always()"),
    ],
)
def test_incorrect_dependency_declarations_are_rejected(needs: str, condition: str) -> None:
    with pytest.raises(AssertionError):
        _assert_dependencies(f"    needs: {needs}\n    if: {condition}\n")


@pytest.mark.parametrize("mode", ["missing", "launch-error", "timeout", "nonzero"])
def test_unusable_bash_is_skipped(monkeypatch: pytest.MonkeyPatch, mode: str) -> None:
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.setattr(shutil, "which", lambda name: None if mode == "missing" else "/probe/bash")

    def probe(*args, **kwargs):
        if mode == "launch-error":
            raise OSError("cannot launch Bash")
        if mode == "timeout":
            raise subprocess.TimeoutExpired("bash", 5)
        return subprocess.CompletedProcess(args[0], 1, "", "WSL launcher unavailable")

    monkeypatch.setattr(subprocess, "run", probe)
    with pytest.raises(pytest.skip.Exception, match="needs a working Bash"):
        _working_bash()


def test_bash_probe_skips_shell_without_gate_environment(bash: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.setattr(shutil, "which", lambda name: bash)
    run = subprocess.run

    def without_batches(*args, **kwargs):
        env = kwargs.get("env", os.environ).copy()
        env.pop("BATCHES", None)
        return run(*args, **{**kwargs, "env": env})

    monkeypatch.setattr(subprocess, "run", without_batches)
    with pytest.raises(pytest.skip.Exception, match="needs a working Bash"):
        _working_bash()


def test_unusable_bash_fails_on_ci(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CI", "true")
    monkeypatch.setattr(shutil, "which", lambda name: None)
    with pytest.raises(pytest.fail.Exception, match="needs a working Bash"):
        _working_bash()


def test_gate_step_runs_with_the_tested_shell_flags(gate_job: str) -> None:
    step = gate_job.split("- name: Assert member discovery and pytest matrix results", 1)[1]
    assert re.search(r"(?m)^        shell: bash\s*$", step), (
        "the gate step must set `shell: bash` to match _BASH_FLAGS"
    )
