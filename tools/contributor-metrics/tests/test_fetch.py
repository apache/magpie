# SPDX-License-Identifier: Apache-2.0
# https://www.apache.org/licenses/LICENSE-2.0
import json
import subprocess
from collections.abc import Iterator
from dataclasses import dataclass, field

import pytest

from contributor_metrics.fetch import InvalidLogin, fetch_items


@dataclass
class FakeResult:
    returncode: int
    stdout: str
    stderr: str = ""


@dataclass
class FakeGh:
    """Answers gh calls by matching a substring of the search file (q=@file) or the command line."""

    responses: list[tuple[str, str]] = field(default_factory=list)
    calls: list[list[str]] = field(default_factory=list)
    queries: list[str] = field(default_factory=list)

    def __call__(self, cmd, *args, **kwargs):
        self.calls.append(cmd)
        query = ""
        for part in cmd:
            if part.startswith("q=@"):
                with open(part[len("q=@") :]) as fh:
                    query = fh.read()
                self.queries.append(query)
        for needle, stdout in self.responses:
            if needle in query or needle in " ".join(cmd):
                return FakeResult(0, stdout)
        raise AssertionError(f"unexpected gh invocation: {cmd} / {query}")


@pytest.fixture
def fake_gh(monkeypatch: pytest.MonkeyPatch) -> Iterator[FakeGh]:
    f = FakeGh()
    monkeypatch.setattr(subprocess, "run", f)
    yield f


def search(nodes, count=None, more=False):
    return json.dumps(
        {
            "data": {
                "search": {
                    "issueCount": count if count is not None else len(nodes),
                    "pageInfo": {"hasNextPage": more, "endCursor": "c" if more else None},
                    "nodes": nodes,
                }
            }
        }
    )


EMPTY = search([])
NO_CONVO = json.dumps(
    {"data": {"repository": {"issueOrPullRequest": {"comments": {"nodes": []}, "reviews": {"nodes": []}}}}}
)


def contributions(nodes, total=None, repo="o/r"):
    return json.dumps(
        {
            "data": {
                "user": {
                    "contributionsCollection": {
                        "pullRequestReviewContributionsByRepository": [
                            {
                                "repository": {"nameWithOwner": repo},
                                "contributions": {
                                    "totalCount": total if total is not None else len(nodes),
                                    "pageInfo": {"hasNextPage": False, "endCursor": None},
                                    "nodes": nodes,
                                },
                            }
                        ]
                    }
                }
            }
        }
    )


EMPTY_CONTRIB = contributions([])


def review_node(pr, occurred, body="", comments=0, labels=()):
    return {
        "occurredAt": occurred,
        "pullRequestReview": {
            "url": f"https://github.com/o/r/pull/{pr}#r-{occurred}",
            "body": body,
            "comments": {"totalCount": comments},
        },
        "pullRequest": {
            "url": f"https://github.com/o/r/pull/{pr}",
            "number": pr,
            "labels": {"nodes": [{"name": n} for n in labels]},
        },
    }


def streams(**overrides):
    base = {
        "type:pr author:": EMPTY,
        "type:issue author:": EMPTY,
        "contributionsCollection": EMPTY_CONTRIB,
        "-author:": EMPTY,
        "commenter:": EMPTY,
        "issueOrPullRequest": NO_CONVO,
    }
    base.update(overrides)
    return list(base.items())


def test_fetch_rejects_invalid_login(fake_gh):
    with pytest.raises(InvalidLogin):
        fetch_items(
            "o/r",
            "bad;login",
            since="2026-03-01",
            end="2026-08-31",
            phrases=(),
            maintainers=(),
        )
    assert fake_gh.calls == []


def test_fetch_passes_search_through_a_file_not_the_command_line(fake_gh):
    fake_gh.responses = streams()
    fetch_items("o/r", "alice", since="2026-03-01", end="2026-08-31", phrases=(), maintainers=())
    for cmd in fake_gh.calls:
        assert not any("author:alice" in part for part in cmd)


def test_fetch_builds_pr_items_with_areas(fake_gh):
    node = {
        "number": 7,
        "url": "https://github.com/o/r/pull/7",
        "state": "MERGED",
        "merged": True,
        "mergedAt": "2026-04-02T00:00:00Z",
        "createdAt": "2026-04-01T00:00:00Z",
        "labels": {"nodes": [{"name": "area:ui"}, {"name": "kind:bug"}]},
    }
    fake_gh.responses = streams(**{"type:pr author:": search([node])})
    items, caps, _ = fetch_items(
        "o/r", "alice", since="2026-03-01", end="2026-08-31", phrases=(), maintainers=()
    )
    (item,) = items
    assert (item.id, item.kind, item.merged, item.areas) == ("pr-7", "pr", True, ("area:ui", "kind:bug"))
    assert item.created_at == "2026-04-01"
    assert caps == []


