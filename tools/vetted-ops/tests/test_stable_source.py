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
"""`vetted-op-read source`: what the stable path the dispatchers start from is, per install method."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from vetted_ops import cli


def _stable(home: Path) -> Path:
    path = home / ".claude" / "magpie" / "vetted-ops"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def test_a_marketplace_link_is_the_plugin(tmp_path: Path) -> None:
    target = (
        tmp_path / ".claude" / "plugins" / "cache" / "apache-magpie" / "magpie-vetted-ops" / "1.0" / "tools"
    )
    target.mkdir(parents=True)
    _stable(tmp_path).symlink_to(target)
    assert cli.stable_source(tmp_path)["kind"] == "plugin"


def test_a_real_directory_is_a_snapshot_copy(tmp_path: Path) -> None:
    _stable(tmp_path).mkdir()
    assert cli.stable_source(tmp_path)["kind"] == "copy"


def test_a_link_elsewhere_is_a_checkout(tmp_path: Path) -> None:
    checkout = tmp_path / "code" / "magpie" / "tools" / "vetted-ops"
    checkout.mkdir(parents=True)
    _stable(tmp_path).symlink_to(checkout)
    status = cli.stable_source(tmp_path)
    assert status["kind"] == "checkout"
    assert status["resolves_to"] == str(checkout.resolve())


def test_nothing_there_is_missing(tmp_path: Path) -> None:
    assert cli.stable_source(tmp_path) == {
        "stable": "~/.claude/magpie/vetted-ops",
        "kind": "missing",
        "resolves_to": None,
    }


def test_the_subcommand_prints_one_json_object(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    _stable(tmp_path).mkdir()
    assert cli.main_read(["source"]) == cli.EXIT_OK
    assert json.loads(capsys.readouterr().out)["kind"] == "copy"


def test_the_subcommand_takes_no_parameters() -> None:
    assert cli.main_read(["source", "x"]) == cli.EXIT_USAGE
