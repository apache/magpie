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
