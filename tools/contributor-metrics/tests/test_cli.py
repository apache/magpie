# SPDX-License-Identifier: Apache-2.0
# https://www.apache.org/licenses/LICENSE-2.0
import json

from contributor_metrics.cli import main


def test_score_cli_round_trip(tmp_path):
    items = {
        "login": "alice",
        "repo": "o/r",
        "since": "2026-03-01",
        "end": "2026-08-31",
        "caps_hit": [],
        "items": [
            {
                "id": "pr-1",
                "kind": "pr",
                "url": "u",
                "thread": "u",
                "created_at": "2026-04-01",
                "merged": True,
                "closed_unmerged": False,
                "substantive": False,
                "areas": ["area:a"],
                "pushback_candidate": "",
            }
        ],
    }
    (tmp_path / "items.json").write_text(json.dumps(items))
    (tmp_path / "classes.json").write_text(json.dumps({"pr-1": "P"}))
    (tmp_path / "weights.json").write_text(json.dumps({"automated_pushback_penalty": 0}))
    rc = main(
        [
            "score",
            "--items",
            str(tmp_path / "items.json"),
            "--classes",
            str(tmp_path / "classes.json"),
            "--weights",
            str(tmp_path / "weights.json"),
            "--out",
            str(tmp_path / "m.json"),
        ]
    )
    assert rc == 0
    out = json.loads((tmp_path / "m.json").read_text())
    assert out["metrics"]["prs_merged"]["adjusted"] == 0.25


def test_fetch_cli_invalid_login_exit_2(tmp_path):
    rc = main(
        [
            "fetch",
            "--repo",
            "o/r",
            "--login",
            "a b",
            "--end",
            "2026-08-31",
            "--months",
            "6",
            "--out",
            str(tmp_path / "x.json"),
        ]
    )
    assert rc == 2
    assert not (tmp_path / "x.json").exists()


def test_fetch_reuses_the_cache(tmp_path, monkeypatch):
    calls = []

    def fake_fetch(*a, **k):
        calls.append(1)
        return [], [], []

    monkeypatch.setattr("contributor_metrics.cli.fetch_items", fake_fetch)
    args = [
        "fetch",
        "--repo",
        "o/r",
        "--login",
        "alice",
        "--end",
        "2026-08-31",
        "--months",
        "6",
        "--cache-dir",
        str(tmp_path / "c"),
    ]
    assert main([*args, "--out", str(tmp_path / "a.json")]) == 0
    assert main([*args, "--out", str(tmp_path / "b.json")]) == 0
    assert len(calls) == 1
    assert json.loads((tmp_path / "a.json").read_text()) == json.loads((tmp_path / "b.json").read_text())


def test_score_since_scores_a_sub_window(tmp_path):
    def pr(n, d):
        return {
            "id": f"pr-{n}",
            "kind": "pr",
            "url": f"u{n}",
            "thread": f"u{n}",
            "created_at": d,
            "merged": True,
            "closed_unmerged": False,
            "substantive": False,
            "areas": [],
            "pushback_candidate": "",
        }

    items = {
        "login": "alice",
        "repo": "o/r",
        "since": "2025-09-01",
        "end": "2026-08-31",
        "caps_hit": [],
        "items": [pr(1, "2025-10-01"), pr(2, "2026-05-01")],
    }
    (tmp_path / "items.json").write_text(json.dumps(items))
    assert (
        main(
            [
                "score",
                "--items",
                str(tmp_path / "items.json"),
                "--since",
                "2026-03-01",
                "--out",
                str(tmp_path / "m.json"),
            ]
        )
        == 0
    )
    out = json.loads((tmp_path / "m.json").read_text())
    assert out["metrics"]["prs_merged"]["raw"] == 1
    assert out["window"]["since"] == "2026-03-01"


def test_floors_cli(tmp_path):
    rows = [
        {
            "target": "committer",
            "outcome": "elected",
            "vote_date": "2026-06-01",
            "metrics": {"prs_merged": p},
            "capped": [],
        }
        for p in (40, 48, 55, 60, 72)
    ]
    (tmp_path / "rows.json").write_text(json.dumps(rows))
    assert (
        main(
            [
                "floors",
                "--rows",
                str(tmp_path / "rows.json"),
                "--today",
                "2026-09-27",
                "--out",
                str(tmp_path / "f.json"),
            ]
        )
        == 0
    )
    assert json.loads((tmp_path / "f.json").read_text())["floors"]["committer"]["prs_merged"] == 36


