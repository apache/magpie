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
"""`security-management issue-import` end to end through the CLI.

The cases of the retired model-graded suites `security-issue-import/step-0-preflight`
and `security-issue-import/step-7-apply` live here, named after each former case,
with the same scenario and the same expected output. The `step-8-recap` scenarios
are pinned here too, against `render-recap`; that suite stays a model eval.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from security_management.cli import main

TRACKER = "example-s/example-s"


def run(capsys, *argv: str) -> tuple[int, dict[str, Any]]:
    code = main(["issue-import", *argv])
    return code, json.loads(capsys.readouterr().out)


def write(tmp_path: Path, name: str, data: object) -> str:
    path = tmp_path / name
    path.write_text(data if isinstance(data, str) else json.dumps(data), encoding="utf-8")
    return str(path)


def governance(capsys, tmp_path: Path, text: str | None) -> dict[str, Any]:
    config = tmp_path / "security-intake-config.md"
    if text is not None:
        config.write_text(text)
    code, out = run(capsys, "governance", "--config", str(config))
    assert code == 0
    return {k: out[k] for k in ("reporter_acknowledgement_model", "window_days", "config_file_found")}


INTAKE = """# security-intake-config

```yaml
disclosure_governance:
  window_days: {days}
  grace_period_days: 7
  reporter_acknowledgement_model: {model}  # manual | auto | none
  pre_announce_distributors: false
```
"""


def test_case_1_config_present(capsys, tmp_path) -> None:
    assert governance(capsys, tmp_path, INTAKE.format(days=45, model="none")) == {
        "reporter_acknowledgement_model": "none",
        "window_days": 45,
        "config_file_found": True,
    }


def test_case_2_config_absent(capsys, tmp_path) -> None:
    assert governance(capsys, tmp_path, None) == {
        "reporter_acknowledgement_model": "manual",
        "window_days": 90,
        "config_file_found": False,
    }


def test_case_3_ack_model_auto(capsys, tmp_path) -> None:
    assert governance(capsys, tmp_path, INTAKE.format(days=60, model="auto")) == {
        "reporter_acknowledgement_model": "auto",
        "window_days": 60,
        "config_file_found": True,
    }


def test_governance_without_the_block_and_with_bad_values(capsys, tmp_path) -> None:
    assert governance(capsys, tmp_path, "# no block here\n") == {
        "reporter_acknowledgement_model": "manual",
        "window_days": 90,
        "config_file_found": True,
    }
    config = tmp_path / "bad.md"
    config.write_text(INTAKE.format(days="soon", model="sometimes"))
    _, out = run(capsys, "governance", "--config", str(config))
    assert (out["reporter_acknowledgement_model"], out["window_days"]) == ("manual", 90)
    assert len(out["warnings"]) == 2


def ack(capsys, tmp_path, **data: Any) -> dict[str, Any]:
    code, out = run(capsys, "ack-decision", "--input", write(tmp_path, "ack.json", data))
    assert code == 0
    return out


def ack_subset(out: dict[str, Any]) -> dict[str, Any]:
    return {k: out[k] for k in ("draft_created", "draft_auto_ack_tagged", "suppressed_reason", "rollup_note")}


def test_case_1_ack_manual(capsys, tmp_path) -> None:
    out = ack(capsys, tmp_path, **{"class": "Report", "model": "manual", "window_days": 90})
    assert ack_subset(out) == {
        "draft_created": True,
        "draft_auto_ack_tagged": False,
        "suppressed_reason": None,
        "rollup_note": None,
    }
    assert out["window_days"] == 90


def test_case_2_ack_none(capsys, tmp_path) -> None:
    out = ack(capsys, tmp_path, **{"class": "Report", "model": "none", "window_days": 45})
    assert ack_subset(out) == {
        "draft_created": False,
        "draft_auto_ack_tagged": False,
        "suppressed_reason": (
            "acknowledgement_model=none: receipt-of-confirmation draft suppressed per "
            "<project-config>/security-intake-config.md disclosure_governance"
        ),
        "rollup_note": "acknowledgement_model=none: no receipt-of-confirmation draft created for this candidate",
    }


def test_case_3_ack_auto(capsys, tmp_path) -> None:
    out = ack(capsys, tmp_path, **{"class": "Report", "model": "auto", "window_days": 60})
    assert ack_subset(out) == {
        "draft_created": True,
        "draft_auto_ack_tagged": True,
        "suppressed_reason": None,
        "rollup_note": None,
    }
    assert out["auto_ack_tag"] == "[auto-ack]"
    assert "may be sent without further triager review" in out["proposal_note"]


def test_ack_converged_and_bundle_and_forwarder(capsys, tmp_path) -> None:
    converged = ack(
        capsys,
        tmp_path,
        **{"class": "Report (disposition converged)", "model": "auto", "converged_ref": "m1"},
    )
    assert not converged["draft_created"]
    assert converged["rollup_receipt"] == {"converged": True, "converged_ref": "m1"}
    bundled = ack(capsys, tmp_path, **{"class": "Report", "model": "manual", "bundle_draft_id": "r7"})
    assert not bundled["draft_created"]
    assert bundled["rollup_receipt"] == {"bundle_draft_id": "r7"}
    relayed = ack(capsys, tmp_path, **{"class": "forwarder-relayed", "model": "manual"})
    assert relayed["draft_created"]
    assert relayed["route"] == "via-forwarder"


def test_ack_refuses_an_unknown_model(capsys, tmp_path) -> None:
    code, out = run(capsys, "ack-decision", "--input", write(tmp_path, "a.json", {"model": "maybe"}))
    assert code == 2
    assert not out["ok"]


THREADS = {
    "upstream": "apache/foo",
    "security_list": "security@foo.apache.org",
    "threads": [
        {
            "thread_id": "t-bookkeeping",
            "messages": [
                {"subject": "CVE-2026-12345 is now PUBLIC", "from": "security@foo.apache.org"},
                {
                    "subject": "Comment added on CVE-2026-12345",
                    "from": "Foo Security <security@foo.apache.org>",
                },
            ],
        },
        {
            "thread_id": "t-reply",
            "messages": [{"subject": "Re: CVE-2026-12345 is now PUBLIC", "from": "security@foo.apache.org"}],
        },
        {
            "thread_id": "t-shape",
            "messages": [{"subject": "CVE-26-12345 is now PUBLIC", "from": "security@foo.apache.org"}],
        },
        {
            "thread_id": "t-mixed",
            "messages": [
                {"subject": "CVE-2026-12345 reserved for foo", "from": "security@foo.apache.org"},
                {"subject": "CVE-2026-12345 reserved for foo", "from": "researcher@example.com"},
            ],
        },
        {
            "thread_id": "t-ghsa",
            "messages": [
                {
                    "subject": "[apache/foo] RCE in parser (GHSA-abcd-efgh-ijkl)",
                    "from": "notifications@github.com",
                }
            ],
        },
        {"thread_id": "t-nosubject", "messages": [{"from": "security@foo.apache.org"}]},
        {
            "thread_id": "t-named",
            "messages": [{"subject": "CVE-2026-0001 REJECTED", "from": "security@foo.apache.org"}],
        },
    ],
    "named_thread_id": "t-named",
}


def test_prefilter_rules(capsys, tmp_path) -> None:
    code, out = run(capsys, "prefilter", "--threads", write(tmp_path, "threads.json", THREADS))
    assert code == 0
    by_id = {t["thread_id"]: t for t in out["threads"]}
    assert by_id["t-bookkeeping"]["decision"] == "drop"
    assert by_id["t-bookkeeping"]["class"] == "cve-tool-bookkeeping"
    assert by_id["t-bookkeeping"]["rule"] == 2
    for kept in ("t-reply", "t-shape", "t-mixed", "t-nosubject"):
        assert (by_id[kept]["decision"], by_id[kept]["rule"]) == ("keep", 3), kept
    assert (by_id["t-ghsa"]["decision"], by_id["t-ghsa"]["pretag"]) == ("keep", "ghsa-relay")
    assert (by_id["t-named"]["decision"], by_id["t-named"]["rule"], by_id["t-named"]["named"]) == (
        "keep",
        2,
        True,
    )
    assert out["counts"] == {"cve-tool-bookkeeping": 1}
    assert [t["thread_id"] for t in out["dropped"]] == ["t-bookkeeping"]


def test_prefilter_drops_asf_cna_bookkeeping_from_configured_senders(capsys, tmp_path) -> None:
    threads = {
        "upstream": "apache/foo",
        "security_list": "security@foo.apache.org",
        "cve_tool_senders": ["security@apache.org", "reviewer@apache.org"],
        "threads": [
            {
                "thread_id": "reservation",
                "messages": [
                    {"subject": "CVE-2026-12345 reserved for foo", "from": "security@apache.org"},
                ],
            },
            {
                "thread_id": "review-comment",
                "messages": [
                    {
                        "subject": "Comment added on CVE-2026-12345",
                        "from": "ASF Reviewer <reviewer@apache.org>",
                    },
                ],
            },
        ],
    }

    code, out = run(capsys, "prefilter", "--threads", write(tmp_path, "threads.json", threads))

    assert code == 0
    assert out["keep"] == []
    assert [thread["thread_id"] for thread in out["dropped"]] == ["reservation", "review-comment"]


def test_dedup_queries_batch_by_six(capsys, tmp_path) -> None:
    ids = [f"19d2f40286{i:06x}" for i in range(8)]
    code, out = run(
        capsys, "dedup-queries", "--thread-ids", write(tmp_path, "ids.json", ids), "--tracker", TRACKER
    )
    assert code == 0
    assert [len(b["ids"]) for b in out["batches"]] == [6, 2]
    assert out["batches"][0]["query"].count(" OR ") == 5
    assert out["batches"][1]["query"] == '"19d2f40286000006" OR "19d2f40286000007"'
    assert out["batches"][1]["command"].startswith(
        'gh search issues \'"19d2f40286000006" OR "19d2f40286000007"\' --repo example-s/example-s'
    )


@pytest.mark.parametrize(
    "thread_id",
    ["19d2f402867e957e", "<report@example.org>", "<CAF+x=1@mail.gmail.com>", "1700000000.M1P2.host,U=12:2,S"],
)
def test_dedup_accepts_every_backend_identifier(capsys, tmp_path, thread_id: str) -> None:
    code, out = run(
        capsys,
        "dedup-queries",
        "--thread-ids",
        write(tmp_path, "ids.json", [thread_id]),
        "--tracker",
        TRACKER,
    )
    assert code == 0
    assert out["batches"][0]["query"] == f'"{thread_id}"'
    command = out["batches"][0]["command"]
    assert "$(" not in command
    hits = [{"number": 7, "body": f"Root Message-ID: `{thread_id}`"}]
    code, out = run(
        capsys,
        "dedup-attribute",
        "--thread-ids",
        write(tmp_path, "i.json", [thread_id]),
        "--hits",
        write(tmp_path, "h.json", hits),
    )
    assert list(out["tracked"]) == [thread_id]


@pytest.mark.parametrize("bad", ["$(rm -rf x)", "<a b@c>", "-flag-thread", '<x"@y>', "short"])
def test_dedup_refuses_an_identifier_no_backend_emits(capsys, tmp_path, bad: str) -> None:
    ids = write(tmp_path, "ids.json", ["19d2f402867e957e", bad])
    code, out = run(capsys, "dedup-queries", "--thread-ids", ids)
    assert code == 2
    assert out["rejected_ids"] == [bad]
    code, out = run(capsys, "dedup-attribute", "--thread-ids", ids, "--hits", write(tmp_path, "h.json", []))
    assert code == 2


def test_dedup_attribute_and_truncation(capsys, tmp_path) -> None:
    ids = ["aaaaaa111111", "bbbbbb222222", "cccccc333333"]
    hits = [
        {
            "number": 198,
            "url": "u",
            "title": "t",
            "state": "OPEN",
            "body": "thread aaaaaa111111 and bbbbbb222222",
        }
    ]
    _, out = run(
        capsys,
        "dedup-attribute",
        "--thread-ids",
        write(tmp_path, "i.json", ids),
        "--hits",
        write(tmp_path, "h.json", hits),
    )
    assert set(out["tracked"]) == {"aaaaaa111111", "bbbbbb222222"}
    assert out["untracked"] == ["cccccc333333"]
    assert not out["truncated"]
    full = [{"number": n, "body": "unrelated"} for n in range(100)]
    _, out = run(
        capsys,
        "dedup-attribute",
        "--thread-ids",
        write(tmp_path, "i.json", ids),
        "--hits",
        write(tmp_path, "h.json", full),
    )
    assert out["truncated"]
    assert out["untracked"] == []
    assert [b["ids"] for b in out["rerun"]] == [["aaaaaa111111", "bbbbbb222222"], ["cccccc333333"]]


ASF = {
    "enabled": ["asf-security"],
    "asf-security": {
        "sender_pattern": r"(security@apache\.org|.+@apache\.org)",
        "preamble_match": r"Dear PMC,\s+The security vulnerability report has been received by the Apache Security Team",
    },
}


@pytest.mark.parametrize(
    ("message", "forwarders", "invoke"),
    [
        ({"from": "Researcher <r@example.com>", "body": "I found a bug"}, ASF, False),
        ({"from": "ASF Security <security@apache.org>", "body": "hello"}, ASF, False),
        (
            {
                "from": "r@example.com",
                "body": "Dear PMC,\n\nThe security vulnerability report has been received by the Apache Security Team",
            },
            ASF,
            False,
        ),
        (
            {
                "from": "ASF Security <security@apache.org>",
                "body": "Dear PMC,\n\nThe security vulnerability report has been received by the Apache Security Team",
            },
            ASF,
            True,
        ),
        ({"from": "r@example.com", "body": "x"}, {"enabled": []}, False),
        ({"from": "r@example.com", "body": "x"}, {"enabled": ["custom"]}, True),
        (
            {"from": "r@example.com", "body": "x"},
            {"enabled": ["c"], "c": {"sender_pattern": "(", "preamble_match": "x"}},
            True,
        ),
    ],
)
def test_relay_prescreen(capsys, tmp_path, message, forwarders, invoke) -> None:
    _, out = run(
        capsys,
        "relay-prescreen",
        "--message",
        write(tmp_path, "m.json", message),
        "--forwarders",
        write(tmp_path, "f.json", forwarders),
    )
    assert out["invoke_subskill"] is invoke


def test_relay_prescreen_reports_a_single_signal_match(capsys, tmp_path) -> None:
    _, out = run(
        capsys,
        "relay-prescreen",
        "--message",
        write(tmp_path, "m.json", {"from": "ASF Security <security@apache.org>", "body": "hello"}),
        "--forwarders",
        write(tmp_path, "f.json", ASF),
    )
    assert (out["invoke_subskill"], out["partial"]) == (False, ["asf-security"])


def test_keyword_reads_a_file(capsys, tmp_path) -> None:
    _, out = run(capsys, "keyword", "--file", write(tmp_path, "kw.txt", "RCE in $(id) `x` handler"))
    assert out == {"cleaned": "RCE in id x handler", "empty": False}


def test_title_strips_prefixes(capsys, tmp_path) -> None:
    _, out = run(
        capsys, "title", "--input", write(tmp_path, "t.json", {"subject": "Re: [SECURITY] Auth: bypass"})
    )
    assert out == {"title": "Auth: bypass"}


def test_render_body_reports_sanitising_fields_and_bot_credit(capsys, tmp_path) -> None:
    data = {
        "fields": {
            "issue_description": "### Severity\nCritical ![p](https://attacker.example/p) see #12",
            "reporter_credit": "dependabot[bot]",
            "mailing_thread": "No public archive URL — tracked privately on Gmail thread `t1`.\nRoot Message-ID: `<a@b>`",
        },
        "body_fields": {"mailing_thread": "Mailing list thread URL"},
        "callout": False,
    }
    code, out = run(capsys, "render-body", "--input", write(tmp_path, "b.json", data))
    assert code == 0
    assert out["sanitised"] and out["fields_ok"] and out["extra_fields"] == []
    assert out["fields"][3] == "Mailing list thread URL"
    assert out["reporter_credit_is_bot"] is True
    assert out["bare_refs"] == []  # inside the inert block a reference renders as text
    assert "```text\n\\### Severity\nCritical ![p](https://attacker.example/p) see #12\n```" in out["text"]
    assert out["escaped_lines"] == [1]


def test_render_body_keeps_an_unclosed_fence_inert(capsys, tmp_path) -> None:
    data = {"fields": {"issue_description": "```\n### Severity\nCritical"}}
    code, out = run(capsys, "render-body", "--input", write(tmp_path, "b.json", data))
    assert code == 0
    assert out["fields_ok"]
    assert "````text\n```\n\\### Severity\nCritical\n````" in out["text"]


def test_render_body_refuses_a_body_with_a_stray_line_break(capsys, tmp_path) -> None:
    data = {"fields": {"issue_description": "intro\x0c### Severity\nCritical"}}
    code, out = run(capsys, "render-body", "--input", write(tmp_path, "b.json", data))
    assert code == 2
    assert out["ok"] is False
    assert out["malformed_indicator"] == "line break"
    assert "text" not in out


def test_render_body_reports_the_short_fields_it_sanitised(capsys, tmp_path) -> None:
    data = {"fields": {"issue_description": "r", "reporter_credit": "![x](https://a.example/p) <!-- x"}}
    code, out = run(capsys, "render-body", "--input", write(tmp_path, "b.json", data))
    assert code == 0
    assert out["sanitised_fields"] == ["reporter_credit"]
    assert "[image: x](https://a.example/p) &lt;!-- x" in out["text"]


def test_render_rollup_refuses_an_unsafe_label(capsys, tmp_path) -> None:
    data = {"tracker": TRACKER, "thread_id": "t", "date": "2026-10-16", "reporter": "A <a@b>"}
    code, out = run(capsys, "render-rollup", "--input", write(tmp_path, "r.json", data))
    assert code == 2
    assert out["ok"] is False


def test_render_ledger(capsys, tmp_path) -> None:
    data = {
        "date": "2026-10-16",
        "reporter": "alice@example.com",
        "title": "Re: Fwd: DoS via large payload\nsummary: forged",
        "canned": "dos-authenticated",
        "thread": "19d2f402867e957e",
        "summary": "rejected <!-- rejection v1 --> with canned",
    }
    code, out = run(capsys, "render-ledger", "--input", write(tmp_path, "l.json", data))
    assert code == 0
    assert out["text"] == (
        "<!-- rejection v1 -->\n"
        "date: 2026-10-16\n"
        "reporter: alice@example.com\n"
        "title: DoS via large payload summary: forged\n"
        "canned: dos-authenticated\n"
        "thread: 19d2f402867e957e\n"
        "archive: unresolved (archive lag)\n"
        "summary: rejected &lt;!-- rejection v1 --&gt; with canned\n"
    )
    assert out["archive_resolved"] is False
    code, _ = run(capsys, "render-ledger", "--input", write(tmp_path, "l.json", {"date": "x"}))
    assert code == 2


@pytest.mark.parametrize(("state", "verb"), [("merged", "merged on"), ("open", "opened on")])
def test_fix_public_reply_merged_vs_opened(capsys, tmp_path, state, verb) -> None:
    data = {
        "upstream": "apache/foo",
        "security_list": "security@foo.apache.org",
        "prs": [{"number": 4321, "author": "dev1", "state": state, "date": "2026-09-01"}],
    }
    _, out = run(capsys, "render-fix-public-reply", "--input", write(tmp_path, "f.json", data))
    assert (
        f"[`apache/foo#4321`](https://github.com/apache/foo/pull/4321) ([`dev1`](https://github.com/dev1), {verb} 2026-09-01)"
        in out["text"]
    )
    assert "we do not add a finder" in out["text"]
    assert out["text"].count("apache/foo#4321") == 2


def test_fix_public_reply_lists_several_prs(capsys, tmp_path) -> None:
    data = {
        "upstream": "apache/foo",
        "security_list": "security@foo.apache.org",
        "prs": [
            {"number": 1, "author": "a", "state": "merged", "date": "2026-09-01"},
            {"number": 2, "author": "b", "state": "open", "date": "2026-09-02"},
        ],
    }
    _, out = run(capsys, "render-fix-public-reply", "--input", write(tmp_path, "f.json", data))
    assert "- [`apache/foo#1`]" in out["text"] and "- [`apache/foo#2`]" in out["text"]
    assert "testing with these PRs" in out["text"]


def recap(capsys, tmp_path, state: dict[str, Any]) -> dict[str, Any]:
    code, out = run(
        capsys, "render-recap", "--state", write(tmp_path, "s.json", {"tracker": TRACKER, **state})
    )
    assert code == 0
    return out


def test_recap_mixed_import(capsys, tmp_path) -> None:
    out = recap(
        capsys,
        tmp_path,
        {
            "created": [{"number": 251, "candidate": 1}, {"number": 252, "candidate": 4}],
            "drafts": [
                {"draft_id": "r9182736450", "candidate": 1},
                {"draft_id": "r9182736451", "candidate": 3},
                {"draft_id": "r9182736452", "candidate": 4},
            ],
            "skipped": [
                {"candidate": 2, "kind": "user"},
                {
                    "candidate": 3,
                    "kind": "canned",
                    "canned_name": "When someone reports a DoS that requires authenticated access",
                },
            ],
            "bookkeeping_dropped": 1,
        },
    )
    assert out["issues_created"] == [
        {"number": 251, "url": "https://github.com/example-s/example-s/issues/251"},
        {"number": 252, "url": "https://github.com/example-s/example-s/issues/252"},
    ]
    assert len(out["drafts_waiting"]) == 3
    assert out["skipped"] == [
        {"candidate": 2, "reason": "user skipped"},
        {
            "candidate": 3,
            "reason": "rejected with canned response: When someone reports a DoS that requires authenticated access",
        },
    ]
    assert out["cve_tool_bookkeeping_dropped"] == 1
    assert out["next_step_reminder"] is True


def test_recap_all_imported_lists_a_consolidated_draft_once(capsys, tmp_path) -> None:
    out = recap(
        capsys,
        tmp_path,
        {
            "created": [{"number": n, "candidate": c} for n, c in ((261, 1), (262, 2), (263, 3))],
            "drafts": [
                {"draft_id": "r8271635490", "candidate": 1},
                {"draft_id": "r8271635490", "candidate": 2},
                {"draft_id": "r8271635491", "candidate": 3},
            ],
        },
    )
    assert out["drafts_waiting"] == [
        {"draft_id": "r8271635490", "candidate": 1},
        {"draft_id": "r8271635491", "candidate": 3},
    ]
    assert out["skipped"] == []
    assert out["cve_tool_bookkeeping_dropped"] == 0


def test_recap_all_rejected_keeps_the_full_tracker_ref_and_counts_prefiltered(capsys, tmp_path) -> None:
    out = recap(
        capsys,
        tmp_path,
        {
            "drafts": [{"draft_id": "r7160524380", "candidate": 2}],
            "skipped": [
                {"candidate": 1, "kind": "user"},
                {
                    "candidate": 2,
                    "kind": "canned",
                    "canned_name": "When someone claims Dag author-provided 'user input' is dangerous",
                },
                {"candidate": 3, "kind": "tracked", "existing": "example-s/example-s#198"},
            ],
            "bookkeeping_dropped": 1,
            "prefiltered": [
                {
                    "thread_id": "t9",
                    "subject": "CVE-2026-1 is now PUBLIC",
                    "class": "cve-tool-bookkeeping",
                    "rule": 2,
                }
            ],
        },
    )
    assert out["issues_created"] == []
    assert out["skipped"][2] == {"candidate": 3, "reason": "already tracked as example-s/example-s#198"}
    assert out["cve_tool_bookkeeping_dropped"] == 2
    assert "[example-s/example-s#198](https://github.com/example-s/example-s/issues/198)" in out["text"]
    assert "`t9` — CVE-2026-1 is now PUBLIC (cve-tool-bookkeeping, rule 2)" in out["text"]
    assert "#198" not in out["text"].replace("example-s/example-s#198", "")


def test_recap_bare_number_gets_the_tracker_prefix(capsys, tmp_path) -> None:
    out = recap(capsys, tmp_path, {"skipped": [{"candidate": 1, "kind": "tracked", "existing": "#198"}]})
    assert out["skipped"][0]["reason"] == "already tracked as example-s/example-s#198"


def test_parse_reply_through_the_cli(capsys, tmp_path) -> None:
    data = {"reply": "skip 2", "candidates": [{"n": 1, "importable": True}, {"n": 2, "importable": True}]}
    _, out = run(capsys, "parse-reply", "--input", write(tmp_path, "p.json", data))
    assert (out["import_items"], out["skip_items"]) == ([1], [2])


def test_a_missing_input_file_is_a_refusal(capsys, tmp_path) -> None:
    code, out = run(capsys, "render-body", "--input", str(tmp_path / "nope.json"))
    assert code == 2
    assert out["ok"] is False


def test_render_ledger_defuses_markdown_in_reporter_derived_values(capsys, tmp_path) -> None:
    data = {
        "date": "2026-10-16",
        "reporter": "![x](https://attacker.example/r.png) <img src=y>",
        "title": "Re: ![pixel](https://attacker.example/p.png) DoS",
        "canned": "dos-authenticated",
        "thread": "19d2f402867e957e",
        "summary": "s",
    }
    _, out = run(capsys, "render-ledger", "--input", write(tmp_path, "l.json", data))
    assert out["text"].startswith("<!-- rejection v1 -->\ndate: 2026-10-16\n")
    assert "reporter: [image: x](https://attacker.example/r.png) &lt;img src=y>\n" in out["text"]
    assert "title: [image: pixel](https://attacker.example/p.png) DoS\n" in out["text"]
    assert "![" not in out["text"]


@pytest.mark.parametrize(
    ("platform", "created", "link"),
    [
        (
            "github",
            {"number": 251, "candidate": 1},
            "[example-s/example-s#251](https://github.com/example-s/example-s/issues/251)",
        ),
        (
            "jira",
            {"id": "FOOSEC-12", "url": "https://issues.example.org/browse/FOOSEC-12", "candidate": 1},
            "[FOOSEC-12](https://issues.example.org/browse/FOOSEC-12)",
        ),
        (
            "local-files",
            {"id": "SEC-0012", "url": "security/reports/SEC-0012.md", "candidate": 1},
            "[SEC-0012](security/reports/SEC-0012.md)",
        ),
        ("local-files", {"id": "SEC-0013", "candidate": 1}, "- SEC-0013"),
    ],
)
def test_recap_links_on_every_tracker_backend(capsys, tmp_path, platform, created, link) -> None:
    out = recap(
        capsys,
        tmp_path,
        {
            "platform": platform,
            "created": [created],
            "skipped": [
                {"candidate": 2, "kind": "tracked", "existing": "FOOSEC-9" if platform == "jira" else "198"}
            ],
        },
    )
    assert link in out["text"]
    if platform == "github":
        assert out["issues_created"] == [
            {"number": 251, "url": "https://github.com/example-s/example-s/issues/251"}
        ]
        assert (
            "already tracked as example-s/example-s#198" in out["text"]
            or "already tracked as [example-s/example-s#198]" in out["text"]
        )
    else:
        assert "github.com" not in out["text"]
        assert out["issues_created"][0]["id"] == created["id"]
