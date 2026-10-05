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
"""Tests for ``checker.config`` — markdown parsing of privacy-llm.md."""

from __future__ import annotations

import pathlib
import textwrap

import pytest

from checker.config import (
    DEFAULT_CONFIG_FILENAME,
    host_of,
    locate_config_path,
    parse_config,
)


def _write(path: pathlib.Path, body: str) -> pathlib.Path:
    path.write_text(textwrap.dedent(body), encoding="utf-8")
    return path


# -- locate_config_path ---------------------------------------------------


def test_locate_explicit_wins(tmp_path: pathlib.Path, monkeypatch):
    monkeypatch.setenv("PRIVACY_LLM_CONFIG", "/should-not-be-used")
    explicit = tmp_path / "explicit.md"
    explicit.write_text("# stub")
    assert locate_config_path(str(explicit)) == explicit


def test_locate_env_used_when_no_explicit(tmp_path: pathlib.Path, monkeypatch):
    env_path = tmp_path / "from-env.md"
    monkeypatch.setenv("PRIVACY_LLM_CONFIG", str(env_path))
    assert locate_config_path(None) == env_path


def test_locate_default_personal_layer_first(tmp_path: pathlib.Path, monkeypatch):
    """The file `setup-privacy-llm` writes for an unadopted repo is the one read."""
    monkeypatch.delenv("PRIVACY_LLM_CONFIG", raising=False)
    monkeypatch.chdir(tmp_path)
    home = tmp_path / ".git" / "apache-magpie"
    home.mkdir(parents=True)
    (tmp_path / ".apache-magpie-overrides").mkdir()
    (tmp_path / ".apache-magpie-overrides" / DEFAULT_CONFIG_FILENAME).write_text("# project")
    cfg = home / DEFAULT_CONFIG_FILENAME
    cfg.write_text("# personal")
    assert locate_config_path(None) == cfg


def test_locate_default_adopted_repo_reads_in_tree_local(tmp_path: pathlib.Path, monkeypatch):
    monkeypatch.delenv("PRIVACY_LLM_CONFIG", raising=False)
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".apache-magpie.lock").write_text("method: local\n")
    local = tmp_path / ".apache-magpie-local"
    local.mkdir()
    cfg = local / DEFAULT_CONFIG_FILENAME
    cfg.write_text("# personal")
    assert locate_config_path(None) == cfg


def test_locate_default_reads_a_legacy_local_dir(tmp_path: pathlib.Path, monkeypatch):
    monkeypatch.delenv("PRIVACY_LLM_CONFIG", raising=False)
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".git").mkdir()
    local = tmp_path / ".apache-magpie-local"
    local.mkdir()
    cfg = local / DEFAULT_CONFIG_FILENAME
    cfg.write_text("# personal")
    assert locate_config_path(None) == cfg


def test_locate_default_falls_back_to_overrides(tmp_path: pathlib.Path, monkeypatch):
    monkeypatch.delenv("PRIVACY_LLM_CONFIG", raising=False)
    monkeypatch.chdir(tmp_path)
    cfg_dir = tmp_path / ".apache-magpie-overrides"
    cfg_dir.mkdir()
    cfg = cfg_dir / DEFAULT_CONFIG_FILENAME
    cfg.write_text("# stub")
    assert locate_config_path(None) == cfg


def test_locate_default_never_reads_the_framework_snapshot(tmp_path: pathlib.Path, monkeypatch):
    """`.apache-magpie/` is the replaceable framework snapshot, not config."""
    monkeypatch.delenv("PRIVACY_LLM_CONFIG", raising=False)
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".apache-magpie").mkdir()
    (tmp_path / ".apache-magpie" / DEFAULT_CONFIG_FILENAME).write_text("# stub")
    with pytest.raises(FileNotFoundError):
        locate_config_path(None)


def test_locate_raises_when_nothing_found(tmp_path: pathlib.Path, monkeypatch):
    monkeypatch.delenv("PRIVACY_LLM_CONFIG", raising=False)
    monkeypatch.chdir(tmp_path)
    with pytest.raises(FileNotFoundError, match="No privacy-llm config found"):
        locate_config_path(None)


# -- parse_config: LLM stack ---------------------------------------------