def test_score_rejects_weights_that_are_not_an_object(tmp_path):
    (tmp_path / "items.json").write_text(
        json.dumps({"since": "2026-03-01", "end": "2026-08-31", "items": []})
    )
    (tmp_path / "w.json").write_text("[1, 2]")
    rc = main(
        [
            "score",
            "--items",
            str(tmp_path / "items.json"),
            "--weights",
            str(tmp_path / "w.json"),
            "--out",
            str(tmp_path / "m.json"),
        ]
    )
    assert rc == 2


def test_fetch_refresh_ignores_the_cache(tmp_path, monkeypatch):
    calls = []

    def fake_fetch(*a, **k):
        calls.append(1)
        return [], [], []

    monkeypatch.setattr("contributor_metrics.cli.fetch_items", fake_fetch)
    args = [
        "fetch",
        "--repo",
        "o/r",
        "--login",
        "alice",
        "--end",
        "2026-08-31",
        "--cache-dir",
        str(tmp_path / "c"),
        "--out",
        str(tmp_path / "a.json"),
    ]
    assert main(args) == 0
    assert main([*args, "--refresh"]) == 0
    assert len(calls) == 2


def test_fetch_cli_invalid_repo_exit_2(tmp_path):
    rc = main(
        [
            "fetch",
            "--repo",
            "norepo",
            "--login",
            "alice",
            "--end",
            "2026-08-31",
            "--cache-dir",
            str(tmp_path / "c"),
            "--out",
            str(tmp_path / "x.json"),
        ]
    )
    assert rc == 2


def _fetch_args(tmp_path, *extra):
    return [
        "fetch",
        "--repo",
        "o/r",
        "--login",
        "alice",
        "--end",
        "2026-08-31",
        "--cache-dir",
        str(tmp_path / "c"),
        "--out",
        str(tmp_path / "a.json"),
        *extra,
    ]


def test_fetch_since_overrides_months(tmp_path, monkeypatch):
    seen = {}

    def fake_fetch(*a, **k):
        seen.update(k)
        return [], [], []

    monkeypatch.setattr("contributor_metrics.cli.fetch_items", fake_fetch)
    assert main(_fetch_args(tmp_path, "--months", "6", "--since", "2026-07-15")) == 0
    assert seen["since"] == "2026-07-15"
    assert json.loads((tmp_path / "a.json").read_text())["since"] == "2026-07-15"


def test_fetch_rejects_a_bad_or_late_since(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "contributor_metrics.cli.fetch_items", lambda *a, **k: (_ for _ in ()).throw(AssertionError)
    )
    assert main(_fetch_args(tmp_path, "--since", "2026-13-01")) == 2
    assert main(_fetch_args(tmp_path, "--since", "2026-09-01")) == 2
    assert not (tmp_path / "a.json").exists()


def test_fetch_substantive_thresholds_reach_fetch_and_the_cache_key(tmp_path, monkeypatch):
    calls = []

    def fake_fetch(*a, **k):
        calls.append((k["substantive_body_chars"], k["substantive_line_comments"]))
        return [], [], []

    monkeypatch.setattr("contributor_metrics.cli.fetch_items", fake_fetch)
    assert main(_fetch_args(tmp_path)) == 0
    assert (
        main(_fetch_args(tmp_path, "--substantive-body-chars", "50", "--substantive-line-comments", "3")) == 0
    )
    assert calls == [(100, 1), (50, 3)]


JIRA_CONFIG = """# Issue tracker

| Key | Value |
|---|---|
| `url` | `https://issues.example.org/jira` |
| `project_key` | `FOO` |
| `tracker_type` | jira |
| `issue_url_template` | `https://issues.example.org/jira/browse/<KEY>` |
"""


def test_read_tracker_config_reads_the_url_table(tmp_path):
    from contributor_metrics.cli import read_tracker_config

    (tmp_path / "issue-tracker-config.md").write_text(JIRA_CONFIG)
    cfg = read_tracker_config(str(tmp_path / "issue-tracker-config.md"))
    assert cfg == {"url": "https://issues.example.org/jira", "project_key": "FOO", "tracker_type": "jira"}


