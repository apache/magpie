# SPDX-License-Identifier: Apache-2.0
# https://www.apache.org/licenses/LICENSE-2.0
"""The GitHub backend answering one side of the seam only."""

from contributor_metrics.backends.common import CODE_HOST
from contributor_metrics.backends.github import fetch_items
from tests.test_fetch import fake_gh, search, streams  # noqa: F401  (fixture re-export)


def test_code_host_side_runs_no_issue_streams(fake_gh):  # noqa: F811
    fake_gh.responses = streams()
    fetch_items(
        "o/r",
        "alice",
        since="2026-03-01",
        end="2026-08-31",
        phrases=(),
        maintainers=(),
        streams=frozenset({CODE_HOST}),
    )
    assert fake_gh.queries, "no searches issued"
    assert not any("type:issue" in q for q in fake_gh.queries)
    threads = [q for q in fake_gh.queries if "commenter:" in q]
    assert threads == ["repo:o/r type:pr commenter:alice created:<=2026-08-31 updated:>=2026-03-01"]


def test_both_sides_keep_the_historical_thread_search(fake_gh):  # noqa: F811
    fake_gh.responses = streams()
    fetch_items("o/r", "alice", since="2026-03-01", end="2026-08-31", phrases=(), maintainers=())
    assert "repo:o/r commenter:alice created:<=2026-08-31 updated:>=2026-03-01" in fake_gh.queries
    assert any("type:issue author:alice" in q for q in fake_gh.queries)


def test_code_host_side_keeps_pr_items(fake_gh):  # noqa: F811
    node = {
        "number": 7,
        "url": "https://github.com/o/r/pull/7",
        "state": "MERGED",
        "merged": True,
        "mergedAt": "2026-04-02T00:00:00Z",
        "createdAt": "2026-04-01T00:00:00Z",
        "labels": {"nodes": []},
    }
    fake_gh.responses = streams(**{"type:pr author:": search([node])})
    items, caps, _ = fetch_items(
        "o/r",
        "alice",
        since="2026-03-01",
        end="2026-08-31",
        phrases=(),
        maintainers=(),
        streams=frozenset({CODE_HOST}),
    )
    assert [i.id for i in items] == ["pr-7"]
    assert caps == []