def test_parse_minimal_claude_only(tmp_path: pathlib.Path):
    cfg = _write(
        tmp_path / "p.md",
        """\
        # Privacy-LLM configuration

        ## Currently configured LLM stack

        - Claude Code (the agent running framework skills)

        ## Approved third-party endpoints (opt-in)

        (none — Claude Code is the only LLM)

        ## Private mailing lists for this project

        - `<private-list>`
        """,
    )
    parsed = parse_config(cfg)
    assert len(parsed.llm_stack) == 1
    assert parsed.llm_stack[0].url is None
    assert "Claude Code" in parsed.llm_stack[0].raw
    assert parsed.opt_in == []


def test_parse_extracts_first_url(tmp_path: pathlib.Path):
    cfg = _write(
        tmp_path / "p.md",
        """\
        ## Currently configured LLM stack

        - Claude Code
        - Local Ollama at http://127.0.0.1:11434/  (model: llama3.1:8b)

        ## Approved third-party endpoints (opt-in)

        (none)
        """,
    )
    parsed = parse_config(cfg)
    assert len(parsed.llm_stack) == 2
    assert parsed.llm_stack[1].url == "http://127.0.0.1:11434/"


def test_parse_skips_html_comments(tmp_path: pathlib.Path):
    cfg = _write(
        tmp_path / "p.md",
        """\
        ## Currently configured LLM stack

        <!-- this comment block lives mid-section
             - Sneaky imposter LLM at http://evil.example/  (model: foo)
             -->
        - Claude Code

        ## Approved third-party endpoints (opt-in)
        """,
    )
    parsed = parse_config(cfg)
    assert len(parsed.llm_stack) == 1
    assert "Claude Code" in parsed.llm_stack[0].raw


def test_parse_skips_placeholder_bullets(tmp_path: pathlib.Path):
    cfg = _write(
        tmp_path / "p.md",
        """\
        ## Currently configured LLM stack

        - Claude Code

        ## Approved third-party endpoints (opt-in)

        - (none — Claude Code is the only LLM)
        """,
    )
    parsed = parse_config(cfg)
    assert parsed.opt_in == []  # placeholder skipped


# -- parse_config: opt-in entries ---------------------------------------


def test_parse_opt_in_full_entry(tmp_path: pathlib.Path):
    cfg = _write(
        tmp_path / "p.md",
        """\
        ## Currently configured LLM stack

        - Claude Code
        - AWS Bedrock at https://bedrock-runtime.eu-central-1.amazonaws.com (model: foo)

        ## Approved third-party endpoints (opt-in)

        - AWS Bedrock — eu-central-1
          - Data-residency contract: AWS DPA + Bedrock no-training default
          - Approved-by: ABC 2026-04-01

        ## Private mailing lists for this project
        """,
    )
    parsed = parse_config(cfg)
    assert len(parsed.opt_in) == 1
    e = parsed.opt_in[0]
    assert e.name.startswith("AWS Bedrock")
    assert "AWS DPA" in (e.data_residency or "")
    assert e.approved_by == "ABC 2026-04-01"


def test_parse_opt_in_missing_approved_by(tmp_path: pathlib.Path):
    cfg = _write(
        tmp_path / "p.md",
        """\
        ## Currently configured LLM stack

        - Direct Anthropic API at https://api.anthropic.com/v1/

        ## Approved third-party endpoints (opt-in)

        - Anthropic API direct
          - Data-residency contract: ZDR agreement applied to API key xxx
        """,
    )
    parsed = parse_config(cfg)
    assert len(parsed.opt_in) == 1
    assert parsed.opt_in[0].approved_by is None


def test_parse_two_opt_in_entries(tmp_path: pathlib.Path):
    cfg = _write(
        tmp_path / "p.md",
        """\
        ## Currently configured LLM stack
        - Claude Code

        ## Approved third-party endpoints (opt-in)

        - First Provider — region-foo
          - Data-residency contract: contract A
          - Approved-by: ABC 2026-04-01

        - Second Provider — region-bar
          - Data-residency contract: contract B
          - Approved-by: XYZ 2026-04-02
        """,
    )
    parsed = parse_config(cfg)
    assert len(parsed.opt_in) == 2
    assert parsed.opt_in[0].approved_by == "ABC 2026-04-01"
    assert parsed.opt_in[1].approved_by == "XYZ 2026-04-02"


# -- host_of ----------------------------------------------------------


def test_host_of_basic():
    assert host_of("http://127.0.0.1:11434/") == "127.0.0.1"


def test_host_of_apache_org():
    assert host_of("https://inference.apache.org/v1/") == "inference.apache.org"


def test_host_of_returns_none_for_garbage():
    assert host_of("not a url") is None
