# SPDX-License-Identifier: Apache-2.0
# https://www.apache.org/licenses/LICENSE-2.0
"""The Jira tracker backend, against recorded REST responses. No network."""

import io
import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from email.message import Message

import pytest

from contributor_metrics.backends.jira import InvalidJiraConfig, InvalidJiraUser, JiraError, JiraTracker
from contributor_metrics.fetch import fetch_items
from tests.test_fetch import fake_gh, search, streams  # noqa: F401  (fixture re-export)

BASE = "https://issues.example.org/jira"


@dataclass
class FakeJira:
    """Answers GET requests by matching a substring of the JQL (or the path)."""

    responses: list[tuple[str, object]] = field(default_factory=list)
    requests: list[urllib.request.Request] = field(default_factory=list)

    def __call__(self, req):
        self.requests.append(req)
        url = urllib.parse.urlparse(req.full_url)
        params = urllib.parse.parse_qs(url.query)
        jql = params.get("jql", [""])[0]
        for needle, answer in self.responses:
            if needle in jql or needle in url.path:
                if isinstance(answer, Exception):
                    raise answer
                return io.BytesIO(json.dumps(answer).encode())
        raise AssertionError(f"unexpected Jira request: {req.full_url}")

    def jqls(self):
        return [
            urllib.parse.parse_qs(urllib.parse.urlparse(r.full_url).query).get("jql", [""])[0]
            for r in self.requests
        ]


def page(issues, total=None):
    return {
        "startAt": 0,
        "maxResults": 100,
        "total": len(issues) if total is None else total,
        "issues": issues,
    }


def comment(cid, author, created, body="thanks"):
    return {"id": str(cid), "author": {"name": author}, "created": created, "body": body}


def issue(
    key,
    *,
    reporter="someone",
    created="2026-01-10T09:00:00.000+0000",
    updated=None,
    comments=(),
    histories=(),
    labels=(),
    resolution=None,
):
    return {
        "key": key,
        "fields": {
            "created": created,
            "updated": updated or created,
            "labels": list(labels),
            "resolution": resolution,
            "reporter": {"name": reporter},
            "comment": {"comments": list(comments), "total": len(comments)},
        },
        "changelog": {"histories": list(histories)},
    }


def history(author, created, *fields):
    return {"author": {"name": author}, "created": created, "items": [{"field": f} for f in fields]}


def tracker(fake, **kw):
    return JiraTracker(
        BASE,
        "FOO",
        token=kw.pop("token", ""),
        token_host=kw.pop("token_host", "issues.example.org"),
        opener=fake,
        sleep=lambda s: None,
        **kw,
    )


def answers(filed=(), scanned=(), targeted=(), scan_total=None):
    return [
        ('reporter = "', page(list(filed))),
        ("CHANGED BY", page(list(targeted))),
        ("updated >= ", page(list(scanned), scan_total)),
    ]


def run(fake, login="jdoe", maintainers=("maint",), phrases=()):
    return tracker(fake).fetch(
        login, since="2026-03-01", end="2026-08-31", phrases=phrases, maintainers=maintainers
    )


def test_filed_issues_become_issue_items_with_pushback_from_a_rostered_maintainer():
    filed = [
        issue(
            "FOO-1",
            reporter="jdoe",
            created="2026-04-01T10:00:00.000+0000",
            labels=("area:ui",),
            resolution={"name": "Fixed"},
            comments=[
                comment(10, "drive-by", "2026-04-02T10:00:00.000+0000", "this is AI slop"),
                comment(11, "maint", "2026-04-03T10:00:00.000+0000", "Looks AI-generated; did you run it?"),
            ],
        )
    ]
    fake = FakeJira(answers(filed=filed))
    items, caps, notes = run(fake)
    (item,) = [i for i in items if i.kind == "issue"]
    assert item.id == "issue-FOO-1"
    assert item.url == f"{BASE}/browse/FOO-1"
    assert (item.created_at, item.areas, item.closed_unmerged) == ("2026-04-01", ("area:ui",), True)
    assert item.pushback_candidate == f"{BASE}/browse/FOO-1?focusedCommentId=11#comment-11"
    assert caps == [] and notes == []
    # The filed search is scoped to the project, the reporter and the window.
    assert (
        'project = "FOO" AND reporter = "jdoe" AND created >= "2026-03-01" AND created <= "2026-08-31 23:59"'
        in (fake.jqls()[0])
    )


