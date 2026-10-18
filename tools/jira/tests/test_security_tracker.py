# SPDX-License-Identifier: Apache-2.0
# https://www.apache.org/licenses/LICENSE-2.0

from __future__ import annotations

import base64
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from jira_bridge import markup
from jira_bridge.rest import authorization_header
from jira_bridge.security_tracker import expand_id, jql_quote
from jira_bridge.tracker_client import UsageError

from .conftest import BASE, ENV, Call, FakeJira, Result, issue

Run = Callable[..., Result]
ISSUE = "/rest/api/2/issue/FOOSEC-12"


def write(tmp_path: Path, name: str, text: str) -> str:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return str(path)


# -- ids and auth ------------------------------------------------------------


def test_expand_id() -> None:
    assert expand_id("12", "FOOSEC") == "FOOSEC-12"
    assert expand_id("FOOSEC-7", "FOOSEC") == "FOOSEC-7"
    assert expand_id("foosec-7", "FOOSEC") == "FOOSEC-7"
    for bad in ("FOO SEC-1", "-1", "FOOSEC-", "1FOO-2", "FOOSEC-1; drop"):
        with pytest.raises(UsageError):
            expand_id(bad, "FOOSEC")
    with pytest.raises(UsageError):
        expand_id("OTHER-1", "FOOSEC")
    with pytest.raises(UsageError):
        expand_id("12", "")


def test_invalid_id_is_usage_error_without_network(run: Run, fake: FakeJira) -> None:
    result = run("view", "not an id")
    assert result.code == 2
    assert fake.calls == []


def test_authorization_header() -> None:
    assert authorization_header("pat", "Bearer", "bob") == "Bearer pat"
    encoded = base64.b64encode(b"bob:secret").decode()
    assert authorization_header(encoded, "Basic", "bob") == f"Basic {encoded}"
    assert (
        authorization_header("raw", "Basic", "bob")
        == "Basic " + base64.b64encode(b"bob:raw").decode()
    )


def test_the_test_transport_never_carries_credentials(run: Run, fake: FakeJira) -> None:
    """Auth is JiraRest's job alone (see test_rest.py); the client adds none of its own."""
    fake.on("GET", ISSUE, (200, issue()))
    run("view", "12")
    assert "Authorization" not in fake.calls[0].headers


# -- view / list / labels ----------------------------------------------------


def test_view_shape(run: Run, fake: FakeJira) -> None:
    fake.on(
        "GET",
        ISSUE,
        (
            200,
            issue(
                assignee={"name": "carol"},
                fixVersions=[{"name": "2.10.2"}, {"name": "3.0.0"}],
                description="h3. CWE\nCWE-22",
            ),
        ),
    )
    result = run("view", "FOOSEC-12")
    assert result.code == 0
    data = result.json()
    assert data == {
        "id": "FOOSEC-12",
        "title": "Path traversal",
        "state": "open",
        "labels": ["needs-triage"],
        "assignees": ["carol"],
        "milestone": "2.10.2",
        "author": "alice",
        "created": "2026-10-01T10:00:00.000+0000",
        "updated": "2026-10-02T10:00:00.000+0000",
        "body": "h3. CWE\nCWE-22",
        "url": f"{BASE}/browse/FOOSEC-12",
        "security_level": "Security Team",
        "warnings": [],
    }
    assert "comment" not in fake.calls[0].query["fields"]


@pytest.mark.parametrize(
    ("fields", "state"),
    [
        ({"resolution": {"name": "Fixed"}}, "closed"),
        ({"status": {"name": "Closed", "statusCategory": {"key": "done"}}}, "closed"),
        (
            {
                "status": {
                    "name": "In Progress",
                    "statusCategory": {"key": "indeterminate"},
                }
            },
            "open",
        ),
    ],
)
def test_view_state_mapping(
    run: Run, fake: FakeJira, fields: dict[str, Any], state: str
) -> None:
    fake.on("GET", ISSUE, (200, issue(**fields)))
    assert run("view", "12").json()["state"] == state


