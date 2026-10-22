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

"""The contract the shared pre-flight block depends on: one JSON verdict,
exit 0 whenever a verdict was reached, non-zero only when it could not be."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from setup_preflight.cli import main, read_installed

from .conftest import write_lock

MARKETPLACE = """\
method:       marketplace
url:          apache/magpie
min_version:  0.2.0

plugins:
  - magpie-setup
"""


@pytest.fixture(autouse=True)
def clean_harness_markers(monkeypatch: pytest.MonkeyPatch) -> None:
    # A developer's surrounding Codex session must not override the
    # harness a test explicitly selects.
    for marker in ("CODEX_SANDBOX", "CODEX_THREAD_ID", "COPILOT_CLI", "GEMINI_CLI", "CLAUDECODE"):
        monkeypatch.delenv(marker, raising=False)


def run(capsys: pytest.CaptureFixture[str], *args: str) -> tuple[int, dict]:
    code = main(list(args))
    out = capsys.readouterr().out
    return code, (json.loads(out) if out.strip() else {})


def test_a_clean_project_answers_ok_and_exits_zero(project: Path, capsys) -> None:
    code, payload = run(capsys, "--skill", "magpie-x", "--project-root", str(project))
    assert code == 0
    assert payload == {"verdict": "ok"}


def test_findings_are_an_answer_not_an_error(project: Path, capsys) -> None:
    """Exit 0 with findings. A non-zero exit means the check could not run,
    and the block falls back to the detail file rather than assuming the
    project is fine — so a finding must never look like a failure."""
    write_lock(project, MARKETPLACE)
    listing = project / "plugins.json"
    listing.write_text('[{"name": "other", "version": "1.0.0"}]')
    code, payload = run(
        capsys,
        "--skill",
        "magpie-x",
        "--hash",
        "sha256:abc",
        "--project-root",
        str(project),
        "--plugin-list",
        str(listing),
        "--verify-interval-days",
        "0",
    )
    assert code == 0
    assert payload["verdict"] == "action"
    assert [f["code"] for f in payload["findings"]] == ["below-floor", "sweep-never-run"]
    assert {f["scope"] for f in payload["findings"]} == {"project", "skill"}


def test_a_malformed_lock_exits_non_zero_rather_than_claiming_ok(project: Path, capsys) -> None:
    write_lock(project, "method: marketplace\ngibberish\n")
    code, payload = run(capsys, "--skill", "magpie-x", "--project-root", str(project))
    assert code == 2
    assert payload == {}


def test_every_section_named_is_one_a_reader_can_find(project: Path, capsys) -> None:
    """A finding's `section` is the contract with `preflight-detail.md`."""
    write_lock(project, MARKETPLACE)
    listing = project / "plugins.json"
    listing.write_text("[]")
    _, payload = run(
        capsys,
        "--skill",
        "magpie-x",
        "--project-root",
        str(project),
        "--plugin-list",
        str(listing),
    )
    for finding in payload.get("findings", []):
        assert finding["section"].startswith("step-")


# --- read_installed: the unknown/absent distinction ---------------------------------