def test_items_never_carry_comment_bodies():
    filed = [
        issue(
            "FOO-2",
            reporter="jdoe",
            created="2026-04-01T10:00:00.000+0000",
            comments=[comment(1, "maint", "2026-04-02T00:00:00.000+0000", "SECRET BODY slop")],
        )
    ]
    items, _, _ = run(FakeJira(answers(filed=filed)))
    assert "SECRET BODY" not in json.dumps([i.to_json() for i in items])


def test_threads_and_triage_are_dated_by_the_users_own_actions():
    scanned = [
        # Someone else's issue: jdoe commented inside the window -> thread + triage.
        issue(
            "FOO-10",
            updated="2026-06-01T00:00:00.000+0000",
            comments=[
                comment(1, "jdoe", "2026-02-01T00:00:00.000+0000"),
                comment(2, "jdoe", "2026-05-05T00:00:00.000+0000"),
            ],
        ),
        # Someone else's issue: jdoe only changed the status -> triage, no thread.
        issue(
            "FOO-11",
            updated="2026-06-02T00:00:00.000+0000",
            histories=[history("jdoe", "2026-04-04T00:00:00.000+0000", "status")],
        ),
        # A non-triage field change counts for nothing.
        issue(
            "FOO-12",
            updated="2026-06-03T00:00:00.000+0000",
            histories=[history("jdoe", "2026-04-04T00:00:00.000+0000", "description")],
        ),
        # jdoe's own issue: a comment is a thread, never triage.
        issue(
            "FOO-13",
            reporter="jdoe",
            updated="2026-06-04T00:00:00.000+0000",
            comments=[comment(3, "jdoe", "2026-07-01T00:00:00.000+0000")],
        ),
        # A comment outside the window is dropped.
        issue(
            "FOO-14",
            updated="2026-06-05T00:00:00.000+0000",
            comments=[comment(4, "jdoe", "2025-12-01T00:00:00.000+0000")],
        ),
    ]
    items, caps, _ = run(FakeJira(answers(scanned=scanned)))
    got = {i.id: i.created_at for i in items}
    assert got == {
        "thread-FOO-10": "2026-05-05",
        "triage-FOO-10": "2026-05-05",
        "triage-FOO-11": "2026-04-04",
        "thread-FOO-13": "2026-07-01",
    }
    assert caps == []


def test_targeted_field_change_search_reaches_beyond_a_capped_scan():
    targeted = [
        issue(
            "FOO-99",
            updated="2026-03-02T00:00:00.000+0000",
            histories=[history("JDoe", "2026-03-02T00:00:00.000+0000", "Priority")],
        )
    ]
    fake = FakeJira(answers(scanned=[], targeted=targeted, scan_total=1500))
    items, caps, notes = run(fake)
    assert [i.id for i in items] == ["triage-FOO-99"]
    assert caps == ["issues_triaged", "threads_commented"]
    assert any("not scanned" in n for n in notes)
    changed = next(q for q in fake.jqls() if "CHANGED BY" in q)
    assert 'status CHANGED BY "jdoe" DURING ("2026-03-01", "2026-08-31 23:59")' in changed


def test_no_roster_means_no_pushback_and_a_note():
    filed = [
        issue(
            "FOO-3",
            reporter="jdoe",
            created="2026-04-01T10:00:00.000+0000",
            comments=[comment(1, "maint", "2026-04-02T00:00:00.000+0000", "slop")],
        )
    ]
    items, _, notes = run(FakeJira(answers(filed=filed)), maintainers=())
    assert items[0].pushback_candidate == ""
    assert any("no maintainer roster" in n for n in notes)