def test_view_warns_without_security_level(run: Run, fake: FakeJira) -> None:
    fake.on("GET", ISSUE, (200, issue(secure=False)))
    data = run("view", "12").json()
    assert data["security_level"] is None
    assert "not access-restricted" in data["warnings"][0]


def test_view_with_comments(run: Run, fake: FakeJira) -> None:
    fake.on("GET", ISSUE, (200, issue()))
    fake.on(
        "GET",
        f"{ISSUE}/comment",
        (
            200,
            {
                "comments": [
                    {"id": "5", "author": {"name": "bob"}, "created": "x", "body": "hi"}
                ],
                "total": 1,
            },
        ),
    )
    data = run("view", "12", "--comments").json()
    assert data["comments"] == [
        {"id": "5", "author": "bob", "created": "x", "body": "hi"}
    ]


def test_view_not_found(run: Run, fake: FakeJira) -> None:
    result = run("view", "99")
    assert result.code == 3
    assert result.out == ""


def test_jql_quote_escapes() -> None:
    assert jql_quote('a "b" \\c') == '"a \\"b\\" \\\\c"'


def test_list_jql(run: Run, fake: FakeJira) -> None:
    fake.on(
        "GET",
        "/rest/api/2/search",
        (
            200,
            {"issues": [issue("FOOSEC-3", resolution={"name": "Fixed"})], "total": 1},
        ),
    )
    result = run(
        "list",
        "--state",
        "closed",
        "--label",
        "cve allocated",
        "--label",
        "x",
        "--search",
        'say "hi"\\',
    )
    assert result.code == 0
    query = fake.calls[0].query
    assert query["jql"] == (
        'project = "FOOSEC" AND (resolution is not EMPTY OR statusCategory = Done) AND labels = "cve allocated" AND labels = "x"'
        ' AND text ~ "say \\"hi\\"\\\\" ORDER BY updated DESC'
    )
    assert result.json() == [
        {
            "id": "FOOSEC-3",
            "title": "Path traversal",
            "state": "closed",
            "labels": ["needs-triage"],
            "updated": "2026-10-02T10:00:00.000+0000",
            "url": f"{BASE}/browse/FOOSEC-3",
        }
    ]


def test_list_defaults_open_and_limit(run: Run, fake: FakeJira) -> None:
    fake.on(
        "GET",
        "/rest/api/2/search",
        (200, {"issues": [issue(f"FOOSEC-{n}") for n in range(5)], "total": 50}),
    )
    result = run("list", "--limit", "3")
    assert len(result.json()) == 3
    assert (
        fake.calls[0].query["jql"]
        == 'project = "FOOSEC" AND resolution is EMPTY AND statusCategory != Done ORDER BY updated DESC'
    )
    assert fake.calls[0].query["maxResults"] == "3"


def test_list_all_states_on_cloud_uses_search_jql(run: Run, fake: FakeJira) -> None:
    fake.on(
        "GET", "/rest/api/2/search/jql", (200, {"issues": [issue()], "isLast": True})
    )
    result = run("list", "--state", "all", env={**ENV, "JIRA_DEPLOYMENT": "cloud"})
    assert result.code == 0
    assert fake.calls[0].query["jql"] == 'project = "FOOSEC" ORDER BY updated DESC'


def test_explicit_server_deployment_beats_inherited_env(run: Run, fake: FakeJira) -> None:
    fake.on("GET", "/rest/api/2/search", (200, {"issues": [issue()], "total": 1}))
    result = run(
        "list", "--state", "all", "--deployment", "server",
        env={**ENV, "JIRA_DEPLOYMENT": "cloud"},
    )
    assert result.code == 0
    assert fake.calls[0].path == "/rest/api/2/search"


def test_explicit_deployment_wins_over_jira_cloud_flag() -> None:
    from jira_bridge import security_tracker

    args = security_tracker.build_parser().parse_args(
        ["--jira-cloud", "--deployment", "server", "pending"]
    )
    assert security_tracker.resolve_config(args, {"JIRA_DEPLOYMENT": "cloud"}).cloud is False
    args = security_tracker.build_parser().parse_args(["pending", "--deployment", "cloud"])
    assert security_tracker.resolve_config(args, {}).cloud is True


