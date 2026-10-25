# SPDX-License-Identifier: Apache-2.0
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

import io
import json
import urllib.error
import urllib.request
from email.message import Message
from pathlib import Path
from typing import Any

import pytest

from magpie_asf_security_dash import cases, client
from magpie_asf_security_dash import main as package_main
from magpie_asf_security_dash.client import DashError, SessionExpired


def case(mid: str, state: str = "untriaged", cves: list[str] | None = None) -> dict[str, Any]:
    return {
        "message_id": f"<{mid}>",
        "state": state,
        "cves": cves or [],
        "title": f"report {mid}",
        "date": "2026-10-01",
        "asf_member_link": f"https://lists.apache.org/thread/{mid}",
    }


def issue(issue_id: str, mids: list[str] | None = None, **kw: Any) -> dict[str, Any]:
    return {
        "id": issue_id,
        "url": f"https://example.test/{issue_id}",
        "message_ids": [f"<{m}>" for m in (mids or [])],
        **kw,
    }


def kinds(result: dict[str, Any]) -> list[str]:
    return [f["kind"] for f in result["findings"]]


# --- normalise ---------------------------------------------------------------------


def test_normalise_strips_brackets_and_derives_the_stage() -> None:
    [c] = cases.normalise([case("a@x", "cve-allocation", ["cve-2026-1"])])
    assert c["message_id"] == "a@x"
    assert c["cves"] == ["CVE-2026-1"]
    assert c["stage"] == "accepted"
    assert c["thread"] == "https://lists.apache.org/thread/a@x"


@pytest.mark.parametrize(
    ("state", "stage"),
    [
        ("untriaged", "untriaged"),
        ("confirmed", "accepted"),
        ("disclosure", "accepted"),
        ("non-issue-docs", "rejected"),
        ("non-issue-feedback", "rejected"),
        ("vendor-reply", "other"),
    ],
)
def test_stage_of_each_dashboard_state(state: str, stage: str) -> None:
    assert cases.stage(state) == stage


def test_a_case_without_message_id_is_an_error() -> None:
    with pytest.raises(DashError, match="message_id"):
        cases.normalise([{"state": "untriaged"}])


# --- reconcile ---------------------------------------------------------------------


def run(dash: list[dict[str, Any]], tracker: list[dict[str, Any]]) -> dict[str, Any]:
    return cases.reconcile("foo", cases.normalise(dash), tracker)


def test_an_untagged_untriaged_case_with_no_issue_is_reviewed_not_imported() -> None:
    """Without its tag it may be one of the security team's standing labels."""
    result = run([case("a@x")], [])
    assert kinds(result) == ["untracked"]
    assert result["findings"][0]["fix"] == "review"
    assert "standing labels" in result["findings"][0]["detail"]


def test_a_tagged_report_with_no_issue_is_imported() -> None:
    result = run([{**case("a@x"), "tag": "2026-10-01 upload traversal"}], [])
    assert result["findings"][0]["fix"] == "import"


def test_an_accepted_case_with_no_issue_is_imported_even_without_a_tag() -> None:
    result = run([case("a@x", "confirmed", ["CVE-2026-1"])], [])
    assert result["findings"][0]["fix"] == "import"


@pytest.mark.parametrize(
    "entry",
    [
        {**case("a@x"), "tag": "aaa-support"},
        {**case("a@x"), "tag": "zzz-admin"},
        case("a@x", "glasswing", ["CVE-2026-9"]),
        case("a@x", "non-fwd"),
    ],
    ids=["aaa-label", "zzz-label", "glasswing", "not-forwarded"],
)
def test_standing_label_entries_are_skipped(entry: dict[str, Any]) -> None:
    result = run([entry], [])
    assert result["findings"] == []
    assert result["labels_skipped"] == 1


def test_agreeing_sides_produce_no_finding() -> None:
    result = run(
        [case("a@x", "confirmed", ["CVE-2026-1"])],
        [issue("1", ["a@x"], decision="accepted", cves=["CVE-2026-1"])],
    )
    assert result["findings"] == []
    assert result["paired"] == 1