def test_invalid_username_makes_no_request():
    fake = FakeJira()
    with pytest.raises(InvalidJiraUser):
        run(fake, login='x" OR reporter is not EMPTY')
    assert fake.requests == []


def test_invalid_config_is_rejected():
    with pytest.raises(InvalidJiraConfig):
        JiraTracker("not-a-url", "FOO", token="")
    with pytest.raises(InvalidJiraConfig):
        JiraTracker(BASE, 'FOO" OR 1=1', token="")


def test_token_is_sent_with_the_configured_scheme():
    fake = FakeJira(answers())
    tracker(fake, token="pat123", auth_scheme="Bearer").fetch(
        "jdoe", since="2026-03-01", end="2026-08-31", phrases=(), maintainers=("m",)
    )
    assert {r.get_header("Authorization") for r in fake.requests} == {"Bearer pat123"}


def test_anonymous_reads_send_no_authorization():
    fake = FakeJira(answers())
    run(fake)
    assert all(r.get_header("Authorization") is None for r in fake.requests)


def test_transient_errors_are_retried_then_fail():
    def unavailable():
        return urllib.error.HTTPError(BASE, 503, "Service Unavailable", Message(), None)

    calls = {"n": 0}

    class Flaky(FakeJira):
        def __call__(self, req):
            calls["n"] += 1
            if calls["n"] <= 2:
                raise unavailable()
            return super().__call__(req)

    run(Flaky(answers()))
    assert calls["n"] >= 3
    with pytest.raises(JiraError):
        run(FakeJira([("project", urllib.error.HTTPError(BASE, 401, "Unauthorized", Message(), None))]))


def test_mixed_fetch_takes_prs_from_github_and_issues_from_jira(fake_gh):  # noqa: F811
    pr = {
        "number": 7,
        "url": "https://github.com/o/r/pull/7",
        "state": "MERGED",
        "merged": True,
        "mergedAt": "2026-04-02T00:00:00Z",
        "createdAt": "2026-04-01T00:00:00Z",
        "labels": {"nodes": []},
    }
    fake_gh.responses = streams(**{"type:pr author:": search([pr])})
    filed = [issue("FOO-1", reporter="jdoe", created="2026-04-01T10:00:00.000+0000")]
    items, caps, _ = fetch_items(
        "o/r",
        "alice",
        since="2026-03-01",
        end="2026-08-31",
        phrases=(),
        maintainers=("maint",),
        tracker=tracker(FakeJira(answers(filed=filed))),
        tracker_login="jdoe",
    )
    assert sorted(i.id for i in items) == ["issue-FOO-1", "pr-7"]
    assert not any("type:issue" in q for q in fake_gh.queries)
    assert caps == []


def test_a_failing_field_change_search_degrades_to_the_scan():
    scanned = [
        issue(
            "FOO-20",
            updated="2026-06-01T00:00:00.000+0000",
            histories=[history("jdoe", "2026-04-04T00:00:00.000+0000", "labels")],
        )
    ]
    fake = FakeJira(
        [
            ('reporter = "', page([])),
            ("CHANGED BY", urllib.error.HTTPError(BASE, 400, "Bad Request", Message(), None)),
            ("updated >= ", page(scanned)),
        ]
    )
    items, _, notes = run(fake)
    assert [i.id for i in items] == ["triage-FOO-20"]
    assert any("field-change search failed" in n for n in notes)


def test_an_unconfirmed_host_reads_anonymously_with_a_note():
    fake = FakeJira(answers())
    _, _, notes = tracker(fake, token="pat123", token_host="jira.elsewhere.org").fetch(
        "jdoe", since="2026-03-01", end="2026-08-31", phrases=(), maintainers=("m",)
    )
    assert all(r.get_header("Authorization") is None for r in fake.requests)
    assert any("reading anonymously" in n for n in notes)
    assert not any("pat123" in n for n in notes)