def test_fetch_with_a_jira_tracker_config_routes_issues_to_jira(tmp_path, monkeypatch):
    (tmp_path / "issue-tracker-config.md").write_text(JIRA_CONFIG)
    seen = {}

    def fake_fetch(*a, **k):
        seen.update(k)
        return [], [], []

    monkeypatch.setattr("contributor_metrics.cli.fetch_items", fake_fetch)
    monkeypatch.delenv("JIRA_API_TOKEN", raising=False)
    rc = main(
        _fetch_args(
            tmp_path,
            "--tracker-config",
            str(tmp_path / "issue-tracker-config.md"),
            "--tracker-login",
            "jdoe",
        )
    )
    assert rc == 0
    tracker = seen["tracker"]
    assert (tracker.url, tracker.project) == ("https://issues.example.org/jira", "FOO")
    assert seen["tracker_login"] == "jdoe"
    out = json.loads((tmp_path / "a.json").read_text())
    assert out["backends"] == {
        "code_host": "github",
        "tracker": "jira",
        "tracker_url": "https://issues.example.org/jira",
        "tracker_project": "FOO",
        "tracker_login": "jdoe",
    }


def test_flags_override_the_tracker_config(tmp_path, monkeypatch):
    (tmp_path / "issue-tracker-config.md").write_text(JIRA_CONFIG)
    seen = {}
    monkeypatch.setattr("contributor_metrics.cli.fetch_items", lambda *a, **k: seen.update(k) or ([], [], []))
    args = _fetch_args(
        tmp_path,
        "--tracker-config",
        str(tmp_path / "issue-tracker-config.md"),
        "--jira-project",
        "BAR",
    )
    assert main(args) == 0
    assert seen["tracker"].project == "BAR"


def test_github_only_fetch_output_has_no_backends_key(tmp_path, monkeypatch):
    seen = {}
    monkeypatch.setattr("contributor_metrics.cli.fetch_items", lambda *a, **k: seen.update(k) or ([], [], []))
    assert main(_fetch_args(tmp_path)) == 0
    assert "tracker" not in seen
    assert "backends" not in json.loads((tmp_path / "a.json").read_text())


def test_github_issues_config_for_the_same_repo_is_the_default(tmp_path, monkeypatch):
    (tmp_path / "c.md").write_text("| `tracker_type` | github-issues |\n| `project_key` | `o/r` |\n")
    seen = {}
    monkeypatch.setattr("contributor_metrics.cli.fetch_items", lambda *a, **k: seen.update(k) or ([], [], []))
    assert main(_fetch_args(tmp_path, "--tracker-config", str(tmp_path / "c.md"))) == 0
    assert "tracker" not in seen


def test_unsupported_tracker_type_exits_2(tmp_path, monkeypatch):
    (tmp_path / "c.md").write_text("| `tracker_type` | bugzilla |\n")
    monkeypatch.setattr(
        "contributor_metrics.cli.fetch_items", lambda *a, **k: (_ for _ in ()).throw(AssertionError)
    )
    assert main(_fetch_args(tmp_path, "--tracker-config", str(tmp_path / "c.md"))) == 2


def test_jira_without_url_exits_2(tmp_path, monkeypatch):
    monkeypatch.delenv("ISSUE_TRACKER_URL", raising=False)
    monkeypatch.delenv("ISSUE_TRACKER_PROJECT", raising=False)
    assert main(_fetch_args(tmp_path, "--tracker", "jira")) == 2


def test_the_tracker_is_part_of_the_cache_key(tmp_path, monkeypatch):
    (tmp_path / "issue-tracker-config.md").write_text(JIRA_CONFIG)
    calls = []

    def fake_fetch(*a, **k):
        calls.append(k)
        return [], [], []

    monkeypatch.setattr("contributor_metrics.cli.fetch_items", fake_fetch)
    assert main(_fetch_args(tmp_path)) == 0
    assert main(_fetch_args(tmp_path, "--tracker-config", str(tmp_path / "issue-tracker-config.md"))) == 0
    assert len(calls) == 2
