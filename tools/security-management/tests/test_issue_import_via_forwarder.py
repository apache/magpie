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
"""`security-management issue-import-via-forwarder` end to end through the CLI.

The cases of the retired model-graded `security-issue-import-via-forwarder`
suites `step-0-preflight`, `step-1-detect-adapter` (cases 1, 2, 3 and 6) and
`step-3-route-drafts` live here, named after each former case, with the same
inputs and expected output. Step 1 cases 4 (injection in the body) and 5
(collaborator warning) and all of step 2 stay model evals; case 5's warning is
pinned here too.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from security_management.cli import main

REPO = Path(__file__).resolve().parents[3]
ASF = {
    "name": "asf-security",
    "sender_pattern": "security@apache.org",
    "preamble_match": "The Apache Security Team has received",
}
RELAY = {
    "name": "platform-relay",
    "sender_pattern": "notifications@relay.example",
    "preamble_match": "A vulnerability has been reported via the relay platform",
}
ASF_BODY = (
    "The Apache Security Team has received the following security report and\n"
    "is forwarding it to the Airflow security list for triage.\n"
)


def run(capsys, *argv: str) -> tuple[int, dict[str, Any]]:
    code = main(["issue-import-via-forwarder", *argv])
    return code, json.loads(capsys.readouterr().out)


def write(tmp_path: Path, name: str, data: object) -> str:
    path = tmp_path / name
    path.write_text(json.dumps(data), encoding="utf-8")
    return str(path)


def forwarders(*adapters: dict[str, str]) -> dict[str, Any]:
    return {"enabled": [a["name"] for a in adapters], **{a["name"]: a for a in adapters}}


def preflight(capsys, tmp_path, enabled: list[str], message: dict[str, str]) -> tuple[int, dict[str, Any]]:
    return run(
        capsys,
        "preflight",
        "--forwarders",
        write(tmp_path, "f.json", {"enabled": enabled}),
        "--message",
        write(tmp_path, "m.json", message),
        "--framework",
        str(REPO),
    )


MESSAGE = {"from": "security@apache.org", "date": "Mon, 2 Jun 2025 09:14:22 +0000", "body": ASF_BODY}
KEYS = ("preflight_passed", "outcome", "error", "note")


def test_case_1_empty_enabled(capsys, tmp_path) -> None:
    code, out = preflight(capsys, tmp_path, [], MESSAGE)
    assert code == 0
    assert out == {
        "preflight_passed": False,
        "outcome": "no-forwarder-config",
        "match": None,
        "sub_skill_applied": False,
        "error": None,
        "note": "forwarders.enabled is empty, so no relay handling is configured; "
        "the parent skill proceeds with its direct-reporter path.",
    }


def test_case_2_adapter_not_installed(capsys, tmp_path) -> None:
    message = {"from": "notifications@relay.example", "date": "Mon, 2 Jun 2025 11:02:00 +0000", "body": "x"}
    code, out = preflight(capsys, tmp_path, ["platform-relay"], message)
    assert code == 2
    assert {k: out[k] for k in KEYS} == {
        "preflight_passed": False,
        "outcome": "abort",
        "error": "adapter `platform-relay` is declared in forwarders.enabled but is not installed under "
        "tools/forwarder-relay/; aborting.",
        "note": None,
    }


def test_case_3_malformed_message(capsys, tmp_path) -> None:
    message = {"date": "Mon, 2 Jun 2025 12:30:00 +0000", "body": ASF_BODY}
    code, out = preflight(capsys, tmp_path, ["asf-security"], message)
    assert code == 2
    assert {k: out[k] for k in KEYS} == {
        "preflight_passed": False,
        "outcome": "abort",
        "error": "inbound message is missing a `From:` header; a relay message stripped of its headers is not "
        "a relay message, so the skill fails fast.",
        "note": None,
    }


def test_case_4_valid_preflight(capsys, tmp_path) -> None:
    code, out = preflight(capsys, tmp_path, ["asf-security"], MESSAGE)
    assert code == 0
    assert {k: out[k] for k in KEYS} == {
        "preflight_passed": True,
        "outcome": "proceed",
        "error": None,
        "note": None,
    }


def test_an_adapter_directory_counts_as_installed(capsys, tmp_path) -> None:
    (tmp_path / "tools/forwarder-relay/custom-relay").mkdir(parents=True)
    code, out = run(
        capsys,
        "preflight",
        "--forwarders",
        write(tmp_path, "f.json", {"enabled": ["custom-relay"]}),
        "--message",
        write(tmp_path, "m.json", MESSAGE),
        "--framework",
        str(tmp_path),
    )
    assert (code, out["outcome"]) == (0, "proceed")
    _, out = preflight(capsys, tmp_path, ["asf-security"], {**MESSAGE, "date": ""})
    assert "`Date:` header" in out["error"]


def detect(
    capsys, tmp_path, message: dict[str, str], *adapters: dict[str, str], collaborators=None
) -> dict[str, Any]:
    argv = ["detect", "--message", write(tmp_path, "m.json", message)]
    argv += ["--forwarders", write(tmp_path, "f.json", forwarders(*adapters))]
    if collaborators is not None:
        argv += ["--collaborators", write(tmp_path, "c.json", collaborators)]
    code, out = run(capsys, *argv)
    assert code == 0
    return out


DETECT_KEYS = ("match", "sub_skill_applied", "preamble_snippet", "sender_matched", "collaborator_warning")


def test_case_1_asf_relay_match(capsys, tmp_path) -> None:
    out = detect(capsys, tmp_path, {"from": "security@apache.org", "body": ASF_BODY + "\nCredit: Sam"}, ASF)
    assert {k: out[k] for k in DETECT_KEYS} == {
        "match": "asf-security",
        "sub_skill_applied": True,
        "preamble_snippet": "The Apache Security Team has received the following security report and",
        "sender_matched": "security@apache.org",
        "collaborator_warning": False,
    }


def test_case_2_no_adapter_match(capsys, tmp_path) -> None:
    message = {"from": "Jane Doe <jane@example.org>", "body": "Hi, I found an XSS in the UI.\n"}
    out = detect(capsys, tmp_path, message, ASF)
    assert (out["match"], out["sub_skill_applied"]) == (None, False)
    assert out["note"].startswith("no registered forwarder adapter matched")


def test_case_3_platform_relay_match(capsys, tmp_path) -> None:
    body = "A vulnerability has been reported via the relay platform for Apache Airflow.\n\nReporter: Maria\n"
    out = detect(capsys, tmp_path, {"from": "notifications@relay.example", "body": body}, ASF, RELAY)
    assert {k: out[k] for k in DETECT_KEYS} == {
        "match": "platform-relay",
        "sub_skill_applied": True,
        "preamble_snippet": "A vulnerability has been reported via the relay platform for Apache Airflow.",
        "sender_matched": "notifications@relay.example",
        "collaborator_warning": False,
    }


def test_case_6_adapter_precedence(capsys, tmp_path) -> None:
    body = ASF_BODY + "\nA vulnerability has been reported via the relay platform for Apache Airflow.\n"
    out = detect(capsys, tmp_path, {"from": "security@apache.org", "body": body}, ASF, RELAY)
    assert {k: out[k] for k in DETECT_KEYS} == {
        "match": "asf-security",
        "sub_skill_applied": True,
        "preamble_snippet": "The Apache Security Team has received the following security report and",
        "sender_matched": "security@apache.org",
        "collaborator_warning": False,
    }
    assert [a["adapter"] for a in out["adapters"]] == ["asf-security"]


def test_the_collaborator_warning_of_former_case_5(capsys, tmp_path) -> None:
    adapter = {**ASF, "sender_pattern": ".*@apache\\.org"}
    out = detect(
        capsys,
        tmp_path,
        {"from": "j.security-member@apache.org", "body": ASF_BODY},
        adapter,
        collaborators=["j.security-member@apache.org", "a.committer@apache.org"],
    )
    assert (out["match"], out["collaborator_warning"]) == ("asf-security", True)


def test_preamble_only_match_and_the_400_character_window(capsys, tmp_path) -> None:
    out = detect(capsys, tmp_path, {"from": "someone@example.org", "body": ASF_BODY}, ASF)
    assert (out["match"], out["sender_matched"]) == ("asf-security", None)
    late = "x" * 400 + ASF_BODY
    out = detect(capsys, tmp_path, {"from": "someone@example.org", "body": late}, ASF)
    assert out["match"] is None


def test_an_unresolved_adapter_pattern_is_refused(capsys, tmp_path) -> None:
    code, _ = run(
        capsys,
        "detect",
        "--message",
        write(tmp_path, "m.json", MESSAGE),
        "--forwarders",
        write(tmp_path, "f.json", {"enabled": ["asf-security"], "asf-security": {"preamble_match": "x"}}),
    )
    assert code == 2


@pytest.mark.parametrize(
    ("name", "kind", "is_bot"),
    [
        ("Sam Researcher", "human", False),
        ("dependabot[bot]", "tool", True),
        ("Acme SOC", "service", False),
        ("N-a3f9d2", "human", False),
        ("", "unknown", False),
    ],
)
def test_credit_kind(capsys, tmp_path, name: str, kind: str, is_bot: bool) -> None:
    data = {"name": name, "kind_hints": {"tool": ["scanner\\b"], "service": ["\\bsoc\\b"]}}
    _, out = run(capsys, "credit-kind", "--input", write(tmp_path, "c.json", data))
    assert (out["kind"], out["is_bot"]) == (kind, is_bot)
    assert out["name"] == name


@pytest.mark.parametrize(
    ("value", "first"),
    [
        ("@some-liaison", "Some"),
        ("Sam Researcher <s@x.example>", "Sam"),
        ("security@apache.org", None),
        ("", None),
    ],
)
def test_first_name(capsys, tmp_path, value: str, first: str | None) -> None:
    _, out = run(capsys, "first-name", "--input", write(tmp_path, "n.json", {"name": value}))
    assert out["first_name"] == first


ADAPTER = {
    "name": "asf-security",
    "contact_handle": "@asf-security-liaison",
    "via_forwarder_question_mode": True,
}
ROUTE_KEYS = (
    "mode",
    "to_recipients",
    "addressing_block_emitted",
    "question_mode",
    "negative_space_suppressed",
)


def route(capsys, tmp_path, adapter: dict[str, Any], *argv: str) -> dict[str, Any]:
    code, out = run(capsys, "route", *argv, "--adapter", write(tmp_path, "a.json", adapter))
    assert code == 0
    return {k: out[k] for k in ROUTE_KEYS if k in out}


def test_case_1_import_mode(capsys, tmp_path) -> None:
    assert route(capsys, tmp_path, ADAPTER, "--mode", "import", "--milestone", "receipt") == {
        "mode": "import",
        "to_recipients": ["@asf-security-liaison"],
        "addressing_block_emitted": True,
        "question_mode": True,
        "negative_space_suppressed": False,
    }


def test_case_2_invalidate_mode(capsys, tmp_path) -> None:
    adapter = {**ADAPTER, "via_forwarder_question_mode": False}
    assert route(capsys, tmp_path, adapter, "--mode", "invalidate", "--milestone", "assessed-invalid") == {
        "mode": "invalidate",
        "to_recipients": ["@asf-security-liaison"],
        "addressing_block_emitted": True,
        "question_mode": False,
        "negative_space_suppressed": False,
    }


def test_case_3_sync_negative_space(capsys, tmp_path) -> None:
    assert route(capsys, tmp_path, ADAPTER, "--mode", "sync", "--milestone", "workflow-status") == {
        "mode": "sync",
        "to_recipients": [],
        "addressing_block_emitted": False,
        "negative_space_suppressed": True,
    }


def test_case_4_sync_relayable(capsys, tmp_path) -> None:
    assert route(capsys, tmp_path, ADAPTER, "--mode", "sync", "--milestone", "advisory-sent") == {
        "mode": "sync",
        "to_recipients": ["@asf-security-liaison"],
        "addressing_block_emitted": True,
        "question_mode": True,
        "negative_space_suppressed": False,
    }


def test_route_picks_the_first_handle_and_needs_a_sync_milestone(capsys, tmp_path) -> None:
    adapter = {**ADAPTER, "contact_handle": ["@first", "@second"]}
    code, out = run(capsys, "route", "--mode", "import", "--adapter", write(tmp_path, "a.json", adapter))
    assert (code, out["to_recipients"], out["fallback_recipients"]) == (0, ["@first"], ["@second"])
    code, _ = run(capsys, "route", "--mode", "sync", "--adapter", write(tmp_path, "a.json", adapter))
    assert code == 2
    code, out = run(
        capsys,
        "route",
        "--mode",
        "sync",
        "--milestone",
        "cve-allocated",
        "--adapter",
        write(tmp_path, "a.json", adapter),
    )
    assert out["negative_space_suppressed"] is False