def test_labels_paginates(run: Run, fake: FakeJira) -> None:
    def page(call: Call) -> tuple[int, Any]:
        start = int(call.query["startAt"])
        if start == 0:
            issues = [issue(f"FOOSEC-{n}", labels=["b", f"l{n}"]) for n in range(100)]
        else:
            issues = [issue("FOOSEC-200", labels=["a", "b"])]
        return 200, {"issues": issues, "total": 101}

    fake.on("GET", "/rest/api/2/search", page)
    labels = run("labels").json()
    assert labels[:3] == ["a", "b", "l0"]
    assert len(labels) == 102
    assert [c.query["startAt"] for c in fake.calls] == ["0", "100"]


# -- body fields -------------------------------------------------------------


def test_field_get(run: Run, fake: FakeJira) -> None:
    fake.on("GET", ISSUE, (200, issue(description="h3. CWE\nCWE-22\n")))
    assert run("field-get", "12", "cwe").json() == {
        "id": "FOOSEC-12",
        "heading": "cwe",
        "value": "CWE-22",
    }


def test_field_get_markdown_and_missing(run: Run, fake: FakeJira) -> None:
    fake.on("GET", ISSUE, (200, issue(description="### Severity\n\nHigh\n")))
    assert run("field-get", "12", "severity").json()["value"] == "High"
    result = run("field-get", "12", "CWE")
    assert result.code == 0
    assert result.json()["value"] is None


def test_field_set_existing(run: Run, fake: FakeJira, tmp_path: Path) -> None:
    fake.on(
        "GET", ISSUE, (200, issue(description="h3. CWE\nold\n\nh3. Severity\nLow\n"))
    )
    fake.on("PUT", ISSUE, (204, None))
    result = run(
        "field-set", "12", "cwe", "--value-file", write(tmp_path, "v", "CWE-22\n")
    )
    assert result.json() == {"id": "FOOSEC-12", "heading": "cwe", "created": False}
    put = fake.writes()[0]
    assert put.json() == {
        "fields": {"description": "h3. CWE\nCWE-22\n\nh3. Severity\nLow\n"}
    }


def test_field_set_appends_missing(run: Run, fake: FakeJira, tmp_path: Path) -> None:
    fake.on("GET", ISSUE, (200, issue(description="Intro")))
    fake.on("PUT", ISSUE, (204, None))
    result = run(
        "field-set", "12", "CWE", "--value-file", write(tmp_path, "v", "CWE-22")
    )
    assert result.json()["created"] is True
    assert (
        fake.writes()[0].json()["fields"]["description"] == "Intro\n\nh3. CWE\nCWE-22\n"
    )


# -- create ------------------------------------------------------------------


def test_create_refuses_without_security_level(
    run: Run, fake: FakeJira, tmp_path: Path
) -> None:
    env = {k: v for k, v in ENV.items() if k != "SECURITY_TRACKER_SECURITY_LEVEL"}
    title = write(tmp_path, "t", "Title")
    body = write(tmp_path, "b", "Body")
    result = run("create", "--title-file", title, "--body-file", body, env=env)
    assert result.code == 4
    assert "security" in result.err
    assert fake.calls == []


def test_create_sets_security_level(run: Run, fake: FakeJira, tmp_path: Path) -> None:
    fake.on("POST", "/rest/api/2/issue", (201, {"id": "1000", "key": "FOOSEC-13"}))
    title = write(tmp_path, "t", "  Path traversal\n in upload  \n")
    body = write(tmp_path, "b", "h3. CWE\nCWE-22\n")
    result = run(
        "create",
        "--title-file",
        title,
        "--body-file",
        body,
        "--label",
        "needs-triage",
        "--issue-type",
        "Task",
    )
    assert result.json() == {"id": "FOOSEC-13", "url": f"{BASE}/browse/FOOSEC-13"}
    assert fake.calls[0].json() == {
        "fields": {
            "project": {"key": "FOOSEC"},
            "summary": "Path traversal in upload",
            "description": "h3. CWE\nCWE-22\n",
            "issuetype": {"name": "Task"},
            "security": {"name": "Security Team"},
            "labels": ["needs-triage"],
        }
    }


