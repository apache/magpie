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
from __future__ import annotations

from pathlib import Path

from pr_management.mentor import config, render

from .conftest import FOOTER


def test_an_intervention_renders_with_the_pointer_and_footer(tmp_path: Path, config_dir: Path) -> None:
    cfg = config.load(tmp_path, config_dir)
    out = tmp_path / "draft.md"
    r = render.render(cfg, kind="missing-repro", author="alice", pointer="Missing repro", out=out)
    body = out.read_text()
    assert r["ok"] and body.startswith("@alice — to take a look")
    assert "[Filing a reproducible report](https://example.org/repro)" in body
    assert body.rstrip().endswith(FOOTER)
    assert r["mentions"] == ["@alice"]


def test_an_unknown_pointer_is_refused(tmp_path: Path, config_dir: Path) -> None:
    cfg = config.load(tmp_path, config_dir)
    r = render.render(cfg, kind="missing-repro", author="alice", pointer="Nope", out=tmp_path / "d.md")
    assert not r["ok"] and not (tmp_path / "d.md").exists()


def test_a_hostile_author_is_refused(tmp_path: Path, config_dir: Path) -> None:
    cfg = config.load(tmp_path, config_dir)
    r = render.render(
        cfg, kind="missing-version", author="a b; rm", pointer="Missing repro", out=tmp_path / "d.md"
    )
    assert not r["ok"]


def test_the_hand_off_tags_the_team_and_silences_other_mentions(tmp_path: Path, config_dir: Path) -> None:
    cfg = config.load(tmp_path, config_dir)
    out = tmp_path / "h.md"
    r = render.render(
        cfg,
        kind="hand-off",
        author=None,
        open_question="does @someone own #42?",
        upstream="acme/product",
        out=out,
    )
    body = out.read_text()
    assert r["ok"] and body.startswith("@acme/committers — handing this off: does `@someone` own")
    assert "[#42](https://github.com/acme/product/issues/42)" in body
    assert r["mentions"] == ["@acme/committers"]


def test_the_hand_off_needs_an_open_question(tmp_path: Path, config_dir: Path) -> None:
    cfg = config.load(tmp_path, config_dir)
    assert not render.render(cfg, kind="hand-off", author=None, open_question=" ", out=tmp_path / "h.md")[
        "ok"
    ]