def test_fetch_flags_maintainer_pushback_candidate_only(fake_gh):
    convo = {
        "data": {
            "repository": {
                "issueOrPullRequest": {
                    "comments": {
                        "nodes": [
                            {
                                "url": "u1",
                                "author": {"login": "alice"},
                                "authorAssociation": "CONTRIBUTOR",
                                "body": "LLM wrote this? no, I did",
                            },
                            {
                                "url": "u2",
                                "author": {"login": "dependabot[bot]"},
                                "authorAssociation": "NONE",
                                "body": "slop",
                            },
                            {
                                "url": "u3",
                                "author": {"login": "maint"},
                                "authorAssociation": "MEMBER",
                                "body": "This looks AI-generated, please review your own work.",
                            },
                        ]
                    },
                    "reviews": {"nodes": []},
                }
            }
        }
    }
    node = {
        "number": 8,
        "url": "https://github.com/o/r/pull/8",
        "state": "OPEN",
        "merged": False,
        "createdAt": "2026-04-01T00:00:00Z",
        "labels": {"nodes": []},
    }
    fake_gh.responses = streams(
        **{"type:pr author:": search([node]), "issueOrPullRequest": json.dumps(convo)}
    )
    items, _, _ = fetch_items(
        "o/r", "alice", since="2026-03-01", end="2026-08-31", phrases=(), maintainers=()
    )
    assert items[0].pushback_candidate == "u3"


def test_fetch_uses_configured_phrases_and_roster(fake_gh):
    convo = {
        "data": {
            "repository": {
                "issueOrPullRequest": {
                    "comments": {
                        "nodes": [
                            {
                                "url": "u9",
                                "author": {"login": "rostered"},
                                "authorAssociation": "CONTRIBUTOR",
                                "body": "Please drop the robo-text.",
                            },
                        ]
                    },
                    "reviews": {"nodes": []},
                }
            }
        }
    }
    node = {
        "number": 9,
        "url": "https://github.com/o/r/pull/9",
        "state": "OPEN",
        "merged": False,
        "createdAt": "2026-04-01T00:00:00Z",
        "labels": {"nodes": []},
    }
    fake_gh.responses = streams(
        **{"type:pr author:": search([node]), "issueOrPullRequest": json.dumps(convo)}
    )
    items, _, _ = fetch_items(
        "o/r",
        "alice",
        since="2026-03-01",
        end="2026-08-31",
        phrases=("robo-text",),
        maintainers=("rostered",),
    )
    assert items[0].pushback_candidate == "u9"


def test_reviews_come_from_contributions_dated_by_occurrence(fake_gh):
    nodes = [
        review_node(11, "2026-05-02T10:00:00Z", body="LGTM"),
        review_node(11, "2026-05-03T10:00:00Z", body="x" * 120),
        review_node(12, "2026-06-01T10:00:00Z", comments=1, labels=("area:ui",)),
    ]
    fake_gh.responses = streams(contributionsCollection=contributions(nodes))
    items, _, _ = fetch_items(
        "o/r", "alice", since="2026-03-01", end="2026-08-31", phrases=(), maintainers=()
    )
    reviews = {i.id: i for i in items if i.kind == "review"}
    assert set(reviews) == {"review-11", "review-12"}
    assert reviews["review-11"].created_at == "2026-05-02" and reviews["review-11"].substantive
    assert reviews["review-12"].substantive and reviews["review-12"].areas == ("area:ui",)
    assert not any("reviewed-by:" in " ".join(c) for c in fake_gh.calls)


def test_substantive_reviews_are_not_capped(fake_gh):
    nodes = [review_node(n, "2026-05-02T10:00:00Z", comments=2) for n in range(100, 115)]
    fake_gh.responses = streams(contributionsCollection=contributions(nodes))
    items, _, _ = fetch_items(
        "o/r", "alice", since="2026-03-01", end="2026-08-31", phrases=(), maintainers=()
    )
    assert sum(1 for i in items if i.kind == "review" and i.substantive) == 15


def test_every_search_is_bounded_by_the_window_end(fake_gh):
    fake_gh.responses = streams()
    fetch_items("o/r", "alice", since="2026-03-01", end="2026-08-31", phrases=(), maintainers=())
    assert fake_gh.queries, "no searches issued"
    for q in fake_gh.queries:
        assert "2026-08-31" in q, q
        assert "updated:>=2026-03-01" not in q or "created:<=2026-08-31" in q, q


def test_merged_after_the_window_end_does_not_count_as_merged(fake_gh):
    node = {
        "number": 7,
        "url": "https://github.com/o/r/pull/7",
        "state": "MERGED",
        "merged": True,
        "mergedAt": "2026-09-15T00:00:00Z",
        "createdAt": "2026-08-20T00:00:00Z",
        "labels": {"nodes": []},
    }
    fake_gh.responses = streams(**{"type:pr author:": search([node])})
    items, _, _ = fetch_items(
        "o/r", "alice", since="2026-03-01", end="2026-08-31", phrases=(), maintainers=()
    )
    assert items[0].merged is False