def test_create_flag_overrides_env_level(
    run: Run, fake: FakeJira, tmp_path: Path
) -> None:
    fake.on("POST", "/rest/api/2/issue", (201, {"key": "FOOSEC-14"}))
    title = write(tmp_path, "t", "T")
    body = write(tmp_path, "b", "B")
    run("--security-level", "PMC", "create", "--title-file", title, "--body-file", body)
    assert fake.calls[0].json()["fields"]["security"] == {"name": "PMC"}


# -- guard -------------------------------------------------------------------


def _write_invocations(tmp_path: Path) -> list[list[str]]:
    f = write(tmp_path, "f", "text")
    attachment = write(tmp_path, "poc.py", "print(1)")
    return [
        ["edit", "12", "--add-label", "x"],
        ["field-set", "12", "CWE", "--value-file", f],
        ["comment", "12", "--body-file", f],
        ["close", "12"],
        ["reopen", "12"],
        [
            "rollup-append",
            "12",
            "--action",
            "Sync",
            "--entry-body-file",
            f,
            "--user",
            "bob",
        ],
        ["rollup-amend-latest", "12", "--action", "Sync", "--entry-body-file", f],
        ["attach", "12", attachment],
    ]


def test_guard_refuses_every_write_on_unrestricted_issue(tmp_path: Path) -> None:
    from jira_bridge.security_tracker import main

    for argv in _write_invocations(tmp_path):
        fake = FakeJira().on(
            "GET", ISSUE, (200, issue(secure=False, resolution={"name": "Fixed"}))
        )
        assert main(argv, transport=fake, env=ENV) == 4, argv
        assert fake.writes() == [], argv
        assert all(c.path == ISSUE for c in fake.calls), argv


def test_guard_message(run: Run, fake: FakeJira, tmp_path: Path) -> None:
    fake.on("GET", ISSUE, (200, issue(secure=False)))
    result = run(
        "comment", "12", "--body-file", write(tmp_path, "f", "SECRET-POC-DETAILS")
    )
    assert result.code == 4
    assert "not access-restricted" in result.err
    assert "SECRET-POC-DETAILS" not in result.err


# -- edit / comment ----------------------------------------------------------


def test_edit_payload_server(run: Run, fake: FakeJira, tmp_path: Path) -> None:
    fake.on("GET", ISSUE, (200, issue()))
    fake.on("PUT", ISSUE, (204, None))
    result = run(
        "edit",
        "12",
        "--add-label",
        "cve-allocated",
        "--remove-label",
        "needs-triage",
        "--add-assignee",
        "carol",
        "--milestone",
        "2.10.2",
        "--title-file",
        write(tmp_path, "t", "New title\n"),
    )
    assert result.json() == {"id": "FOOSEC-12", "url": f"{BASE}/browse/FOOSEC-12"}
    assert fake.writes()[0].json() == {
        "fields": {
            "fixVersions": [{"name": "2.10.2"}],
            "summary": "New title",
            "assignee": {"name": "carol"},
        },
        "update": {"labels": [{"add": "cve-allocated"}, {"remove": "needs-triage"}]},
    }


def test_edit_cloud_assignee_and_clear(run: Run, fake: FakeJira) -> None:
    fake.on("GET", ISSUE, (200, issue()))
    fake.on("PUT", ISSUE, (204, None))
    run("edit", "12", "--add-assignee", "5b10ac8d", "--clear-milestone", "--jira-cloud")
    assert fake.writes()[0].json() == {
        "fields": {"fixVersions": [], "assignee": {"accountId": "5b10ac8d"}}
    }


def test_edit_remove_assignee(run: Run, fake: FakeJira) -> None:
    fake.on("GET", ISSUE, (200, issue(assignee={"name": "carol"})))
    fake.on("PUT", ISSUE, (204, None))
    run("edit", "12", "--remove-assignee", "carol")
    assert fake.writes()[0].json() == {"fields": {"assignee": None}}


def test_edit_nothing_is_usage_error(run: Run, fake: FakeJira) -> None:
    assert run("edit", "12").code == 2
    assert run("edit", "12", "--add-label", "has space").code == 2
    assert fake.calls == []