def test_pairs_by_message_id_ignoring_brackets() -> None:
    tracker = [{"id": "1", "message_ids": ["a@x"], "decision": "undecided"}]
    assert run([case("a@x")], tracker)["findings"] == []


def test_falls_back_to_a_shared_cve() -> None:
    result = run(
        [case("a@x", "confirmed", ["CVE-2026-1"])], [issue("1", decision="accepted", cves=["CVE-2026-1"])]
    )
    assert result["paired"] == 1 and result["findings"] == []


def test_two_issues_for_one_case_are_ambiguous() -> None:
    result = run(
        [case("a@x", "confirmed", ["CVE-2026-1", "CVE-2026-2"])],
        [issue("1", cves=["CVE-2026-1"]), issue("2", cves=["CVE-2026-2"])],
    )
    assert kinds(result) == ["ambiguous"]


def test_cve_differences_name_who_fixes_them() -> None:
    result = run(
        [case("a@x", "confirmed", ["CVE-2026-1"])],
        [issue("1", ["a@x"], decision="accepted", cves=["CVE-2026-2"])],
    )
    assert {f["kind"]: f["fix"] for f in result["findings"]} == {
        "cve-missing-in-tracker": "tracker",
        "cve-missing-on-dashboard": "asf-security",
    }


def test_decided_in_tracker_but_untriaged_on_dashboard() -> None:
    result = run([case("a@x")], [issue("1", ["a@x"], decision="rejected")])
    [finding] = result["findings"]
    assert finding["kind"] == "triage-on-dashboard"
    assert finding["fix"] == "dashboard-triage"
    assert "https://dash.security.apache.org/project/foo" in finding["detail"]
    assert "emails the reporter" in finding["detail"]


def test_opposite_decisions_conflict() -> None:
    result = run([case("a@x", "non-issue-docs")], [issue("1", ["a@x"], decision="accepted")])
    assert kinds(result) == ["decision-conflict"]


def test_closed_in_tracker_but_open_on_dashboard() -> None:
    result = run([case("a@x", "confirmed")], [issue("1", ["a@x"], state="closed", decision="accepted")])
    assert kinds(result) == ["closed-in-tracker"]


def test_closed_as_rejected_but_untriaged_on_dashboard_is_triaged_there() -> None:
    """Triage clears the case, so no separate note to the security team."""
    result = run([case("a@x")], [issue("1", ["a@x"], state="closed", decision="rejected")])
    assert kinds(result) == ["triage-on-dashboard"]


def test_a_closed_issue_still_shows_a_decision_conflict() -> None:
    result = run([case("a@x", "non-issue-docs")], [issue("1", ["a@x"], state="closed", decision="accepted")])
    assert kinds(result) == ["decision-conflict", "closed-in-tracker"]


@pytest.mark.parametrize("state", ["cve-allocation", "non-issue-feedback"])
def test_a_dashboard_decision_with_an_undecided_issue(state: str) -> None:
    result = run([case("a@x", state)], [issue("1", ["a@x"], decision="undecided")])
    assert kinds(result) == ["decision-missing-in-tracker"]
    assert result["findings"][0]["fix"] == "tracker"


def test_ambiguous_candidates_are_not_reported_missing() -> None:
    result = run([case("a@x")], [issue("1", ["a@x"]), issue("2", ["a@x"])])
    assert kinds(result) == ["ambiguous"]


def test_disclosure_pending_is_reported() -> None:
    result = run(
        [case("a@x", "disclosure", ["CVE-2026-1"])],
        [issue("1", ["a@x"], decision="accepted", cves=["CVE-2026-1"])],
    )
    assert kinds(result) == ["disclosure-pending"]


