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