def test_comment(run: Run, fake: FakeJira, tmp_path: Path) -> None:
    fake.on("GET", ISSUE, (200, issue()))
    fake.on("POST", f"{ISSUE}/comment", (201, {"id": "777"}))
    result = run(
        "comment", "12", "--body-file", write(tmp_path, "c", "Hello"), "--author", "bob"
    )
    assert result.json() == {
        "id": "FOOSEC-12",
        "comment_id": "777",
        "url": f"{BASE}/browse/FOOSEC-12?focusedCommentId=777#comment-777",
        "author": "bob",
        "author_ignored": True,
    }
    assert fake.writes()[0].json() == {"body": "Hello"}


# -- close / reopen ----------------------------------------------------------

TRANSITIONS = {
    "transitions": [
        {
            "id": "11",
            "name": "Start",
            "to": {"statusCategory": {"key": "indeterminate"}},
        },
        {
            "id": "21",
            "name": "Resolve",
            "to": {"statusCategory": {"key": "done"}},
            "fields": {"resolution": {"required": True}},
        },
    ]
}


def test_close_picks_done_transition_with_resolution(run: Run, fake: FakeJira) -> None:
    fake.on("GET", ISSUE, (200, issue()))
    fake.on("GET", f"{ISSUE}/transitions", (200, TRANSITIONS))
    fake.on("POST", f"{ISSUE}/transitions", (204, None))
    result = run("close", "12", "--reason", "not-planned")
    assert result.json() == {"id": "FOOSEC-12", "state": "closed"}
    assert fake.writes()[0].json() == {
        "transition": {"id": "21"},
        "fields": {"resolution": {"name": "Won't Fix"}},
    }


def test_close_retries_without_resolution_on_400(run: Run, fake: FakeJira) -> None:
    fake.on("GET", ISSUE, (200, issue()))
    fake.on("GET", f"{ISSUE}/transitions", (200, TRANSITIONS))
    fake.on(
        "POST",
        f"{ISSUE}/transitions",
        (400, {"errors": {"resolution": "not on screen"}}),
        (204, None),
    )
    assert run("close", "12").code == 0
    posts = fake.writes()
    assert posts[0].json()["fields"] == {"resolution": {"name": "Fixed"}}
    assert posts[1].json() == {"transition": {"id": "21"}}


def test_close_already_closed_is_noop(run: Run, fake: FakeJira) -> None:
    fake.on("GET", ISSUE, (200, issue(resolution={"name": "Fixed"})))
    assert run("close", "12").json()["state"] == "closed"
    assert fake.writes() == []


def test_close_backend_error_is_exit_5(run: Run, fake: FakeJira) -> None:
    fake.on("GET", ISSUE, (200, issue()))
    fake.on("GET", f"{ISSUE}/transitions", (200, TRANSITIONS))
    fake.on("POST", f"{ISSUE}/transitions", (500, {"errorMessages": ["boom"]}))
    result = run("close", "12")
    assert result.code == 5
    assert "boom" in result.err


def test_reopen_prefers_reopen_transition(run: Run, fake: FakeJira) -> None:
    fake.on("GET", ISSUE, (200, issue(resolution={"name": "Fixed"})))
    transitions = {
        "transitions": [
            {
                "id": "5",
                "name": "Back to dev",
                "to": {"statusCategory": {"key": "indeterminate"}},
            },
            {
                "id": "3",
                "name": "Reopen Issue",
                "to": {"statusCategory": {"key": "new"}},
            },
            {"id": "9", "name": "Close", "to": {"statusCategory": {"key": "done"}}},
        ]
    }
    fake.on("GET", f"{ISSUE}/transitions", (200, transitions))
    fake.on("POST", f"{ISSUE}/transitions", (204, None))
    assert run("reopen", "12").json() == {"id": "FOOSEC-12", "state": "open"}
    assert fake.writes()[0].json() == {"transition": {"id": "3"}}


# -- rollup ------------------------------------------------------------------