def test_open_issue_missing_from_the_dashboard() -> None:
    result = run([], [issue("1", ["a@x"], decision="accepted")])
    assert kinds(result) == ["not-on-dashboard"]
    assert result["findings"][0]["fix"] == "asf-security"


@pytest.mark.parametrize(
    "tracked",
    [issue("1", ["a@x"], state="closed"), issue("1", ["a@x"], decision="rejected"), issue("1")],
    ids=["closed", "rejected", "no-thread"],
)
def test_issues_the_dashboard_need_not_list(tracked: dict[str, Any]) -> None:
    assert run([], [tracked])["findings"] == []


@pytest.mark.parametrize(
    ("bad", "message"),
    [
        ({"message_ids": []}, "no id"),
        ({"id": "1", "state": "merged"}, "state"),
        ({"id": "1", "decision": "maybe"}, "decision"),
    ],
)
def test_malformed_tracker_issues_are_refused(bad: dict[str, Any], message: str) -> None:
    with pytest.raises(DashError, match=message):
        run([], [bad])


# --- client ------------------------------------------------------------------------


class FakeResponse(io.BytesIO):
    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


def serve(monkeypatch: pytest.MonkeyPatch, reply: Any, status: int = 200) -> list[urllib.request.Request]:
    seen: list[urllib.request.Request] = []

    def fake_open(request: urllib.request.Request, timeout: float) -> FakeResponse:
        seen.append(request)
        if status != 200:
            raise urllib.error.HTTPError(request.full_url, status, "status", Message(), None)
        body = reply if isinstance(reply, bytes) else json.dumps(reply).encode()
        return FakeResponse(body)

    monkeypatch.setattr(client, "_open", fake_open)
    return seen


def test_fetch_sends_a_get_with_the_cookie_to_the_dashboard(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = serve(monkeypatch, [case("a@x")])
    assert client.fetch_reports("foo", "session=abc")[0]["message_id"] == "<a@x>"
    [request] = seen
    assert request.full_url == "https://dash.security.apache.org/api/project/foo/reports"
    assert request.get_method() == "GET"
    assert request.get_header("Cookie") == "session=abc"


@pytest.mark.parametrize("status", [302, 401])
def test_a_login_redirect_or_401_means_the_session_expired(
    monkeypatch: pytest.MonkeyPatch, status: int
) -> None:
    serve(monkeypatch, None, status)
    with pytest.raises(SessionExpired):
        client.fetch_reports("foo", "session=abc")


def test_403_names_the_pmc(monkeypatch: pytest.MonkeyPatch) -> None:
    serve(monkeypatch, None, 403)
    with pytest.raises(DashError, match="not authorized for foo"):
        client.fetch_reports("foo", "session=abc")


def test_an_html_answer_is_treated_as_an_expired_session(monkeypatch: pytest.MonkeyPatch) -> None:
    serve(monkeypatch, b"<html>login</html>")
    with pytest.raises(SessionExpired):
        client.fetch_reports("foo", "session=abc")


@pytest.mark.parametrize("pmc", ["Foo", "../foo", "foo/bar", "", "-foo", "foo-bar"])
def test_pmc_ids_are_validated_before_any_request(pmc: str) -> None:
    with pytest.raises(DashError, match="not a PMC id"):
        client.check_pmc(pmc)


def test_redirects_are_never_followed() -> None:
    assert client._NoRedirect().redirect_request() is None


def test_load_cookie(tmp_path: Path) -> None:
    path = tmp_path / "session.json"
    with pytest.raises(SessionExpired, match="no dashboard session"):
        client.load_cookie(path)
    path.write_text(json.dumps({"cookie": "a=b\r\nX-Evil: 1"}))
    with pytest.raises(DashError, match="must hold"):
        client.load_cookie(path)
    path.write_text(json.dumps({"cookie": " a=b "}))
    assert client.load_cookie(path) == "a=b"


def test_the_session_path_follows_the_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv(client.SESSION_ENV, str(tmp_path / "s.json"))
    assert client.session_file() == tmp_path / "s.json"


# --- cli ---------------------------------------------------------------------------


@pytest.fixture
def asf_project(tmp_path: Path) -> str:
    """A project.md that declares the ASF, as every bridge run needs."""
    path = tmp_path / "project.md"
    path.write_text("| Key | Value |\n|---|---|\n| `organization` | `ASF` |\n")
    return str(path)


def test_cases_from_saved_input(tmp_path: Path, capsys: pytest.CaptureFixture[str], asf_project: str) -> None:
    saved = tmp_path / "reports.json"
    saved.write_text(json.dumps([case("a@x")]))
    assert package_main(["cases", "--pmc", "foo", "--project-md", asf_project, "--input", str(saved)]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["pmc"] == "foo" and out["cases"][0]["message_id"] == "a@x"


def test_reconcile_from_saved_input(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], asf_project: str
) -> None:
    saved = tmp_path / "reports.json"
    saved.write_text(json.dumps([case("a@x")]))
    tracker = tmp_path / "issues.json"
    tracker.write_text(json.dumps([issue("1", ["a@x"], decision="accepted")]))
    assert (
        package_main(
            [
                "reconcile",
                "--pmc",
                "foo",
                "--project-md",
                asf_project,
                "--input",
                str(saved),
                "--tracker",
                str(tracker),
            ]
        )
        == 0
    )
    assert kinds(json.loads(capsys.readouterr().out)) == ["triage-on-dashboard"]


def test_errors_exit_1_with_a_message(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], asf_project: str
) -> None:
    tracker = tmp_path / "issues.json"
    tracker.write_text("{}")
    saved = tmp_path / "reports.json"
    saved.write_text("[]")
    assert (
        package_main(
            [
                "reconcile",
                "--pmc",
                "foo",
                "--project-md",
                asf_project,
                "--input",
                str(saved),
                "--tracker",
                str(tracker),
            ]
        )
        == 1
    )
    assert "JSON list" in capsys.readouterr().err


