# SPDX-License-Identifier: Apache-2.0
# https://www.apache.org/licenses/LICENSE-2.0
import json

import pytest

from contributor_metrics.cli import main
from contributor_metrics.fetch import InvalidRepo, fetch_items
from contributor_metrics.model import Item
from contributor_metrics.repos import active_repos, belongs_to


def counts(table):
    """A fake search_count answering from {repo: (merged, opened)}; an unknown repo searches empty."""

    def count(q):
        repo = q.split()[0].removeprefix("repo:")
        merged, opened = table.get(repo, (0, 0))
        return merged if "is:merged" in q else opened

    return count


def test_belongs_to_keeps_the_slug_and_its_dash_prefix_only():
    assert belongs_to("airflow", "airflow")
    assert belongs_to("Airflow-Site", "airflow")
    assert not belongs_to("nutch-airflow-tools", "airflow")
    assert not belongs_to("airflowctl", "airflow")


def test_active_repos_sorts_every_candidate_into_one_list():
    names = ["airflow", "airflow-site.git", "airflow-ci", "nutch-airflow-tools", "airflow-gone", "bad name"]
    count = counts({"apache/airflow": (40, 90), "apache/airflow-site": (0, 3), "apache/airflow-ci": (0, 0)})
    out = active_repos("apache", "airflow", names, since="2026-05-01", end="2026-10-31", count=count)
    assert [r["repo"] for r in out["active"]] == ["apache/airflow", "apache/airflow-site"]
    assert out["active"][1] == {"repo": "apache/airflow-site", "merged_prs": 0, "opened": 3}
    assert [r["repo"] for r in out["inactive"]] == ["apache/airflow-ci", "apache/airflow-gone"]
    assert out["excluded_by_name"] == ["nutch-airflow-tools"]
    assert out["invalid_names"] == ["bad name"]


def test_active_repos_cli(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "contributor_metrics.repos.search_count",
        counts(
            {"apache/magpie": (300, 400), "apache/magpie-site": (12, 15), "apache/magpie-economics": (0, 0)}
        ),
    )
    (tmp_path / "names.txt").write_text("magpie\nmagpie-economics\nmagpie-site\n")
    rc = main(
        [
            "active-repos",
            "--owner",
            "apache",
            "--project",
            "magpie",
            "--names-file",
            str(tmp_path / "names.txt"),
            "--end",
            "2026-10-31",
            "--out",
            str(tmp_path / "out.json"),
        ]
    )
    assert rc == 0
    out = json.loads((tmp_path / "out.json").read_text())
    assert out["since"] == "2026-04-28"
    assert [r["repo"] for r in out["active"]] == ["apache/magpie", "apache/magpie-site"]
    assert [r["repo"] for r in out["inactive"]] == ["apache/magpie-economics"]


def test_active_repos_cli_rejects_a_bad_project(tmp_path):
    (tmp_path / "names.txt").write_text("x")
    rc = main(
        [
            "active-repos",
            "--owner",
            "apache",
            "--project",
            "a b",
            "--names-file",
            str(tmp_path / "names.txt"),
            "--end",
            "2026-10-31",
            "--out",
            str(tmp_path / "out.json"),
        ]
    )
    assert rc == 2


def _item(n):
    return Item(id=f"pr-{n}", kind="pr", url=f"u{n}", thread=f"u{n}", created_at="2026-06-01", merged=True)


def test_fetch_many_prefixes_ids_and_merges_caps_and_notes(monkeypatch):
    seen = []

    def fake(repo, login, **kw):
        seen.append((repo, kw["streams"]))
        if repo == "apache/a":
            return [_item(1)], ["prs_opened"], ["a note"]
        return [_item(1)], ["prs_opened", "reviews_total"], []

    monkeypatch.setattr("contributor_metrics.fetch.github_fetch_items", fake)
    items, caps, notes = fetch_items(
        ["apache/a", "apache/a-site", "apache/a"],
        "alice",
        since="2026-05-01",
        end="2026-10-31",
        phrases=[],
        maintainers=[],
    )
    assert [r for r, _ in seen] == ["apache/a", "apache/a-site"]
    assert all(len(streams) == 2 for _, streams in seen)  # code host and tracker
    assert [i.id for i in items] == ["apache/a:pr-1", "apache/a-site:pr-1"]
    assert caps == ["prs_opened", "reviews_total"]
    assert notes == ["apache/a: a note"]


def test_fetch_many_with_a_tracker_asks_the_code_host_only(monkeypatch):
    seen = []

    def fake(repo, login, **kw):
        seen.append(kw["streams"])
        return [], [], []

    monkeypatch.setattr("contributor_metrics.fetch.github_fetch_items", fake)

    class Tracker:
        def fetch(self, login, **kw):
            return [Item(id="issue-X-1", kind="issue", url="j", thread="j", created_at="2026-06-01")], [], []

    items, _, _ = fetch_items(
        ["apache/a", "apache/a-site"],
        "alice",
        since="2026-05-01",
        end="2026-10-31",
        phrases=[],
        maintainers=[],
        tracker=Tracker(),
    )
    assert all(len(s) == 1 for s in seen)
    assert [i.id for i in items] == ["issue-X-1"]


def test_fetch_many_validates_every_repo():
    with pytest.raises(InvalidRepo):
        fetch_items(
            ["apache/a", "bad"], "alice", since="2026-05-01", end="2026-10-31", phrases=[], maintainers=[]
        )


def test_fetch_cli_with_two_repos_records_them_and_keys_the_cache(tmp_path, monkeypatch):
    seen = []

    def fake(repo, *a, **k):
        seen.append(repo)
        return [], [], []

    monkeypatch.setattr("contributor_metrics.cli.fetch_items", fake)
    base = ["fetch", "--login", "alice", "--end", "2026-10-31", "--cache-dir", str(tmp_path / "c")]
    assert main([*base, "--repo", "apache/a", "--out", str(tmp_path / "one.json")]) == 0
    assert (
        main([*base, "--repo", "apache/a", "--repo", "apache/a-site", "--out", str(tmp_path / "two.json")])
        == 0
    )
    assert seen == ["apache/a", ["apache/a", "apache/a-site"]]
    one = json.loads((tmp_path / "one.json").read_text())
    two = json.loads((tmp_path / "two.json").read_text())
    assert "repos" not in one
    assert two["repo"] == "apache/a" and two["repos"] == ["apache/a", "apache/a-site"]
    assert len(list((tmp_path / "c").iterdir())) == 2
