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
"""The `@`-mention allowlist every renderer honours."""

from __future__ import annotations

import argparse
from pathlib import Path

from pr_management import config, mentions
from pr_management.code_review import body as review_body
from pr_management.triage.render import enforce


def _cfg(tmp_path: Path, cell: str) -> config.Config:
    d = tmp_path / "cfg"
    d.mkdir(exist_ok=True)
    (d / "pr-management-config.md").write_text(
        f"| Key | Value | Notes |\n|---|---|---|\n| `mention_allowlist` | {cell} | x |\n"
    )
    return config.load(tmp_path, d)


def test_the_config_key_is_read(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path, "`@release-bot` `@acme/docs-team`")
    assert mentions.allowed(cfg) == {"release-bot", "acme/docs-team"}


def test_an_unset_key_allows_nothing(tmp_path: Path) -> None:
    assert mentions.allowed(_cfg(tmp_path, "*(empty)*")) == frozenset()


def test_the_flag_adds_to_the_config(tmp_path: Path) -> None:
    parser = argparse.ArgumentParser()
    mentions.add_flag(parser)
    args = parser.parse_args(["--allow-mention", "@Kaxil", "--allow-mention", "potiuk"])
    cfg = mentions.apply_flag(_cfg(tmp_path, "`@release-bot`"), args)
    assert mentions.allowed(cfg) == {"release-bot", "kaxil", "potiuk"}


def test_triage_and_stale_sweep_keep_allowed_handles_live() -> None:
    text, mentioned = enforce("@alice — cc @release-bot and @bob", "alice", None, frozenset({"release-bot"}))
    assert text == "@alice — cc @release-bot and `@bob`"
    assert mentioned == ["alice", "release-bot"]


def test_without_an_allowlist_only_the_author_stays_live() -> None:
    text, _ = enforce("@alice — cc @release-bot", "alice", None)
    assert text == "@alice — cc `@release-bot`"


def test_code_review_keeps_allowed_handles_live() -> None:
    allowed = frozenset({"acme/docs-team"})
    assert (
        review_body.escape_handles("cc @acme/docs-team and @bob", allowed) == "cc @acme/docs-team and `@bob`"
    )
    assert [h["handle"] for h in review_body.mention_scan("cc @acme/docs-team and @bob", allowed)] == ["bob"]
