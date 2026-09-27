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

    def __call__(self, cmd, *args, **kwargs):
        self.calls.append(cmd)
        query = ""
        for part in cmd:
            if part.startswith("q=@"):
                with open(part[len("q=@") :]) as fh:
                    query = fh.read()
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


def streams(**overrides):
    base = {
        "type:pr author:": EMPTY,
        "type:issue author:": EMPTY,
        "reviewed-by:": EMPTY,
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
            review_depth=0,
            phrases=(),
            maintainers=(),
        )
    assert fake_gh.calls == []


def test_fetch_passes_search_through_a_file_not_the_command_line(fake_gh):
    fake_gh.responses = streams()
    fetch_items(
        "o/r", "alice", since="2026-03-01", end="2026-08-31", review_depth=0, phrases=(), maintainers=()
    )
    for cmd in fake_gh.calls:
        assert not any("author:alice" in part for part in cmd)


def test_fetch_builds_pr_items_with_areas(fake_gh):
    node = {
        "number": 7,
        "url": "https://github.com/o/r/pull/7",
        "state": "MERGED",
        "merged": True,
        "createdAt": "2026-04-01T00:00:00Z",
        "labels": {"nodes": [{"name": "area:ui"}, {"name": "kind:bug"}]},
    }
    fake_gh.responses = streams(**{"type:pr author:": search([node])})
    items, caps = fetch_items(
        "o/r", "alice", since="2026-03-01", end="2026-08-31", review_depth=0, phrases=(), maintainers=()
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
    items, _ = fetch_items(
        "o/r", "alice", since="2026-03-01", end="2026-08-31", review_depth=0, phrases=(), maintainers=()
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
    items, _ = fetch_items(
        "o/r",
        "alice",
        since="2026-03-01",
        end="2026-08-31",
        review_depth=0,
        phrases=("robo-text",),
        maintainers=("rostered",),
    )
    assert items[0].pushback_candidate == "u9"


def test_fetch_marks_substantive_reviews_within_depth(fake_gh):
    node = {
        "number": 11,
        "url": "https://github.com/o/r/pull/11",
        "state": "MERGED",
        "merged": True,
        "createdAt": "2026-05-01T00:00:00Z",
        "labels": {"nodes": []},
    }
    convo = {
        "data": {
            "repository": {
                "issueOrPullRequest": {
                    "comments": {"nodes": []},
                    "reviews": {
                        "nodes": [
                            {
                                "url": "r1",
                                "author": {"login": "alice"},
                                "authorAssociation": "CONTRIBUTOR",
                                "body": "LGTM",
                                "createdAt": "2026-05-02T00:00:00Z",
                                "comments": {"totalCount": 2},
                            }
                        ]
                    },
                }
            }
        }
    }
    fake_gh.responses = streams(**{"reviewed-by:": search([node]), "issueOrPullRequest": json.dumps(convo)})
    items, _ = fetch_items(
        "o/r", "alice", since="2026-03-01", end="2026-08-31", review_depth=10, phrases=(), maintainers=()
    )
    (review,) = items
    assert review.kind == "review" and review.substantive


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
    items, caps = fetch_items(
        "o/r", "alice", since="2026-03-01", end="2026-08-31", review_depth=0, phrases=(), maintainers=()
    )
    assert "issues_filed" in caps
    assert sum(1 for i in items if i.kind == "issue") == 300