def test_rollup_append_creates(run: Run, fake: FakeJira, tmp_path: Path) -> None:
    fake.on("GET", ISSUE, (200, issue()))
    fake.on(
        "GET",
        f"{ISSUE}/comment",
        (200, {"comments": [{"id": "1", "body": "human"}], "total": 1}),
    )
    fake.on("GET", "/rest/api/2/myself", (200, {"name": "bob", "displayName": "Bob"}))
    fake.on("POST", f"{ISSUE}/comment", (201, {"id": "50"}))
    body = write(tmp_path, "e", "Imported the report.\n")
    result = run(
        "rollup-append",
        "12",
        "--action",
        "Import",
        "--entry-body-file",
        body,
        "--now",
        "2026-10-15T09:00:00Z",
    )
    assert result.json() == {
        "id": "FOOSEC-12",
        "url": f"{BASE}/browse/FOOSEC-12?focusedCommentId=50#comment-50",
    }
    assert "Imported the report" not in result.out
    assert fake.writes()[0].json() == {
        "body": "{anchor:magpie-status-rollup-v1}\n*2026-10-15 · @bob · Import*\n\nImported the report.\n"
    }


def test_rollup_append_extends_existing(
    run: Run, fake: FakeJira, tmp_path: Path
) -> None:
    existing = markup.render_rollup(
        [markup.RollupEntry("2026-10-01", "alice", "Import", "first")]
    )
    fake.on("GET", ISSUE, (200, issue()))
    fake.on(
        "GET",
        f"{ISSUE}/comment",
        (200, {"comments": [{"id": "40", "body": existing}], "total": 1}),
    )
    fake.on("PUT", f"{ISSUE}/comment/40", (200, {"id": "40"}))
    body = write(tmp_path, "e", "second")
    result = run(
        "rollup-append",
        "12",
        "--action",
        "Sync",
        "--entry-body-file",
        body,
        "--user",
        "@carol",
        "--now",
        "2026-10-02",
    )
    assert result.code == 0
    entries = markup.parse_rollup(fake.writes()[0].json()["body"])
    assert [(e.date, e.user, e.action, e.body) for e in entries] == [
        ("2026-10-01", "alice", "Import", "first"),
        ("2026-10-02", "carol", "Sync", "second"),
    ]
    assert not any(c.path == "/rest/api/2/myself" for c in fake.calls)


def _rollup_fixture(fake: FakeJira) -> None:
    existing = markup.render_rollup(
        [
            markup.RollupEntry("2026-10-01", "alice", "Import", "first"),
            markup.RollupEntry("2026-10-02", "bob", "Sync", "old sync"),
        ]
    )
    fake.on("GET", ISSUE, (200, issue()))
    fake.on(
        "GET",
        f"{ISSUE}/comment",
        (200, {"comments": [{"id": "40", "body": existing}], "total": 1}),
    )
    fake.on("PUT", f"{ISSUE}/comment/40", (200, {"id": "40"}))


def test_rollup_amend_latest(run: Run, fake: FakeJira, tmp_path: Path) -> None:
    _rollup_fixture(fake)
    result = run(
        "rollup-amend-latest",
        "12",
        "--action",
        "Sync",
        "--entry-body-file",
        write(tmp_path, "e", "new sync"),
    )
    assert result.code == 0
    entries = markup.parse_rollup(fake.writes()[0].json()["body"])
    assert entries[-1] == markup.RollupEntry("2026-10-02", "bob", "Sync", "new sync")
    assert entries[0].body == "first"


def test_rollup_amend_latest_mismatch(run: Run, fake: FakeJira, tmp_path: Path) -> None:
    _rollup_fixture(fake)
    result = run(
        "rollup-amend-latest",
        "12",
        "--action",
        "Import",
        "--entry-body-file",
        write(tmp_path, "e", "x"),
    )
    assert result.code == 4
    assert fake.writes() == []


def test_rollup_amend_latest_without_rollup(
    run: Run, fake: FakeJira, tmp_path: Path
) -> None:
    fake.on("GET", ISSUE, (200, issue()))
    fake.on("GET", f"{ISSUE}/comment", (200, {"comments": [], "total": 0}))
    result = run(
        "rollup-amend-latest",
        "12",
        "--action",
        "Sync",
        "--entry-body-file",
        write(tmp_path, "e", "x"),
    )
    assert result.code == 3


