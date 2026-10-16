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
    assert read_installed(str(bad)) is None


def test_an_empty_listing_is_unknown_not_an_empty_install(tmp_path: Path) -> None:
    """Inside a sandbox the plugin cache is read-denied and the listing
    comes back `[]`, indistinguishable from a genuinely plugin-free
    harness. Unknown is the safe reading: it proposes nothing."""
    empty = tmp_path / "empty.json"
    empty.write_text("[]")
    assert read_installed(str(empty)) is None


def test_a_real_listing_parses_to_a_name_version_map(tmp_path: Path) -> None:
    listing = tmp_path / "list.json"
    listing.write_text('[{"name": "magpie-setup", "version": "0.2.0"}]')
    assert read_installed(str(listing)) == {"magpie-setup": "0.2.0"}


def test_a_listing_that_is_not_a_list_is_unknown(tmp_path: Path) -> None:
    listing = tmp_path / "list.json"
    listing.write_text('{"plugins": []}')
    assert read_installed(str(listing)) is None


def test_a_missing_harness_cli_is_unknown(monkeypatch: pytest.MonkeyPatch) -> None:
    def explode(*_args: object, **_kwargs: object) -> None:
        raise FileNotFoundError("claude")

    monkeypatch.setattr("setup_preflight.cli.subprocess.run", explode)
    assert read_installed(None) is None


# --- read_installed: every harness answers with its own listing ----------------------


def test_a_missing_claude_binary_falls_through_to_codex(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A missing `claude` binary on another harness is not unknown: that
    harness answers with its own listing (issue #1641)."""
    seen: list[list[str]] = []

    def run(argv: list[str], **_kwargs: object) -> subprocess.CompletedProcess:
        seen.append(list(argv))
        if argv[0] == "claude":
            raise FileNotFoundError("claude")
        completed = subprocess.CompletedProcess[str](argv, 0)
        completed.stdout = '[{"name": "magpie-setup", "version": "0.3.1"}]'
        return completed

    monkeypatch.setattr("setup_preflight.cli.subprocess.run", run)
    assert read_installed(None) == {"magpie-setup": "0.3.1"}
    assert seen == [["claude", "plugin", "list", "--json"], ["codex", "plugin", "list"]]


def test_no_harness_cli_at_all_is_unknown(monkeypatch: pytest.MonkeyPatch) -> None:
    """A machine where none of the listing commands exist stays unknown."""

    def explode(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess:
        raise FileNotFoundError("no harness here")

    monkeypatch.setattr("setup_preflight.cli.subprocess.run", explode)
    assert read_installed(None) is None


def test_a_found_harness_that_fails_is_unknown_not_a_fallthrough(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The first binary that exists answers for the machine: a listing it
    cannot produce stays unknown rather than borrowing another harness's."""

    def run(argv: list[str], **_kwargs: object) -> subprocess.CompletedProcess:
        if argv[0] == "claude":
            raise FileNotFoundError("claude")
        completed = subprocess.CompletedProcess[str](argv, 1)
        completed.stdout = ""
        return completed

    monkeypatch.setattr("setup_preflight.cli.subprocess.run", run)
    assert read_installed(None) is None


def test_an_unparsable_listing_from_the_found_harness_is_unknown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A found harness whose listing is not the shared JSON shape reads as
    unknown — the checker proposes nothing it cannot read."""

    def run(argv: list[str], **_kwargs: object) -> subprocess.CompletedProcess:
        if argv[0] == "claude":
            raise FileNotFoundError("claude")
        completed = subprocess.CompletedProcess[str](argv, 0)
        completed.stdout = "magpie-setup 0.3.1 (marketplace)"
        return completed

    monkeypatch.setattr("setup_preflight.cli.subprocess.run", run)
    assert read_installed(None) is None


def test_a_present_claude_listing_is_not_second_guessed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A readable Claude Code listing ends the probe: later harnesses are
    never asked, so the established behaviour is unchanged."""
    seen: list[list[str]] = []

    def run(argv: list[str], **_kwargs: object) -> subprocess.CompletedProcess:
        seen.append(list(argv))
        completed = subprocess.CompletedProcess[str](argv, 0)
        completed.stdout = '[{"name": "magpie-setup", "version": "0.2.0"}]'
        return completed

    monkeypatch.setattr("setup_preflight.cli.subprocess.run", run)
    assert read_installed(None) == {"magpie-setup": "0.2.0"}
    assert seen == [["claude", "plugin", "list", "--json"]]
