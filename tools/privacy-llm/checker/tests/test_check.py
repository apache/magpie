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
    path.write_text(textwrap.dedent(body), encoding="utf-8")
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


# -- check_endpoint helper tests ---------------------------------------


def test_check_endpoint_default_approved():
    v = check.check_endpoint("http://localhost:8000/v1")
    assert v.approved is True
    assert "local-only" in v.reason


def test_check_endpoint_denied_no_config(monkeypatch, tmp_path):
    monkeypatch.delenv("PRIVACY_LLM_CONFIG", raising=False)
    monkeypatch.chdir(tmp_path)
    v = check.check_endpoint("https://api.example.com/v1")
    assert v.approved is False
    assert "denied" in v.reason


def test_check_endpoint_approved_opt_in():
    opt = OptInEntry(
        name="Example Provider",
        data_residency="Strict US",
        approved_by="PMC 2026-09-01",
    )
    cfg = ParsedConfig(path=pathlib.Path("/dev/null"), llm_stack=[], opt_in=[opt])
    v = check.check_endpoint(
        "https://api.example.com/v1",
        config=cfg,
        default_endpoint="https://api.example.com/v1",
        raw_desc="Example Provider (https://api.example.com/v1)",
    )
    assert v.approved is True


def test_check_endpoint_rejects_url_fragment_and_claude_code():
    """A URL containing a fragment is rejected and cannot trigger the Claude Code rule."""
    v = check.check_endpoint("https://evil.example.com/v1#claude code")
    assert v.approved is False
    assert "fragment" in v.reason


def test_check_endpoint_rejects_subdomain_opt_in_bypass():
    """An opt-in for api.typesafe.ai does not approve api.typesafe.ai.evil.example."""
    opt = OptInEntry(
        name="https://api.typesafe.ai",
        data_residency="eu-central-1",
        approved_by="PMC 2026-09-01",
    )
    cfg = ParsedConfig(path=pathlib.Path("/dev/null"), llm_stack=[], opt_in=[opt])
    v = check.check_endpoint("https://api.typesafe.ai.evil.example/v1", config=cfg)
    assert v.approved is False
    assert "denied" in v.reason


def test_check_endpoint_rejects_userinfo_opt_in_bypass():
    """A URL containing userinfo (e.g. user@host) is strictly rejected."""
    opt = OptInEntry(
        name="https://api.typesafe.ai",
        data_residency="eu-central-1",
        approved_by="PMC 2026-09-01",
    )
    cfg = ParsedConfig(path=pathlib.Path("/dev/null"), llm_stack=[], opt_in=[opt])
    v = check.check_endpoint("https://api.typesafe.ai@evil.example/v1", config=cfg)
    assert v.approved is False
    assert "userinfo" in v.reason


def test_check_endpoint_name_only_opt_in_rejects_different_host():
    """A name-only opt-in like 'TypeSafe — Jev API' never approves a non-default host."""
    opt = OptInEntry(
        name="TypeSafe — Jev API",
        data_residency="eu-central-1",
        approved_by="PMC 2026-09-01",
    )
    cfg = ParsedConfig(path=pathlib.Path("/dev/null"), llm_stack=[], opt_in=[opt])
    v = check.check_endpoint(
        "https://typesafe.evil.example/v1",
        config=cfg,
        default_endpoint="https://api.typesafe.ai/v1/systemone",
    )
    assert v.approved is False
    assert "denied" in v.reason


def test_check_endpoint_approved_opt_in_url():
    """An opt-in with a full URL approves endpoints sharing the exact same host."""
    opt = OptInEntry(
        name="https://api.typesafe.ai",
        data_residency="eu-central-1",
        approved_by="PMC 2026-09-01",
    )
    cfg = ParsedConfig(path=pathlib.Path("/dev/null"), llm_stack=[], opt_in=[opt])
    v = check.check_endpoint("https://api.typesafe.ai/v1/systemone", config=cfg)
    assert v.approved is True