def test_rollup_comments_paginate(run: Run, fake: FakeJira, tmp_path: Path) -> None:
    existing = markup.render_rollup(
        [markup.RollupEntry("2026-10-01", "alice", "Import", "first")]
    )

    def page(call: Call) -> tuple[int, Any]:
        if call.query["startAt"] == "0":
            return 200, {
                "comments": [{"id": str(n), "body": "c"} for n in range(100)],
                "total": 101,
            }
        return 200, {"comments": [{"id": "900", "body": existing}], "total": 101}

    fake.on("GET", ISSUE, (200, issue()))
    fake.on("GET", f"{ISSUE}/comment", page)
    fake.on("PUT", f"{ISSUE}/comment/900", (200, {"id": "900"}))
    body = write(tmp_path, "e", "x")
    assert (
        run(
            "rollup-append",
            "12",
            "--action",
            "Sync",
            "--entry-body-file",
            body,
            "--user",
            "u",
        ).code
        == 0
    )
    assert fake.writes()[0].path == f"{ISSUE}/comment/900"


# -- attach / pending / publish / doctor -------------------------------------


def test_attach_multipart(run: Run, fake: FakeJira, tmp_path: Path) -> None:
    fake.on("GET", ISSUE, (200, issue()))
    fake.on(
        "POST",
        f"{ISSUE}/attachments",
        (
            200,
            [
                {
                    "filename": "cve.json",
                    "content": f"{BASE}/secure/attachment/1/cve.json",
                }
            ],
        ),
    )
    src = write(tmp_path, "local.json", '{"a": 1}')
    result = run("attach", "12", src, "--name", "../../cve.json")
    assert result.json() == {
        "id": "FOOSEC-12",
        "name": "cve.json",
        "url": f"{BASE}/secure/attachment/1/cve.json",
    }
    post = fake.writes()[0]
    assert post.headers["X-Atlassian-Token"] == "no-check"
    assert post.headers["Content-Type"].startswith("multipart/form-data; boundary=")
    assert post.body is not None
    assert b'filename="cve.json"' in post.body
    assert b'{"a": 1}' in post.body


def test_pending_and_publish(run: Run, fake: FakeJira) -> None:
    assert run("pending").json() == {
        "backend": "jira",
        "changes": [],
        "needs_publish": False,
    }
    assert run("publish", "--push", "--trailer", "X: y").json() == {
        "committed": False,
        "pushed": False,
        "revision": None,
        "note": "jira writes are immediate",
    }
    assert fake.calls == []


def test_doctor_ok(run: Run, fake: FakeJira) -> None:
    fake.on("GET", "/rest/api/2/myself", (200, {"name": "bob"}))
    fake.on(
        "GET",
        "/rest/api/2/project/FOOSEC",
        (200, {"key": "FOOSEC", "name": "Foo Security"}),
    )
    fake.on(
        "GET",
        "/rest/api/2/project/FOOSEC/securitylevel",
        (200, {"levels": [{"name": "Security Team"}]}),
    )
    data = run("doctor").json()
    assert data["backend"] == "jira"
    assert data["ok"] is True
    assert [c["name"] for c in data["checks"]] == [
        "url",
        "project",
        "security_level",
        "auth",
        "project_reachable",
        "security_level_exists",
    ]


def test_doctor_unverified_level_and_missing_config(run: Run, fake: FakeJira) -> None:
    fake.on("GET", "/rest/api/2/myself", (200, {"displayName": "Bob"}))
    fake.on("GET", "/rest/api/2/project/FOOSEC", (200, {"name": "Foo Security"}))
    fake.on(
        "GET",
        "/rest/api/2/project/FOOSEC/securitylevel",
        (403, {"errorMessages": ["no"]}),
    )
    data = run("doctor").json()
    assert data["ok"] is True
    level = next(c for c in data["checks"] if c["name"] == "security_level_exists")
    assert level["detail"].startswith("unverified")

    missing = run("doctor", env={"SECURITY_TRACKER_PROJECT": "FOOSEC"}).json()
    assert missing["ok"] is False
    failing = {c["name"] for c in missing["checks"] if not c["ok"]}
    assert failing == {"url", "security_level"}