def test_unparsable_output_is_unknown(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("not json at all")
    assert read_installed(str(bad)) == (None, None)


def test_an_empty_listing_is_unknown_not_an_empty_install(tmp_path: Path) -> None:
    """Inside a sandbox the plugin cache is read-denied and the listing
    comes back `[]`, indistinguishable from a genuinely plugin-free
    harness. Unknown is the safe reading: it proposes nothing."""
    empty = tmp_path / "empty.json"
    empty.write_text("[]")
    assert read_installed(str(empty)) == (None, None)


def test_a_real_listing_parses_to_a_name_version_map(tmp_path: Path) -> None:
    listing = tmp_path / "list.json"
    listing.write_text('[{"name": "magpie-setup", "version": "0.2.0"}]')
    assert read_installed(str(listing)) == (None, {"magpie-setup": "0.2.0"})


def test_a_listing_that_is_not_a_list_is_unknown(tmp_path: Path) -> None:
    listing = tmp_path / "list.json"
    listing.write_text('{"plugins": []}')
    assert read_installed(str(listing)) == (None, None)


# --- read_installed: the running harness answers with its own listing ----------------


def _listing_ok(argv: list[str], body: str) -> subprocess.CompletedProcess:
    completed = subprocess.CompletedProcess[str](argv, 0)
    completed.stdout = body
    return completed


def test_the_claude_marker_runs_only_claudes_listing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The harness running this session is detected from its own marker,
    and only its listing command runs."""
    seen: list[list[str]] = []

    def run(argv: list[str], **_kwargs: object) -> subprocess.CompletedProcess:
        seen.append(list(argv))
        return _listing_ok(argv, '[{"name": "magpie-setup", "version": "0.2.0"}]')

    monkeypatch.setattr("setup_preflight.cli.subprocess.run", run)
    assert read_installed(None, {"CLAUDECODE": "1"}) == ("claude", {"magpie-setup": "0.2.0"})
    assert seen == [["claude", "plugin", "list", "--json"]]


def test_the_codex_marker_runs_codex_listing_with_its_json_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`codex plugin list` prints a terminal summary by default; only
    `--json` makes it emit the array the shared parser reads."""
    seen: list[list[str]] = []

    def run(argv: list[str], **_kwargs: object) -> subprocess.CompletedProcess:
        seen.append(list(argv))
        return _listing_ok(argv, '[{"name": "magpie-setup", "version": "0.3.1"}]')

    monkeypatch.setattr("setup_preflight.cli.subprocess.run", run)
    assert read_installed(None, {"CODEX_SANDBOX": "1"}) == ("codex", {"magpie-setup": "0.3.1"})
    assert seen == [["codex", "plugin", "list", "--json"]]


def test_the_gemini_marker_runs_gemini_listing_with_json_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`gemini extensions list` prints plain text by default; only
    `-o json` makes it emit the array the shared parser reads."""
    seen: list[list[str]] = []

    def run(argv: list[str], **_kwargs: object) -> subprocess.CompletedProcess:
        seen.append(list(argv))
        return _listing_ok(argv, '[{"name": "magpie", "version": "0.2.0"}]')

    monkeypatch.setattr("setup_preflight.cli.subprocess.run", run)
    assert read_installed(None, {"GEMINI_CLI": "1"}) == ("gemini", {"magpie": "0.2.0"})
    assert seen == [["gemini", "extensions", "list", "-o", "json"]]


def test_the_innermost_marker_wins_when_two_harnesses_inherit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A harness started from inside another inherits the outer one's
    variables; the innermost candidate answers, and `CLAUDECODE` — which
    every child inherits — is checked last."""
    seen: list[list[str]] = []

    def run(argv: list[str], **_kwargs: object) -> subprocess.CompletedProcess:
        seen.append(list(argv))
        return _listing_ok(argv, '[{"name": "magpie", "version": "0.2.0"}]')

    monkeypatch.setattr("setup_preflight.cli.subprocess.run", run)
    harness, _ = read_installed(None, {"CLAUDECODE": "1", "GEMINI_CLI": "1"})
    assert harness == "gemini"
    assert seen == [["gemini", "extensions", "list", "-o", "json"]]


def test_no_marker_is_unknown_and_no_listing_runs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A session under no detected harness stays unknown: nothing is
    probed in a fixed order, so no harness can answer for another."""

    def explode(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess:
        raise AssertionError("no listing may run without a detected harness")

    monkeypatch.setattr("setup_preflight.cli.subprocess.run", explode)
    assert read_installed(None, {}) == (None, None)


def test_the_copilot_marker_is_unknown_without_a_listing_cli(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Copilot installs from a repo URL and has no listing CLI: the floor
    stays unknown rather than guessing what a listing would print."""

    def explode(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess:
        raise AssertionError("copilot has no listing command to run")

    monkeypatch.setattr("setup_preflight.cli.subprocess.run", explode)
    assert read_installed(None, {"COPILOT_CLI": "1"}) == (None, None)


def test_a_timeout_of_the_running_harness_is_unknown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A `claude` that exists and times out must not borrow another
    harness's listing: unknown, and no other harness is ever probed."""

    def explode(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess:
        raise subprocess.TimeoutExpired(cmd=["claude"], timeout=20)

    monkeypatch.setattr("setup_preflight.cli.subprocess.run", explode)
    assert read_installed(None, {"CLAUDECODE": "1"}) == (None, None)


def test_a_refused_binary_of_the_running_harness_is_unknown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A sandbox that refuses to execute the harness's own binary reads as
    unknown, not as a missing binary to probe around."""

    def explode(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess:
        raise PermissionError("sandbox denies execution")

    monkeypatch.setattr("setup_preflight.cli.subprocess.run", explode)
    assert read_installed(None, {"CLAUDECODE": "1"}) == (None, None)


def test_a_missing_binary_of_the_running_harness_is_unknown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The marker says Claude Code but `claude` is not on PATH: unknown —
    the checker never asks a different harness to answer for it."""

    def explode(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess:
        raise FileNotFoundError("claude")

    monkeypatch.setattr("setup_preflight.cli.subprocess.run", explode)
    assert read_installed(None, {"CLAUDECODE": "1"}) == (None, None)


def test_a_failed_listing_of_the_running_harness_is_unknown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A detected harness whose listing exits non-zero stays unknown."""

    def run(argv: list[str], **_kwargs: object) -> subprocess.CompletedProcess:
        completed = subprocess.CompletedProcess[str](argv, 1)
        completed.stdout = ""
        return completed

    monkeypatch.setattr("setup_preflight.cli.subprocess.run", run)
    assert read_installed(None, {"CLAUDECODE": "1"}) == (None, None)


def test_an_unparsable_listing_of_the_running_harness_is_unknown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A detected harness whose listing is not the shared JSON shape reads
    as unknown — the checker proposes nothing it cannot read."""

    def run(argv: list[str], **_kwargs: object) -> subprocess.CompletedProcess:
        return _listing_ok(argv, "magpie-setup 0.3.1 (marketplace)")

    monkeypatch.setattr("setup_preflight.cli.subprocess.run", run)
    assert read_installed(None, {"CLAUDECODE": "1"}) == (None, None)


def test_the_finding_names_the_running_harness(
    project: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The `below-floor` finding carries the harness its listing came
    from, so the rules can name that harness's own commands."""
    write_lock(project, MARKETPLACE)
    monkeypatch.setenv("CLAUDECODE", "1")
    monkeypatch.setattr(
        "setup_preflight.cli.subprocess.run",
        lambda argv, **_kwargs: _listing_ok(argv, '[{"name": "magpie-setup", "version": "0.1.0"}]'),
    )
    code, payload = run(
        capsys,
        "--skill",
        "magpie-x",
        "--project-root",
        str(project),
        "--verify-interval-days",
        "0",
    )
    assert code == 0
    finding = next(f for f in payload["findings"] if f["code"] == "below-floor")
    assert finding["facts"]["harness"] == "claude"


def test_a_supplied_listing_reports_no_harness(project: Path, capsys) -> None:
    """`--plugin-list` is what the caller already read; the map stands
    alone and the finding names no harness."""
    write_lock(project, MARKETPLACE)
    listing = project / "plugins.json"
    listing.write_text('[{"name": "other", "version": "1.0.0"}]')
    _, payload = run(
        capsys,
        "--skill",
        "magpie-x",
        "--project-root",
        str(project),
        "--plugin-list",
        str(listing),
    )
    finding = next(f for f in payload["findings"] if f["code"] == "below-floor")
    assert finding["facts"]["harness"] is None


@pytest.mark.parametrize("version", ["0.2.0", "0.3.0", "0.10.0"])
def test_gemini_extension_at_or_above_floor_does_not_block(
    project: Path, capsys, monkeypatch, version
) -> None:
    write_lock(project, MARKETPLACE + "  - magpie-agent-guard\n")
    monkeypatch.setenv("GEMINI_CLI", "1")
    monkeypatch.setattr(
        "setup_preflight.cli.subprocess.run",
        lambda argv, **kwargs: _listing_ok(argv, json.dumps([{"name": "magpie", "version": version}])),
    )
    code, payload = run(capsys, "--skill", "magpie-x", "--project-root", str(project), "--no-cache")
    assert code == 0
    assert not any(f["code"] == "below-floor" for f in payload.get("findings", []))


def test_gemini_extension_below_floor_is_outdated_for_every_family(
    project: Path, capsys, monkeypatch
) -> None:
    write_lock(project, MARKETPLACE + "  - magpie-agent-guard\n")
    monkeypatch.setenv("GEMINI_CLI", "1")
    monkeypatch.setattr(
        "setup_preflight.cli.subprocess.run",
        lambda argv, **kwargs: _listing_ok(argv, '[{"name":"magpie","version":"0.1.0"}]'),
    )
    _, payload = run(capsys, "--skill", "magpie-x", "--project-root", str(project), "--no-cache")
    facts = next(f["facts"] for f in payload["findings"] if f["code"] == "below-floor")
    assert facts["missing"] == []
    assert facts["outdated"] == [
        {"plugin": name, "installed": "0.1.0", "floor": "0.2.0"}
        for name in ("magpie-setup", "magpie-agent-guard", "magpie-vetted-ops")
    ]


def test_a_supplied_gemini_listing_keeps_the_single_extension_rule(
    project: Path, capsys, monkeypatch
) -> None:
    write_lock(project, MARKETPLACE + "  - magpie-agent-guard\n")
    monkeypatch.setenv("GEMINI_CLI", "1")
    listing = project / "plugins.json"
    listing.write_text('[{"name": "magpie", "version": "0.3.0"}]')
    code, payload = run(
        capsys, "--skill", "magpie-x", "--project-root", str(project), "--plugin-list", str(listing)
    )
    assert code == 0
    assert not any(f["code"] == "below-floor" for f in payload.get("findings", []))


def test_a_supplied_codex_envelope_is_unwrapped(monkeypatch, tmp_path: Path) -> None:
    listing = tmp_path / "codex.json"
    listing.write_text(
        (Path(__file__).parent / "fixtures" / "codex-0.149.1-list.json").read_text(encoding="utf-8")
    )
    assert read_installed(str(listing), {"CODEX_THREAD_ID": "test"}) == (
        "codex",
        {"documents": "26.1015.12040"},
    )


def test_codex_live_listing_reads_only_installed_entries(monkeypatch) -> None:
    text = (Path(__file__).parent / "fixtures" / "codex-0.149.1-list.json").read_text(encoding="utf-8")
    listing = json.loads(text)
    listing["available"] = [{"name": "magpie-setup", "version": "0.1.0"}]
    text = json.dumps(listing)
    monkeypatch.setattr("setup_preflight.cli.subprocess.run", lambda argv, **kwargs: _listing_ok(argv, text))
    assert read_installed(None, {"CODEX_THREAD_ID": "test"}) == ("codex", {"documents": "26.1015.12040"})


def test_codex_envelope_reports_a_below_floor_install(project: Path, capsys, monkeypatch) -> None:
    write_lock(project, MARKETPLACE)
    monkeypatch.setenv("CODEX_THREAD_ID", "test")
    monkeypatch.setattr(
        "setup_preflight.cli.subprocess.run",
        lambda argv, **kwargs: _listing_ok(
            argv, '{"installed":[{"name":"magpie-setup","version":"0.1.0"}],"available":[]}'
        ),
    )
    _, payload = run(capsys, "--skill", "magpie-x", "--project-root", str(project), "--no-cache")
    facts = next(f["facts"] for f in payload["findings"] if f["code"] == "below-floor")
    assert facts["harness"] == "codex"
    assert facts["missing"] == ["magpie-vetted-ops"]
    assert facts["outdated"] == [{"plugin": "magpie-setup", "installed": "0.1.0", "floor": "0.2.0"}]


@pytest.mark.parametrize(
    "text",
    [
        '[{"id":"magpie-setup","version":"0.1.0"}]',
        '[{"name":"magpie-setup","version":"0.1.0"},{"plugin":"magpie-agent-guard","version":"0.1.0"}]',
        '{"installed":[],"available":[{"name":"magpie-setup","version":"0.1.0"}]}',
        '{"available":[{"name":"magpie-setup","version":"0.1.0"}]}',
    ],
)
def test_unrecognised_or_empty_codex_listing_is_unknown(monkeypatch, text) -> None:
    monkeypatch.setattr("setup_preflight.cli.subprocess.run", lambda argv, **kwargs: _listing_ok(argv, text))
    assert read_installed(None, {"CODEX_THREAD_ID": "test"}) == (None, None)
