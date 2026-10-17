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
"""`security-management issue-triage` end to end through the CLI.

The cases of the retired model-graded `security-issue-triage` suites
`step-1-selector`, `step-5-confirm` and `step-7-recap`, and cases 1 and 2 of
`step-6-body-scrub`, live here, named after each former case, with the same
scenario and expected output. The `step-26-precedent-search` scenarios pin
`precedent-signal` here; that suite stays a model eval (rating a match is
judgement).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from security_management.cli import main

TRACKER = "example-s/example-s"
ROSTER = ["alice", "bob", "carol", "dave"]


def run(capsys, tmp_path: Path, command: str, data: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    path = tmp_path / f"{command}.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    code = main(["issue-triage", command, "--input", str(path)])
    return code, json.loads(capsys.readouterr().out)


def selector(capsys, tmp_path, invocation: str, **extra: Any) -> tuple[int, dict[str, Any]]:
    return run(capsys, tmp_path, "selector", {"invocation": invocation, "tracker": TRACKER, **extra})


def picked(out: dict[str, Any]) -> dict[str, Any]:
    return {k: out[k] for k in ("action", "issue_numbers", "scope_label", "cve_token")}


# --- step-1-selector -------------------------------------------------------


def test_step1_case_1_default(capsys, tmp_path):
    code, out = selector(capsys, tmp_path, "triage")
    assert code == 0
    assert picked(out) == {
        "action": "list_query",
        "issue_numbers": None,
        "scope_label": None,
        "cve_token": None,
    }
    assert out["command"] == (
        'gh issue list --repo example-s/example-s --state open --label "needs triage" '
        "--limit 1000 --json number,title,labels,updatedAt"
    )


def test_step1_case_2_verbatim_numbers(capsys, tmp_path):
    code, out = selector(capsys, tmp_path, "triage #212, #215")
    assert code == 0
    assert picked(out) == {
        "action": "verbatim",
        "issue_numbers": [212, 215],
        "scope_label": None,
        "cve_token": None,
    }
    assert out["explicit"] is True and out["command"] is None


def test_step1_case_3_scope_label(capsys, tmp_path):
    code, out = selector(capsys, tmp_path, "triage scope:providers")
    assert code == 0
    assert picked(out) == {
        "action": "list_query",
        "issue_numbers": None,
        "scope_label": "providers",
        "cve_token": None,
    }
    assert '--label "needs triage" --label "providers"' in out["command"]


def test_step1_case_4_invalid_cve_format(capsys, tmp_path):
    code, out = selector(capsys, tmp_path, "triage CVE-ABCD-1234")
    assert code == 2
    assert out["action"] == "error" and out["cve_token"] is None
    assert out["error"] == "CVE-ABCD-1234 does not match expected format CVE-YYYY-NNNNN"


def test_step1_case_5_retriage_no_selector(capsys, tmp_path):
    code, out = selector(capsys, tmp_path, "--retriage")
    assert code == 2
    assert out["action"] == "error"
    assert out["error"] == "no selector provided — expected 'triage [<selector>]'"


def test_selector_ranges_cve_and_retriage(capsys, tmp_path):
    _, out = selector(capsys, tmp_path, "triage #210-#213, 220 --no-preflight")
    assert out["issue_numbers"] == [210, 211, 212, 213, 220] and out["no_preflight"] is True
    _, out = selector(capsys, tmp_path, "triage CVE-2026-12345 --retriage")
    assert out["action"] == "cve_search" and out["retriage"] is True
    assert out["command"].startswith(
        'gh search issues "CVE-2026-12345" --repo example-s/example-s --match body'
    )
    _, out = selector(capsys, tmp_path, "triage scope:providers --retriage")
    assert "needs triage" not in out["command"]
    code, out = selector(capsys, tmp_path, "triage other/repo#12")
    assert code == 2 and "not example-s/example-s" in out["error"]
    code, out = selector(capsys, tmp_path, "triage scope:chart", scope_labels=["airflow", "providers"])
    assert code == 2


def test_queue_stop_cases_and_batches(capsys, tmp_path):
    sel = {"action": "list_query", "scope_label": None, "explicit": False, "retriage": False}
    _, out = run(
        capsys, tmp_path, "queue", {"selection": sel, "issues": [], "tracker": TRACKER, "scratch": "/s"}
    )
    assert out["stop"] == "empty"
    issues = [{"number": n, "updatedAt": f"2026-0{1 + n % 9}-01T00:00:00Z"} for n in range(1, 1001)]
    _, out = run(
        capsys, tmp_path, "queue", {"selection": sel, "issues": issues, "tracker": TRACKER, "scratch": "/s"}
    )
    assert out["stop"] == "limit" and out["batches"] == []
    _, out = run(
        capsys,
        tmp_path,
        "queue",
        {"selection": sel, "issues": issues[:45], "tracker": TRACKER, "scratch": "/s"},
    )
    assert out["stop"] is None
    assert [b["numbers"][0] for b in out["batches"]] == [1, 21, 41]
    assert out["batches"][0]["command"] == "gh api graphql -F query=@/s/triage-batch-1.graphql"
    assert 'repository(owner: "example-s", name: "example-s")' in out["batches"][0]["query"]
    assert "i20: issue(number: 20)" in out["batches"][0]["query"]
    cve = {"action": "cve_search", "cve_token": "CVE-2026-1234", "retriage": True}
    _, out = run(capsys, tmp_path, "queue", {"selection": cve, "cve_matches": [3, 4], "tracker": TRACKER})
    assert out["stop"] == "ask"
    many = {"action": "verbatim", "issue_numbers": list(range(1, 52)), "retriage": True, "explicit": True}
    _, out = run(capsys, tmp_path, "queue", {"selection": many, "tracker": TRACKER, "scratch": "/s"})
    assert out["stop"] == "confirm"
    _, out = run(
        capsys, tmp_path, "queue", {"selection": many, "tracker": TRACKER, "scratch": "/s", "confirmed": True}
    )
    assert out["stop"] is None and len(out["batches"]) == 3


# --- pre-flight skip --------------------------------------------------------

PROPOSAL = "**Triage proposal**\n\nSummary.\n\n**Proposed disposition: INVALID.**\n\nSeverity: low-ish.\n"


def tracker(number: int, *, author="alice", body_first=PROPOSAL, updated="2026-10-01T10:00:30Z", thread=None):
    mailing = (
        f"No public archive URL — tracked privately on Gmail thread `{thread}`."
        if thread
        else "_No response_"
    )
    return {
        "number": number,
        "updatedAt": updated,
        "body": f"### The issue description\n\nx\n\n### Security mailing list thread\n\n{mailing}\n",
        "comments": {
            "nodes": [
                {"author": {"login": "reporter"}, "createdAt": "2026-09-30T10:00:00Z", "body": "hi"},
                {"author": {"login": author}, "createdAt": "2026-10-01T10:00:00Z", "body": body_first},
            ]
        },
    }


def test_preflight_skips_only_when_all_four_rules_hold(capsys, tmp_path):
    data: dict[str, Any] = {
        "trackers": [
            tracker(1),
            tracker(2, author="mallory"),
            tracker(3, updated="2026-10-01T10:05:00Z"),
            tracker(4, body_first="**Triage proposal** looks like one\n"),
            tracker(5, thread="18f3a2b9c1d4e507"),
        ],
        "roster": ROSTER,
    }
    _, out = run(capsys, tmp_path, "preflight", data)
    assert [s["number"] for s in out["skipped"]] == [1]
    assert out["skipped"][0]["proposed_class"] == "INVALID"
    assert out["kept"] == [2, 3, 4]
    assert out["mail_checks"] == [{"number": 5, "thread_id": "18f3a2b9c1d4e507"}]
    data["mail"] = {"5": {"newest": "2026-10-02T00:00:00Z"}}
    _, out = run(capsys, tmp_path, "preflight", data)
    assert out["kept"] == [2, 3, 4, 5] and out["mail_checks"] == []
    data["mail"] = {"5": {"newest": "2026-09-30T00:00:00Z"}}
    _, out = run(capsys, tmp_path, "preflight", data)
    assert [s["number"] for s in out["skipped"]] == [1, 5]
    data["mail"] = {"5": {"error": True}}
    _, out = run(capsys, tmp_path, "preflight", data)
    assert 5 in out["kept"]


def test_preflight_is_disabled_by_flags_and_explicit_selectors(capsys, tmp_path):
    for flag, why in (
        ("retriage", "--retriage"),
        ("no_preflight", "--no-preflight"),
        ("explicit", "explicit selector"),
    ):
        _, out = run(capsys, tmp_path, "preflight", {"trackers": [tracker(1)], "roster": ROSTER, flag: True})
        assert out["disabled"] == why and out["kept"] == [1] and out["skipped"] == []
    _, out = run(
        capsys, tmp_path, "preflight", {"trackers": [tracker(1)], "roster": ROSTER, "explicit": True}
    )
    assert out["explicit_notes"] == [{"number": 1, "unanswered_proposal_since": "2026-10-01T10:00:00Z"}]


def test_preflight_reads_raw_responses_and_reports_null_aliases(capsys, tmp_path):
    response = {"data": {"repository": {"i1": tracker(1), "i99": None}}}
    _, out = run(capsys, tmp_path, "preflight", {"responses": [response], "roster": ROSTER})
    assert out["missing_numbers"] == ["99"] and out["all_skipped"] is True


# --- step-26-precedent-search (pinned; the suite stays a model eval) ---------


def test_step26_case_1_strong_rejection(capsys, tmp_path):
    data = {
        "tracker": TRACKER,
        "rejection_precedents": [
            {
                "number": 187,
                "closed_at": "2025-08-14T00:00:00Z",
                "match_strength": "STRONG",
                "one_line_shape": "dagrun.py — authenticated DoS",
            }
        ],
        "positive_precedents": [],
        "calls_used": 2,
    }
    _, out = run(capsys, tmp_path, "precedent-signal", data)
    assert out["disposition_signal"] == "lowers_to_invalid" and out["budget_exhausted"] is False
    assert out["citations"] == [
        "Direct precedent: [example-s/example-s#187](https://github.com/example-s/example-s/issues/187) "
        "(closed 2025-08-14 as INVALID, same shape: dagrun.py — authenticated DoS)."
    ]


def test_step26_case_2_positive_precedent(capsys, tmp_path):
    data = {
        "tracker": TRACKER,
        "positive_precedents": [{"number": 201, "match_strength": "STRONG"}],
        "calls_used": 3,
    }
    _, out = run(capsys, tmp_path, "precedent-signal", data)
    assert out["disposition_signal"] == "raises_to_valid" and out["budget_exhausted"] is True


def test_step26_case_3_no_match(capsys, tmp_path):
    data = {
        "tracker": TRACKER,
        "rejection_precedents": [{"number": 155, "match_strength": "MODERATE"}],
        "calls_used": 2,
    }
    _, out = run(capsys, tmp_path, "precedent-signal", data)
    assert out["disposition_signal"] == "neutral" and out["citations"] == []


# --- routing and the proposal ------------------------------------------------


def test_mentions_priorities_cap_and_fallback(capsys, tmp_path):
    base = {"roster": ROSTER, "viewer": "carol"}
    _, out = run(
        capsys,
        tmp_path,
        "mentions",
        {**base, "pr_authors": ["mallory", "alice"], "reviewers": ["carol", "bob"]},
    )
    assert out["handles"] == ["@alice", "@bob"] and out["routing_fallback"] is False
    assert {d["handle"] for d in out["dropped"]} == {"mallory", "carol"}
    _, out = run(
        capsys,
        tmp_path,
        "mentions",
        {
            **base,
            "pr_authors": ["alice"],
            "reviewers": ["bob"],
            "topic_owners": ["dave", "alice"],
            "scope_default": ["bob"],
        },
    )
    assert out["handles"] == ["@alice", "@bob", "@dave"]
    _, out = run(capsys, tmp_path, "mentions", {**base, "scope_default": ["dave", "bob"], "pointer": "x.py"})
    assert out["handles"] == ["@dave"] and out["routing_fallback"] is True
    assert "no PR-history match for `x.py`" in out["fallback_note"]
    code, _ = run(capsys, tmp_path, "mentions", {"roster": []})
    assert code == 2


def proposal(**extra: Any) -> dict[str, Any]:
    return {
        "tracker": TRACKER,
        "number": 212,
        "class": "VALID",
        "summary": "The header leaks; see #198.",
        "severity": "my read is Medium-ish, team-scoring expected",
        "open_question": "whether log access is DAG-scoped",
        "fix_shape": "Redact the header before the log write.",
        "handles": ["@alice", "@bob"],
        "question": "does apache/airflow#39100 cover this fully",
        "roster": ROSTER,
        "viewer": "carol",
        "scratch": "/s",
        **extra,
    }


def test_render_proposal_shape_links_and_command(capsys, tmp_path):
    code, out = run(capsys, tmp_path, "render-proposal", proposal())
    assert code == 0
    text = out["text"]
    assert text.startswith("**Triage proposal**\n\n")
    assert "**Proposed disposition: VALID.**" in text
    assert "Final scoring per the team after assessing whether log access is DAG-scoped." in text
    assert "[#198](https://github.com/example-s/example-s/issues/198)" in text
    assert "[apache/airflow#39100](https://github.com/apache/airflow/issues/39100)" in text
    assert text.rstrip().endswith(
        "@alice @bob — does [apache/airflow#39100](https://github.com/apache/airflow/issues/39100) cover this fully?"
    )
    assert out["command"] == "gh issue comment 212 --repo example-s/example-s --body-file /s/triage-212.md"


@pytest.mark.parametrize(
    ("extra", "why"),
    [
        ({"class": "MAYBE"}, "class must be one of"),
        ({"severity": "CVSS 7.5 HIGH"}, "never a CVSS score"),
        ({"handles": ["@alice", "@bob", "@dave", "@carol"]}, "the cap is 3"),
        ({"handles": ["@mallory"]}, "off the roster"),
        ({"handles": ["@carol"]}, "off the roster, or the triager"),
        (
            {"class": "INFO-ONLY", "canned_heading": "Made up", "canned_headings": ["Real one"]},
            "exact heading",
        ),
        ({"class": "PROBABLE-DUP"}, "kept tracker"),
        ({"class": "FIX-ALREADY-PUBLIC"}, "FIX-ALREADY-PUBLIC"),
    ],
)
def test_render_proposal_refuses(capsys, tmp_path, extra, why):
    code, out = run(capsys, tmp_path, "render-proposal", proposal(**extra))
    assert code == 2 and why in out["refused"]


def test_render_proposal_class_additions(capsys, tmp_path):
    _, out = run(capsys, tmp_path, "render-proposal", proposal(**{"class": "DEFENSE-IN-DEPTH"}))
    assert "Defense-in-depth fix is welcome via public PR; not a CVE." in out["text"]
    _, out = run(
        capsys, tmp_path, "render-proposal", proposal(**{"class": "UNCERTAIN", "tentative_class": "INVALID"})
    )
    assert out["text"].index("**Low-confidence proposal, please challenge.**") < out["text"].index(
        "**Proposed disposition: INVALID.**"
    )
    _, out = run(
        capsys, tmp_path, "render-proposal", proposal(**{"class": "PROBABLE-DUP", "kept_tracker": 198})
    )
    assert "`security-issue-deduplicate 212 198`" in out["text"]
    prs = [{"number": 39100, "author": "dev1", "state": "MERGED", "date": "2026-09-01T00:00:00Z"}]
    data = proposal(**{"class": "FIX-ALREADY-PUBLIC", "upstream": "apache/airflow", "prs": prs})
    _, out = run(capsys, tmp_path, "render-proposal", data)
    assert "> Thanks for the report. We noticed that" in out["text"]
    assert "([`dev1`](https://github.com/dev1), merged 2026-09-01)" in out["text"]
    assert "we do not credit a finder" in out["text"]


# --- step-6-body-scrub (cases 1 and 2; case 3, injection, stays a model eval)


def test_step6_case_1_bare_name_replacement(capsys, tmp_path):
    body = "**Triage proposal**\n\nAlice Smith, Bob Chen — does the log-redaction approach in apache/airflow#39100 cover this?\n"
    _, out = run(
        capsys,
        tmp_path,
        "scrub",
        {"text": body, "names": {"Alice Smith": "@alice", "Bob Chen": "@bob"}, "tracker": TRACKER},
    )
    assert out["replacements_made"] == [
        {"bare_name": "Alice Smith", "handle": "@alice", "count": 1},
        {"bare_name": "Bob Chen", "handle": "@bob", "count": 1},
    ]
    assert "@alice, @bob — " in out["text"]
    assert "[apache/airflow#39100](https://github.com/apache/airflow/issues/39100)" in out["text"]


def test_step6_case_2_clean_body(capsys, tmp_path):
    body = "**Triage proposal**\n\n@bob — does the canned response need any inline augmentation?\n"
    _, out = run(
        capsys,
        tmp_path,
        "scrub",
        {"text": body, "names": {"Alice Smith": "@alice", "Bob Chen": "@bob"}, "tracker": TRACKER},
    )
    assert out["replacements_made"] == [] and out["text"] == body


def test_scrub_leaves_code_and_urls_and_rewrites_link_text(capsys, tmp_path):
    body = "`Alice Smith` and https://x.example/Alice Smith and [Alice Smith](https://x.example)\n"
    _, out = run(
        capsys, tmp_path, "scrub", {"text": body, "names": {"Alice Smith": "alice"}, "tracker": TRACKER}
    )
    assert out["text"] == "`Alice Smith` and https://x.example/Alice Smith and @alice\n"


# --- step-5-confirm ----------------------------------------------------------


def reply(capsys, tmp_path, text: str, items: list[int], **extra: Any) -> dict[str, Any]:
    _, out = run(capsys, tmp_path, "parse-reply", {"reply": text, "items": items, **extra})
    return out


def plan(out: dict[str, Any]) -> dict[str, Any]:
    return {
        k: out[k]
        for k in ("action", "post_items", "skip_items", "edits", "reclassifications", "ambiguous_tokens")
    }


def test_step5_case_1_post_all(capsys, tmp_path):
    assert plan(reply(capsys, tmp_path, "all", [1, 2, 3])) == {
        "action": "post",
        "post_items": [1, 2, 3],
        "skip_items": [],
        "edits": [],
        "reclassifications": [],
        "ambiguous_tokens": [],
    }


def test_step5_case_2_selective_skip(capsys, tmp_path):
    assert plan(reply(capsys, tmp_path, "1,3 2:skip 4:skip", [1, 2, 3, 4])) == {
        "action": "post",
        "post_items": [1, 3],
        "skip_items": [2, 4],
        "edits": [],
        "reclassifications": [],
        "ambiguous_tokens": [],
    }


def test_step5_case_3_edit_and_downgrade(capsys, tmp_path):
    out = reply(capsys, tmp_path, "all 2:edit swap @alice to @bob 3:downgrade DEFENSE-IN-DEPTH", [1, 2, 3])
    assert plan(out) == {
        "action": "post",
        "post_items": [1, 2, 3],
        "skip_items": [],
        "edits": [{"item": 2, "instruction": "swap @alice to @bob"}],
        "reclassifications": [{"item": 3, "new_class": "DEFENSE-IN-DEPTH"}],
        "ambiguous_tokens": [],
    }
    assert out["post_now"] == [1] and out["redraft_items"] == [2, 3]


def test_step5_case_4_cancel(capsys, tmp_path):
    assert plan(reply(capsys, tmp_path, "cancel", [1, 2])) == {
        "action": "cancel",
        "post_items": [],
        "skip_items": [],
        "edits": [],
        "reclassifications": [],
        "ambiguous_tokens": [],
    }


@pytest.mark.parametrize(
    "text", ["2:skip", "post them", "1,9", "1 1:skip", "don't post 2", "3:downgrade MAYBE"]
)
def test_reply_ambiguity_posts_nothing(capsys, tmp_path, text):
    out = reply(capsys, tmp_path, text, [1, 2, 3])
    assert out["action"] == "ambiguous" and out["post_items"] == [] and out["ambiguous_tokens"]


def test_reply_force_triage(capsys, tmp_path):
    out = reply(capsys, tmp_path, "1 force-triage 240", [1], skipped_trackers=[240])
    assert out["force_triage"] == [240] and out["post_items"] == [1]
    out = reply(capsys, tmp_path, "force-triage 241", [1], skipped_trackers=[240])
    assert out["action"] == "ambiguous"


# --- step-7-recap ------------------------------------------------------------


def url(n: int, c: int) -> str:
    return f"https://github.com/example-s/example-s/issues/{n}#issuecomment-{c}"


def zero(**counts: int) -> dict[str, int]:
    base = {
        "VALID": 0,
        "DEFENSE_IN_DEPTH": 0,
        "INFO_ONLY": 0,
        "INVALID": 0,
        "PROBABLE_DUP": 0,
        "FIX_ALREADY_PUBLIC": 0,
    }
    return {**base, **counts}


def recap(capsys, tmp_path, posted: list[dict[str, Any]], **extra: Any) -> dict[str, Any]:
    _, out = run(capsys, tmp_path, "render-recap", {"tracker": TRACKER, "posted": posted, **extra})
    return out


def test_step7_case_1_mixed_dispositions(capsys, tmp_path):
    out = recap(
        capsys,
        tmp_path,
        [
            {"number": 212, "class": "VALID", "comment_url": url(212, 1001)},
            {"number": 215, "class": "INVALID", "comment_url": url(215, 1002)},
            {"number": 218, "class": "INFO-ONLY", "comment_url": url(218, 1003)},
            {"number": 220, "class": "PROBABLE-DUP", "kept": 212, "comment_url": url(220, 1004)},
        ],
    )
    assert out["distribution"] == zero(VALID=1, INFO_ONLY=1, INVALID=1, PROBABLE_DUP=1)
    assert out["next_steps"] == [
        "/security-cve-allocate 212",
        "/security-issue-invalidate 215",
        "/security-issue-invalidate 218",
        "/security-issue-deduplicate 220 212",
    ]
    assert [t["comment_url"] for t in out["trackers"]] == [
        url(212, 1001),
        url(215, 1002),
        url(218, 1003),
        url(220, 1004),
    ]
    assert out["sync_note"] is True and out["bare_refs"] == []


def test_step7_case_2_all_valid(capsys, tmp_path):
    posted = [
        {"number": n, "class": "VALID", "comment_url": url(n, c)}
        for n, c in ((231, 2001), (232, 2002), (235, 2003))
    ]
    out = recap(capsys, tmp_path, posted)
    assert out["distribution"] == zero(VALID=3)
    assert out["trackers"] == [
        {"number": p["number"], "class": "VALID", "comment_url": p["comment_url"]} for p in posted
    ]
    assert out["next_steps"] == [
        "/security-cve-allocate 231",
        "/security-cve-allocate 232",
        "/security-cve-allocate 235",
    ]


def test_step7_case_3_no_valid(capsys, tmp_path):
    posted = [
        {"number": 241, "class": "INVALID", "comment_url": url(241, 3001)},
        {"number": 242, "class": "DEFENSE-IN-DEPTH", "comment_url": url(242, 3002)},
        {"number": 244, "class": "INVALID", "comment_url": url(244, 3003)},
    ]
    out = recap(capsys, tmp_path, posted)
    assert out["distribution"] == zero(DEFENSE_IN_DEPTH=1, INVALID=2)
    assert out["next_steps"] == ["/security-issue-invalidate 241", "/security-issue-invalidate 244"]


def test_recap_fix_public_note_and_skipped_group(capsys, tmp_path):
    out = recap(
        capsys,
        tmp_path,
        [{"number": 250, "class": "FIX-ALREADY-PUBLIC", "comment_url": url(250, 1)}],
        skipped=[
            {"number": 251, "proposal_date": "2026-10-01T10:00:00Z", "proposed_class": "INVALID", "rule": "r"}
        ],
    )
    assert out["next_step_notes"][0]["note"].startswith("only after the reporter confirms")
    assert "**Pre-flight skipped (awaiting reaction):**" in out["text"]
    assert "[example-s/example-s#251](https://github.com/example-s/example-s/issues/251)" in out["text"]