@pytest.mark.parametrize(
    "text",
    [
        "| `organization` | `independent` |\n",
        "| `organization` | TODO: the organization whose defaults this project inherits |\n",
        "organization: acme\n",
        "no organization at all\n",
        "```\norganization: ASF\n```\n",
        "<!--\n| `organization` | `ASF` |\n-->\n| `organization` | `independent` |\n",
        "<!-- organization: ASF -->\n",
        "| `organization` | `ASF.example` |\n",
        "| `organization` | ASFX |\n",
        "organization: ASF-fork\n",
        "organization: ASF extra\n",
    ],
)
def test_a_project_that_is_not_asf_is_refused_before_anything_is_read(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, text: str
) -> None:
    """The dashboard lists ASF PMCs only: no cookie read, no request, exit 3."""
    project = tmp_path / "project.md"
    project.write_text(text)

    def boom(*a: object, **kw: object) -> None:
        raise AssertionError("must not touch the session or the network")

    monkeypatch.setattr("magpie_asf_security_dash.cli.load_cookie", boom)
    monkeypatch.setattr("magpie_asf_security_dash.cli.fetch_reports", boom)
    assert package_main(["cases", "--pmc", "foo", "--project-md", str(project)]) == 3
    assert "ASF projects only" in capsys.readouterr().err


@pytest.mark.parametrize(
    "text",
    [
        "| `organization` | `ASF` |\n",
        "| `organization` | `ASF` (derived: apache/ GitHub org) |\n",
        "organization: ASF\n",
        "organization: `ASF`\n",
        "organization: `ASF` (from .asf.yaml)\n",
    ],
)
def test_an_asf_project_md_is_recognised(text: str) -> None:
    from magpie_asf_security_dash.organization import organization

    assert organization(text) == "ASF"


def test_the_project_md_flag_is_required() -> None:
    with pytest.raises(SystemExit) as excinfo:
        package_main(["cases", "--pmc", "foo"])
    assert excinfo.value.code == 2
