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
"""Tests for ``checker.check`` — gate-check verdict logic + CLI."""

from __future__ import annotations

import io
import pathlib
import textwrap

from checker import check
from checker.config import LLMEntry, OptInEntry, ParsedConfig, parse_config


def _write(path: pathlib.Path, body: str) -> pathlib.Path:
    path.write_text(textwrap.dedent(body))
    return path


def _cfg(stack: list[LLMEntry], opt_in: list[OptInEntry] | None = None) -> ParsedConfig:
    return ParsedConfig(path=pathlib.Path("/dev/null"), llm_stack=stack, opt_in=opt_in or [])


def _run(monkeypatch, argv: list[str]) -> tuple[int, str, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    monkeypatch.setattr("sys.stdout", stdout)
    monkeypatch.setattr("sys.stderr", stderr)
    rc = check.main(argv)
    return rc, stdout.getvalue(), stderr.getvalue()


# -- default-approval rules --------------------------------------------


def test_claude_code_is_approved_by_default():
    [v] = check.check_stack(_cfg([LLMEntry(raw="Claude Code (the agent running …)", url=None)]))
    assert v.approved is True
    assert "Claude Code" in v.reason


def test_claude_code_match_is_case_insensitive():
    [v] = check.check_stack(_cfg([LLMEntry(raw="claude CODE itself", url=None)]))
    assert v.approved is True


def test_localhost_is_approved():
    for host in ("http://127.0.0.1:11434/", "http://localhost:8000/v1/", "http://[::1]:8080/"):
        [v] = check.check_stack(_cfg([LLMEntry(raw=f"Local at {host}", url=host)]))
        assert v.approved is True, f"expected {host} to be approved, got {v.reason}"


def test_apache_org_is_approved():
    [v] = check.check_stack(
        _cfg(
            [
                LLMEntry(
                    raw="ASF inference at https://inference.apache.org/v1/",
                    url="https://inference.apache.org/v1/",
                )
            ]
        )
    )
    assert v.approved is True
    # Match the verdict's exact phrasing rather than a bare "apache.org"
    # substring — the latter trips CodeQL's incomplete-URL-sanitization
    # rule (false positive here; v.reason is a human message, not a URL
    # being validated). Asserting on the production-code phrasing also
    # locks down the user-facing reason text against accidental drift.
    assert "*.apache.org-hosted" in v.reason


def test_subdomain_apache_org_is_approved():
    [v] = check.check_stack(
        _cfg(
            [
                LLMEntry(
                    raw="ASF infra at https://llm.airflow.apache.org/", url="https://llm.airflow.apache.org/"
                )
            ]
        )
    )
    assert v.approved is True


def test_llmao_gateway_is_carved_out_of_apache_org_approval():
    """``llm.apache.org`` matches the apache.org rule but must NOT be approved.

    The LLMAO pilot serves self-hosted models from rented third-party GPU
    hardware and its operators state pilot traffic is visible to llmao
    admins, so it fails the infra-governance assumption the blanket
    apache.org approval rests on.
    """
    [v] = check.check_stack(
        _cfg(
            [
                LLMEntry(
                    raw="ASF LLMAO gateway at https://llm.apache.org/",
                    url="https://llm.apache.org/",
                )
            ]
        )
    )
    assert v.approved is False
    assert "carved out" in v.reason


def test_llmao_carve_out_does_not_affect_other_apache_hosts():
    """The carve-out is by exact host, not a prefix or suffix match."""
    for url in ("https://llm.airflow.apache.org/", "https://inference.apache.org/v1/"):
        [v] = check.check_stack(_cfg([LLMEntry(raw=f"ASF at {url}", url=url)]))
        assert v.approved is True, f"expected {url} to stay approved, got {v.reason}"


def test_apache_org_lookalike_is_not_approved():
    """``apache.org-attacker.example.com`` must NOT match the apache.org rule."""
    [v] = check.check_stack(
        _cfg(
            [
                LLMEntry(
                    raw="Imposter at https://apache.org.evil.example/", url="https://apache.org.evil.example/"
                )
            ]
        )
    )
    assert v.approved is False


# -- opt-in matching --------------------------------------------------


def test_opt_in_full_entry_approves_match():
    stack = [LLMEntry(raw="AWS Bedrock at https://bedrock.eu.example/", url="https://bedrock.eu.example/")]
    opt_in = [
        OptInEntry(
            name="AWS Bedrock — eu-central-1",
            data_residency="AWS DPA + Bedrock no-training",
            approved_by="ABC 2026-04-01",
        )
    ]
    [v] = check.check_stack(_cfg(stack, opt_in))
    assert v.approved is True
    assert "AWS Bedrock" in v.reason


def test_opt_in_missing_data_residency_rejects():
    stack = [
        LLMEntry(
            raw="Anthropic API direct at https://api.anthropic.com/v1/", url="https://api.anthropic.com/v1/"
        )
    ]
    opt_in = [OptInEntry(name="Anthropic API direct", data_residency=None, approved_by="ABC 2026-04-01")]
    [v] = check.check_stack(_cfg(stack, opt_in))
    assert v.approved is False
    assert "Data-residency" in v.reason


def test_opt_in_missing_approved_by_rejects():
    stack = [
        LLMEntry(
            raw="Anthropic API direct at https://api.anthropic.com/v1/", url="https://api.anthropic.com/v1/"
        )
    ]
    opt_in = [OptInEntry(name="Anthropic API direct", data_residency="ZDR + no-training", approved_by=None)]
    [v] = check.check_stack(_cfg(stack, opt_in))
    assert v.approved is False
    assert "Approved-by" in v.reason


def test_opt_in_placeholder_approved_by_rejects():
    stack = [
        LLMEntry(
            raw="Anthropic API direct at https://api.anthropic.com/v1/", url="https://api.anthropic.com/v1/"
        )
    ]
    opt_in = [
        OptInEntry(
            name="Anthropic API direct",
            data_residency="ZDR + no-training",
            approved_by="<PMC-member-initials> <YYYY-MM-DD>",
        )
    ]
    [v] = check.check_stack(_cfg(stack, opt_in))
    assert v.approved is False
    assert "placeholder" in v.reason.lower()


def test_no_default_approval_no_opt_in_rejects():
    stack = [LLMEntry(raw="Some random LLM at https://random.example/", url="https://random.example/")]
    [v] = check.check_stack(_cfg(stack))
    assert v.approved is False
    assert "no default-approval rule matches" in v.reason


# -- CLI exit codes ---------------------------------------------------


def test_cli_exit_0_on_all_approved(tmp_path: pathlib.Path, monkeypatch):
    cfg = _write(
        tmp_path / "p.md",
        """\
        ## Currently configured LLM stack

        - Claude Code

        ## Approved third-party endpoints (opt-in)
        """,
    )
    rc, out, err = _run(monkeypatch, ["--config", str(cfg)])
    assert rc == 0
    assert "approved" in out.lower()


def test_cli_exit_0_quiet_emits_no_stdout(tmp_path: pathlib.Path, monkeypatch):
    cfg = _write(
        tmp_path / "p.md",
        """\
        ## Currently configured LLM stack
        - Claude Code

        ## Approved third-party endpoints (opt-in)
        """,
    )
    rc, out, err = _run(monkeypatch, ["--config", str(cfg), "--quiet"])
    assert rc == 0
    assert out == ""


def test_cli_exit_1_on_unapproved_entry(tmp_path: pathlib.Path, monkeypatch):
    cfg = _write(
        tmp_path / "p.md",
        """\
        ## Currently configured LLM stack

        - Claude Code
        - Some random LLM at https://random.example/

        ## Approved third-party endpoints (opt-in)
        """,
    )
    rc, out, err = _run(monkeypatch, ["--config", str(cfg)])
    assert rc == 1
    assert "not approved" in err.lower()
    assert "random.example" in err


def test_cli_exit_1_on_empty_stack(tmp_path: pathlib.Path, monkeypatch):
    cfg = _write(
        tmp_path / "p.md",
        """\
        ## Currently configured LLM stack

        ## Approved third-party endpoints (opt-in)
        """,
    )
    rc, out, err = _run(monkeypatch, ["--config", str(cfg)])
    assert rc == 1
    assert "empty" in err.lower()


def test_cli_exit_2_on_missing_config(tmp_path: pathlib.Path, monkeypatch):
    monkeypatch.delenv("PRIVACY_LLM_CONFIG", raising=False)
    monkeypatch.chdir(tmp_path)
    rc, out, err = _run(monkeypatch, [])
    assert rc == 2
    assert "no privacy-llm config" in err.lower()


def test_cli_reads_private_list_flag_in_banner(tmp_path: pathlib.Path, monkeypatch):
    cfg = _write(
        tmp_path / "p.md",
        """\
        ## Currently configured LLM stack
        - Claude Code

        ## Approved third-party endpoints (opt-in)
        """,
    )
    rc, out, err = _run(monkeypatch, ["--config", str(cfg), "--reads-private-list"])
    assert rc == 0
    assert "private-list" in out


# -- end-to-end against the framework's template ------------------------


def test_framework_template_is_approved_by_default(tmp_path: pathlib.Path, monkeypatch):
    """The shipped projects/_template/privacy-llm.md must pass the
    check out of the box (Claude Code only, no opt-in entries) — it
    is the starting state for every fresh adopter."""
    template = pathlib.Path(__file__).resolve().parents[3] / "projects" / "_template" / "privacy-llm.md"
    if not template.exists():
        # Tests sometimes run from a stripped checkout without the
        # template; skip rather than fail.
        return
    parsed = parse_config(template)
    verdicts = check.check_stack(parsed)
    assert verdicts, "template should declare at least Claude Code in its stack"
    bad = [v for v in verdicts if not v.approved]
    assert not bad, f"unapproved entries in shipped template: {bad}"