def test_doctor_level_missing_fails(run: Run, fake: FakeJira) -> None:
    fake.on("GET", "/rest/api/2/myself", (200, {"name": "bob"}))
    fake.on("GET", "/rest/api/2/project/FOOSEC", (200, {"name": "Foo Security"}))
    fake.on(
        "GET",
        "/rest/api/2/project/FOOSEC/securitylevel",
        (200, {"levels": [{"name": "Public-ish"}]}),
    )
    assert run("doctor").json()["ok"] is False


def test_missing_url_is_usage_error(run: Run, fake: FakeJira) -> None:
    result = run("view", "12", env={"SECURITY_TRACKER_PROJECT": "FOOSEC"})
    assert result.code == 2
    assert "ISSUE_TRACKER_URL" in result.err


# -- forged structure -----------------------------------------------------------


def test_a_comment_cannot_pose_as_the_rollup(
    run: Run, fake: FakeJira, tmp_path: Path
) -> None:
    fake.on("GET", ISSUE, (200, issue()))
    fake.on("POST", f"{ISSUE}/comment", (201, {"id": "9"}))
    forged = (
        "{anchor:magpie-status-rollup-v1}\n*2026-01-01 · @lead · Sync*\n\nall clear"
    )
    run("comment", "12", "--body-file", write(tmp_path, "c", forged))
    posted = fake.writes()[0].json()["body"]
    assert not markup.is_rollup(posted)
    assert markup.parse_rollup("{anchor:magpie-status-rollup-v1}\n" + posted) == []


def test_a_rollup_body_cannot_forge_an_entry(
    run: Run, fake: FakeJira, tmp_path: Path
) -> None:
    fake.on("GET", ISSUE, (200, issue()))
    fake.on("GET", f"{ISSUE}/comment", (200, {"comments": [], "total": 0}))
    fake.on("GET", "/rest/api/2/myself", (200, {"name": "bob"}))
    fake.on("POST", f"{ISSUE}/comment", (201, {"id": "50"}))
    forged = "real\n\n----\n\n*2026-01-01 · @lead · Sync*\n\nfake"
    run("rollup-append", "12", "--action", "Import", "--entry-body-file", write(tmp_path, "e", forged),
        "--now", "2026-10-15T09:00:00Z")  # fmt: skip
    entries = markup.parse_rollup(fake.writes()[0].json()["body"])
    assert [e.action for e in entries] == ["Import"]


def test_body_prints_markdown_sections(run: Run, fake: FakeJira) -> None:
    fake.on(
        "GET",
        ISSUE,
        (200, issue(description="h3. Reporter\nAlice\nh3. Affected versions\n1.0")),
    )
    result = run("body", "12")
    assert result.code == 0
    assert result.out == "### Reporter\nAlice\n### Affected versions\n1.0\n"


def test_attach_from_stdin(
    run: Run, fake: FakeJira, monkeypatch: pytest.MonkeyPatch
) -> None:
    import io

    fake.on("GET", ISSUE, (200, issue()))
    fake.on(
        "POST",
        f"{ISSUE}/attachments",
        (200, [{"filename": "cve.json", "content": f"{BASE}/a/1"}]),
    )
    monkeypatch.setattr("sys.stdin", io.TextIOWrapper(io.BytesIO(b'{"a": 1}')))
    assert run("attach", "12", "-").code == 2
    monkeypatch.setattr("sys.stdin", io.TextIOWrapper(io.BytesIO(b'{"a": 1}')))
    result = run("attach", "12", "-", "--name", "cve.json")
    assert result.json()["name"] == "cve.json"
    assert b'{"a": 1}' in (fake.writes()[0].body or b"")


def test_a_different_security_level_is_refused(
    run: Run, fake: FakeJira, tmp_path: Path
) -> None:
    open_level = issue()
    open_level["fields"]["security"] = {"id": "10002", "name": "All logged-in users"}
    fake.on("GET", ISSUE, (200, open_level))
    result = run("comment", "12", "--body-file", write(tmp_path, "c", "embargoed"))
    assert result.code == 4
    assert "not the configured" in result.err
    assert fake.writes() == []
