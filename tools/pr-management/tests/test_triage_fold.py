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
"""Splicing the fold block into a PR body."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pr_management import cli
from pr_management.triage import fold as F

BLOCK = "<!-- pr-triage-fold: triaged=2026-10-01T12:00:00Z head=abc1234 action=draft by=t -->\n\nnote\n\n<!-- /pr-triage-fold -->\n"
OTHER = "<!-- pr-triage-fold: triaged=2026-09-01T12:00:00Z head=0000000 action=comment by=t -->\nold\n<!-- /pr-triage-fold -->"


def test_append_to_a_body_without_a_block() -> None:
    new, replaced = F.splice("Author text.\n", BLOCK)
    assert new == "Author text.\n\n" + BLOCK
    assert not replaced


def test_applying_twice_is_byte_identical() -> None:
    once, _ = F.splice("Author text.\n", BLOCK)
    twice, replaced = F.splice(once, BLOCK)
    assert twice == once and replaced
    assert twice.count("<!-- pr-triage-fold:") == 1


def test_replaces_an_older_block_and_keeps_text_around_it() -> None:
    body = f"Intro.\n\n{OTHER}\n\nAuthor footer."
    new, replaced = F.splice(body, BLOCK)
    assert replaced
    assert "\nold\n" not in new
    assert new.startswith("Intro.\n\nAuthor footer.\n\n")
    assert new.count("pr-triage-fold:") == 1


def test_several_stale_blocks_all_go() -> None:
    new, _ = F.splice(f"a\n{OTHER}\nb\n{OTHER}\n", BLOCK)
    assert new.count("pr-triage-fold:") == 1


def test_an_unclosed_block_is_dropped() -> None:
    new, replaced = F.splice("a\n\n<!-- pr-triage-fold: triaged=x head=y -->\nhalf", BLOCK)
    assert replaced and new == "a\n\n" + BLOCK


def test_empty_body() -> None:
    assert F.splice("", BLOCK)[0] == BLOCK


def test_crlf_bodies_are_normalised() -> None:
    once, _ = F.splice("Author\r\ntext\r\n", BLOCK)
    assert "\r" not in once


def test_reads_the_saved_pr_view_json(tmp_path: Path) -> None:
    saved = tmp_path / "pr.json"
    saved.write_text(json.dumps({"number": 1, "body": "From JSON.", "title": "t"}))
    assert F.read_body(saved) == "From JSON."


def test_cli_fold(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    cur = tmp_path / "cur.md"
    cur.write_text(f"Body.\n\n{OTHER}\n")
    blk = tmp_path / "blk.md"
    blk.write_text(BLOCK)
    out = tmp_path / "new.md"
    assert (
        cli.main(["triage", "fold", "--current-body", str(cur), "--block", str(blk), "--out", str(out)]) == 0
    )
    report = json.loads(capsys.readouterr().out)
    assert report == {"out": str(out), "replaced": True, "bytes": len(out.read_bytes())}
    assert out.read_text() == "Body.\n\n" + BLOCK