def test_name_only_opt_in_rejects_empty_or_missing_raw_desc():
    """Empty or missing raw_desc must not match name-only opt-in entries."""
    opt = OptInEntry(
        name="AWS Bedrock — eu-central-1",
        data_residency="eu-central-1",
        approved_by="PMC 2026-09-01",
    )
    cfg = ParsedConfig(path=pathlib.Path("/dev/null"), llm_stack=[], opt_in=[opt])

    # No raw_desc provided
    v1 = check.check_endpoint(
        "https://api.typesafe.ai/v1/systemone",
        config=cfg,
        default_endpoint="https://api.typesafe.ai/v1/systemone",
    )
    assert v1.approved is False

    # Empty raw_desc
    v2 = check.check_endpoint(
        "https://api.typesafe.ai/v1/systemone",
        config=cfg,
        default_endpoint="https://api.typesafe.ai/v1/systemone",
        raw_desc="",
    )
    assert v2.approved is False

    # Whitespace raw_desc
    v3 = check.check_endpoint(
        "https://api.typesafe.ai/v1/systemone",
        config=cfg,
        default_endpoint="https://api.typesafe.ai/v1/systemone",
        raw_desc="   ",
    )
    assert v3.approved is False


def test_name_only_opt_in_requires_provider_in_desc():
    """Name-only opt-in matches only if the opt-in name appears in raw_desc."""
    opt_typesafe = OptInEntry(
        name="TypeSafe — Jev API",
        data_residency="eu-central-1",
        approved_by="PMC 2026-09-01",
    )
    cfg_typesafe = ParsedConfig(path=pathlib.Path("/dev/null"), llm_stack=[], opt_in=[opt_typesafe])

    v_match = check.check_endpoint(
        "https://api.typesafe.ai/v1/systemone",
        config=cfg_typesafe,
        default_endpoint="https://api.typesafe.ai/v1/systemone",
        raw_desc="TypeSafe Jev (https://api.typesafe.ai/v1/systemone)",
    )
    assert v_match.approved is True

    # If opt-in is AWS Bedrock, calling default endpoint with TypeSafe desc is rejected
    opt_aws = OptInEntry(
        name="AWS Bedrock — eu-central-1",
        data_residency="eu-central-1",
        approved_by="PMC 2026-09-01",
    )
    cfg_aws = ParsedConfig(path=pathlib.Path("/dev/null"), llm_stack=[], opt_in=[opt_aws])

    v_mismatch = check.check_endpoint(
        "https://api.typesafe.ai/v1/systemone",
        config=cfg_aws,
        default_endpoint="https://api.typesafe.ai/v1/systemone",
        raw_desc="TypeSafe Jev (https://api.typesafe.ai/v1/systemone)",
    )
    assert v_mismatch.approved is False
    assert "denied" in v_mismatch.reason


def test_extract_opt_in_host_rejects_model_version_tokens():
    """Model version tokens (3.5, 4.0, 1.0.0) are not treated as hostnames."""
    assert check._extract_opt_in_host("3.5 Sonnet (AWS Bedrock)") is None
    assert check._extract_opt_in_host("4.0 Omni") is None
    assert check._extract_opt_in_host("1.0.0 Model") is None
    assert check._extract_opt_in_host("api.example.com (Provider)") == "api.example.com"
    assert check._extract_opt_in_host("https://api.example.com/v1") == "api.example.com"


def test_check_endpoint_rejects_numeric_host_bypass_with_model_version_opt_in():
    """Opt-in starting with a version does not approve numeric/decimal host targets."""
    opt = OptInEntry(
        name="3.5 Sonnet (AWS Bedrock)",
        data_residency="eu-central-1",
        approved_by="PMC 2026-09-01",
    )
    cfg = ParsedConfig(path=pathlib.Path("/dev/null"), llm_stack=[], opt_in=[opt])

    v = check.check_endpoint("https://3.5/v1", config=cfg)
    assert v.approved is False
    assert "denied" in v.reason


def test_is_valid_hostname_rules():
    """_is_valid_hostname enforces standard hostname syntax and rejects invalid tokens."""
    assert check._is_valid_hostname("api.example.com") is True
    assert check._is_valid_hostname("bedrock-runtime.eu-central-1.amazonaws.com") is True
    assert check._is_valid_hostname("typesafe.ai") is True

    # Purely numeric or version tokens
    assert check._is_valid_hostname("3.5") is False
    assert check._is_valid_hostname("4.0") is False
    assert check._is_valid_hostname("1.0.0") is False
    assert check._is_valid_hostname("192.168.1.1") is False

    # Label syntax violations
    assert check._is_valid_hostname("-bad.example.com") is False
    assert check._is_valid_hostname("bad-.example.com") is False
    assert check._is_valid_hostname("example..com") is False
    assert check._is_valid_hostname("singlelabel") is False

    # Userinfo, fragments, slashes
    assert check._is_valid_hostname("user@example.com") is False
    assert check._is_valid_hostname("example.com/v1") is False
    assert check._is_valid_hostname("example.com#frag") is False