def test_thread_is_dated_by_the_candidates_own_comment_and_dropped_outside_the_window(fake_gh):
    threads = [
        {
            "number": 21,
            "url": "https://github.com/o/r/issues/21",
            "state": "OPEN",
            "createdAt": "2025-01-01T00:00:00Z",
            "updatedAt": "2026-05-01T00:00:00Z",
            "labels": {"nodes": []},
        },
        {
            "number": 22,
            "url": "https://github.com/o/r/issues/22",
            "state": "OPEN",
            "createdAt": "2025-01-01T00:00:00Z",
            "updatedAt": "2026-05-01T00:00:00Z",
            "labels": {"nodes": []},
        },
    ]

    def convo(dates):
        return json.dumps(
            {
                "data": {
                    "repository": {
                        "issueOrPullRequest": {
                            "comments": {
                                "nodes": [
                                    {
                                        "url": f"c{d}",
                                        "author": {"login": "alice"},
                                        "authorAssociation": "CONTRIBUTOR",
                                        "body": "hi",
                                        "createdAt": d,
                                    }
                                    for d in dates
                                ]
                            }
                        }
                    }
                }
            }
        )

    fake_gh.responses = streams(**{"commenter:": search(threads)})
    fake_gh.responses = [
        ("number=21", convo(["2025-02-01T00:00:00Z"])),
        ("number=22", convo(["2025-02-01T00:00:00Z", "2026-04-10T00:00:00Z"])),
        *fake_gh.responses,
    ]
    items, _, _ = fetch_items(
        "o/r", "alice", since="2026-03-01", end="2026-08-31", phrases=(), maintainers=()
    )
    threads_out = {i.id: i for i in items if i.kind == "thread"}
    assert set(threads_out) == {"thread-22"}
    assert threads_out["thread-22"].created_at == "2026-04-10"


def test_rate_limit_is_retried_with_backoff(fake_gh, monkeypatch):
    import contributor_metrics.fetch as f

    sleeps = []
    monkeypatch.setattr(f.time, "sleep", lambda s: sleeps.append(s))
    failures = {"n": 0}
    base = fake_gh.__call__

    def flaky(cmd, *a, **k):
        if "contributionsCollection" in " ".join(cmd) and failures["n"] < 2:
            failures["n"] += 1
            return FakeResult(1, "", "gh: API rate limit exceeded for user")
        return base(cmd, *a, **k)

    fake_gh.responses = streams()
    monkeypatch.setattr(subprocess, "run", flaky)
    fetch_items("o/r", "alice", since="2026-03-01", end="2026-08-31", phrases=(), maintainers=())
    assert len(sleeps) == 2 and sleeps[1] > sleeps[0]


def test_other_gh_errors_are_not_retried(fake_gh, monkeypatch):
    import contributor_metrics.fetch as f

    monkeypatch.setattr(f.time, "sleep", lambda s: (_ for _ in ()).throw(AssertionError("should not sleep")))
    monkeypatch.setattr(
        subprocess, "run", lambda *a, **k: FakeResult(1, "", "gh: Could not resolve to a Repository")
    )
    with pytest.raises(f.GhError):
        fetch_items("o/r", "alice", since="2026-03-01", end="2026-08-31", phrases=(), maintainers=())


def test_fetch_records_cap_hit(fake_gh):
    nodes = [
        {
            "number": n,
            "url": f"https://github.com/o/r/issues/{n}",
            "state": "OPEN",
            "createdAt": "2026-04-01T00:00:00Z",
            "labels": {"nodes": []},
        }
        for n in range(100)
    ]
    fake_gh.responses = streams(**{"type:issue author:": search(nodes, count=450, more=True)})
    items, caps, _ = fetch_items(
        "o/r", "alice", since="2026-03-01", end="2026-08-31", phrases=(), maintainers=()
    )
    assert "issues_filed" in caps
    assert sum(1 for i in items if i.kind == "issue") == 300


def test_fetch_rejects_a_repository_without_owner(fake_gh):
    from contributor_metrics.fetch import InvalidRepo

    with pytest.raises(InvalidRepo):
        fetch_items("justarepo", "alice", since="2026-03-01", end="2026-08-31", phrases=(), maintainers=())
    assert fake_gh.calls == []


def test_substantive_thresholds_are_configurable(fake_gh):
    nodes = [
        review_node(21, "2026-05-02T10:00:00Z", body="x" * 60),
        review_node(22, "2026-05-02T10:00:00Z", comments=2),
        review_node(23, "2026-05-02T10:00:00Z", comments=3),
        review_node(24, "2026-05-02T10:00:00Z", body="x" * 50),
    ]
    fake_gh.responses = streams(contributionsCollection=contributions(nodes))
    items, _, _ = fetch_items(
        "o/r",
        "alice",
        since="2026-03-01",
        end="2026-08-31",
        phrases=(),
        maintainers=(),
        substantive_body_chars=50,
        substantive_line_comments=3,
    )
    substantive = {i.id for i in items if i.kind == "review" and i.substantive}
    assert substantive == {"review-21", "review-23"}
