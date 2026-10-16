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
"""release-archive-sweep: the Step 0 verdict, trains.json, the retention rule and the Step 2 command set.

The retention cases moved from `archive-sweep/tests/test_retention.py` unchanged.
The scripted cases of the retired model-graded suites `step-0-preflight`
(cases 2 to 4), `step-1-load-listing` (cases 1 to 3) and `step-2-emit-commands`
(cases 1 and 2) live here, named after each former case, with the same scenario
and the same assertions.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest

from release_management.archive_sweep import render, retention
from release_management.cli import main

TWO_X = [{"label": "2.x", "pattern": "2.x"}]
ORPHAN_REASON = (
    "1.10.15 is not listed in release-trains.md and is an orphan; no archival command will be proposed "
    "for it — the RM must decide whether to archive, keep, or reconcile it into a known train"
)


def loaded(
    *,
    backend: str = "svnpubsub",
    template: str = "https://dist.apache.org/repos/dist/<bucket>/airflow/<version>",
    archive: str | None = "https://archive.apache.org/dist/airflow/<version>",
    project: str | None = "airflow",
    lines: list[str] | None = None,
    rule: str = "latest_of_each_supported_line",
) -> dict[str, Any]:
    config: dict[str, Any] = {
        "release_dist_backend": backend,
        "release_dist_url_template": template,
        "archive_retention_rule": rule,
    }
    if archive:
        config["archive_url_template"] = archive
    if project:
        config["project_dist_name"] = project
    return {
        "config": config,
        "derived": {
            "non_asf": backend not in ("svnpubsub", "atr"),
            "release_lines": lines
            if lines is not None
            else ["**`v2-11-stable`** — the 2.x train, supported; latest `2.11.0`."],
        },
    }


def sweep_of(**kwargs: Any) -> render.Sweep:
    upstream = kwargs.pop("upstream", None)
    return render.Sweep.from_load(loaded(**kwargs), upstream=upstream)


def run(listing: str, trains: list[dict[str, Any]]) -> dict[str, Any]:
    versions, other = retention.parse_listing(listing)
    out = retention.sweep(versions, trains)
    out["non_version_entries"] = other
    return out


# --------------------------------------------------------------------------- retention (moved)


class TestSort:
    def test_numeric_not_lexical(self) -> None:
        assert sorted(["2.10.0", "2.9.0", "2.11.0"], key=retention.version_key) == [
            "2.9.0",
            "2.10.0",
            "2.11.0",
        ]

    def test_prerelease_before_final_and_post_after(self) -> None:
        assert sorted(["3.0.0.post1", "3.0.0", "3.0.0rc1"], key=retention.version_key) == [
            "3.0.0rc1",
            "3.0.0",
            "3.0.0.post1",
        ]

    def test_incubating_is_a_release_qualifier_not_a_prerelease(self) -> None:
        assert not retention.is_prerelease("1.3.0-incubating")
        assert retention.is_prerelease("1.3.0-rc1-incubating")
        assert retention.is_prerelease("1.3.0-incubating-rc1")
        assert sorted(
            ["1.3.0-incubating", "1.3.0-incubating-rc1", "1.2.0-incubating", "1.10.0-incubating"],
            key=retention.version_key,
        ) == ["1.2.0-incubating", "1.3.0-incubating-rc1", "1.3.0-incubating", "1.10.0-incubating"]

    def test_listing_drops_slash_and_separates_non_versions(self) -> None:
        assert retention.parse_listing("2.10.0/\nKEYS\n\nproviders/\n") == (["2.10.0"], ["KEYS", "providers"])


class TestSweep:
    def test_single_line(self) -> None:
        out = retention.sweep(["2.11.0", "2.10.0"], TWO_X)
        assert out["releases_found"] == ["2.10.0", "2.11.0"]
        assert out["past_retention"] == ["2.10.0"]
        assert out["latest_of_each_line"] == {"2.x": "2.11.0"}
        assert not out["handoff_required"]
        assert out["handoff_reasons"] == []

    def test_multi_line(self) -> None:
        trains = [*TWO_X, {"label": "3.x", "pattern": "3.x"}]
        out = retention.sweep(["2.9.0", "2.10.0", "2.11.0", "3.0.0", "3.0.1"], trains)
        assert out["past_retention"] == ["2.9.0", "2.10.0", "3.0.0"]
        assert out["latest_of_each_line"] == {"2.x": "2.11.0", "3.x": "3.0.1"}

    def test_orphan_listed_never_archived(self) -> None:
        out = retention.sweep(["2.10.0", "2.11.0", "1.10.15"], TWO_X)
        assert out["orphans"] == ["1.10.15"]
        assert "1.10.15" not in out["past_retention"]
        assert out["handoff_required"]
        assert "1.10.15" in out["handoff_reasons"][0]

    def test_keep_two(self) -> None:
        out = retention.sweep(["2.9.0", "2.10.0", "2.11.0"], [{"label": "2.x", "pattern": "2.x", "keep": 2}])
        assert out["past_retention"] == ["2.9.0"]

    def test_keep_zero_is_retention_rule_error(self) -> None:
        out = retention.sweep(["2.10.0", "2.11.0"], [{"label": "2.x", "pattern": "2.x", "keep": 0}])
        assert out["retention_rule_error"]
        assert out["past_retention"] == []
        assert out["handoff_required"]

    def test_loose_pattern_goes_unmapped(self) -> None:
        out = retention.sweep(["1.0.0", "2.0.0"], [{"label": "LTS", "pattern": "long-term support line"}])
        assert [u["version"] for u in out["unmapped"]] == ["1.0.0", "2.0.0"]
        assert not out["mapping_complete"]
        assert out["orphans"] == []

    def test_explicit_versions_resolve_loose_train(self) -> None:
        out = retention.sweep(["1.0.0", "1.1.0", "2.0.0"], [{"label": "LTS", "versions": ["1.0.0", "1.1.0"]}])
        assert out["past_retention"] == ["1.0.0"]
        assert out["orphans"] == ["2.0.0"]

    def test_overlapping_patterns_go_unmapped(self) -> None:
        trains = [*TWO_X, {"label": "2.11", "pattern": "2.11.x"}]
        out = retention.sweep(["2.11.0"], trains)
        assert out["unmapped"][0]["version"] == "2.11.0"


class TestPrerelease:
    """A pre-release in the release area never decides what is kept."""

    def test_rc_never_displaces_the_latest_release(self) -> None:
        out = retention.sweep(["2.10.5", "2.11.0-rc1", "2.10.4"], TWO_X)
        assert out["latest_of_each_line"] == {"2.x": "2.10.5"}
        assert out["past_retention"] == ["2.10.4"]
        assert "2.10.5" not in out["past_retention"]
        assert "2.11.0-rc1" not in out["past_retention"]

    def test_prerelease_is_handed_to_the_rm(self) -> None:
        out = retention.sweep(["2.10.5", "2.11.0rc1"], TWO_X)
        assert out["prereleases"] == ["2.11.0rc1"]
        assert out["handoff_required"]
        assert any("2.11.0rc1" in r and "pre-release" in r for r in out["handoff_reasons"])

    def test_podling_archives_its_older_incubating_releases(self) -> None:
        out = retention.sweep(
            ["1.2.0-incubating", "1.3.0-incubating", "1.4.0-rc1-incubating"],
            [{"label": "1.x", "pattern": "1.x"}],
        )
        assert out["latest_of_each_line"] == {"1.x": "1.3.0-incubating"}
        assert out["past_retention"] == ["1.2.0-incubating"]
        assert out["prereleases"] == ["1.4.0-rc1-incubating"]

    def test_post_release_still_counts_as_a_release(self) -> None:
        out = retention.sweep(["2.10.5", "2.10.5.post1"], TWO_X)
        assert out["latest_of_each_line"] == {"2.x": "2.10.5.post1"}
        assert out["prereleases"] == []


# --------------------------------------------------------------------------- step-0-preflight


def preflight(blockers: list[str], *, non_asf: bool, backend: str) -> dict[str, Any]:
    return {
        "ok": not blockers,
        "skill": "archive-sweep",
        "blockers": blockers,
        "warnings": [],
        "values": {"non_asf": non_asf, "dist_backend": backend},
    }


def test_step0_case_2_retention_rule_error() -> None:
    """A missing `archive_retention_rule` key blocks (the case name predates the rule's own error)."""
    blocker = "required key `archive_retention_rule` is missing from release-management-config.md"
    out = render.verdict(preflight([blocker], non_asf=False, backend="svnpubsub"))
    assert out == {"verdict": "blocked", "blockers": [blocker], "non_asf": False, "dist_backend": "svnpubsub"}


def test_step0_case_3_missing_config() -> None:
    blockers = [
        "release-trains.md not found in <project-config> (looked in .apache-magpie-local/ then .apache-magpie-overrides/)",
        "archive destination for github-releases backend is not configured (archive_url_template missing)",
    ]
    out = render.verdict(preflight(blockers, non_asf=True, backend="github-releases"))
    assert out["verdict"] == "blocked"
    assert out["blockers"] == blockers
    assert (out["non_asf"], out["dist_backend"]) == (True, "github-releases")


def test_step0_case_4_atr_backend() -> None:
    out = render.verdict(preflight([], non_asf=False, backend="atr"))
    assert out == {"verdict": "proceed", "blockers": [], "non_asf": False, "dist_backend": "atr"}


# --------------------------------------------------------------------------- Step 1: listing and trains


def test_listing_svnpubsub_lists_the_release_directory() -> None:
    out = render.listing(sweep_of())
    assert out["command"] == "svn list https://dist.apache.org/repos/dist/release/airflow/"
    assert out["read"] == "backends/svnpubsub.md"


def test_listing_other_backends() -> None:
    gh = render.listing(sweep_of(backend="github-releases", upstream="example-org/myproject"))
    assert gh["command"] == "gh release list --repo example-org/myproject --exclude-drafts"
    s3 = render.listing(
        sweep_of(
            backend="s3", template="s3://releases/myproject/<version>/", archive="s3://archive/myproject/"
        )
    )
    assert s3["command"] == "aws s3 ls s3://releases/myproject/"
    atr = render.listing(sweep_of(backend="atr", archive=None))
    assert atr["command"] is None and "ATR" in atr["note"]
    assert render.listing(sweep_of(backend="self-hosted"))["command"] is None


def test_trains_from_strict_bullets() -> None:
    out = render.trains(
        sweep_of(
            lines=[
                "**`v2-11-stable`** — the 2.x train, supported; latest `2.11.0`.",
                "**`main`** — the 3.x train, supported; latest `3.0.0`.",
            ]
        )
    )
    assert out["trains"] == [{"label": "2.x", "pattern": "2.x"}, {"label": "3.x", "pattern": "3.x"}]
    assert out["loose"] == [] and out["keep_decided"] is True


def test_trains_loose_bullet_and_free_text_rule_go_to_the_agent() -> None:
    out = render.trains(sweep_of(lines=["**`lts`** — the long-term support line"], rule="keep two per line"))
    assert out["trains"] == [{"label": "lts", "pattern": "**`lts`** — the long-term support line"}]
    assert out["loose"] == ["lts"]
    assert out["keep_decided"] is False and len(out["notes"]) == 2


def test_trains_keep_flag() -> None:
    out = render.trains(sweep_of(rule="keep two per line"), keep=2)
    assert out["trains"] == [{"label": "2.x", "pattern": "2.x", "keep": 2}] and out["keep_decided"]


# --------------------------------------------------------------------------- step-1-load-listing


def _step1(listing: str, trains: list[dict[str, Any]]) -> dict[str, Any]:
    out = run(listing, trains)
    keys = (
        "releases_found",
        "past_retention",
        "orphans",
        "latest_of_each_line",
        "handoff_required",
        "handoff_reasons",
    )
    return {k: out[k] for k in keys}


def test_step1_case_1_single_line_one_old() -> None:
    assert _step1("2.10.0/\n2.11.0/\n", TWO_X) == {
        "releases_found": ["2.10.0", "2.11.0"],
        "past_retention": ["2.10.0"],
        "orphans": [],
        "latest_of_each_line": {"2.x": "2.11.0"},
        "handoff_required": False,
        "handoff_reasons": [],
    }


def test_step1_case_2_multi_line_mixed() -> None:
    trains = [*TWO_X, {"label": "3.x", "pattern": "3.x"}]
    assert _step1("2.9.0/\n2.10.0/\n2.11.0/\n3.0.0/\n3.0.1/\n", trains) == {
        "releases_found": ["2.9.0", "2.10.0", "2.11.0", "3.0.0", "3.0.1"],
        "past_retention": ["2.9.0", "2.10.0", "3.0.0"],
        "orphans": [],
        "latest_of_each_line": {"2.x": "2.11.0", "3.x": "3.0.1"},
        "handoff_required": False,
        "handoff_reasons": [],
    }


def test_step1_case_3_orphan_detected() -> None:
    assert _step1("2.10.0/\n2.11.0/\n1.10.15/\n", TWO_X) == {
        "releases_found": ["1.10.15", "2.10.0", "2.11.0"],
        "past_retention": ["2.10.0"],
        "orphans": ["1.10.15"],
        "latest_of_each_line": {"2.x": "2.11.0"},
        "handoff_required": True,
        "handoff_reasons": [ORPHAN_REASON],
    }


# --------------------------------------------------------------------------- step-2-emit-commands


def test_step2_case_1_svn_backend() -> None:
    out = render.step2(sweep_of(), run("2.9.0/\n2.10.0/\n2.11.0/\n", TWO_X))
    assert (out["archive_count"], out["backend"], out["proposed"]) == (2, "svnpubsub", True)
    commands = out["commands"]
    assert re.search(r"svn mv", commands, re.I)
    assert re.search(r"archive\.apache\.org", commands, re.I)
    assert re.search(r"-m .*(archive|retention)", commands, re.I)
    assert commands == (
        "```text\n"
        "svn mv \\\n"
        "  https://dist.apache.org/repos/dist/release/airflow/2.9.0 \\\n"
        "  https://archive.apache.org/dist/airflow/2.9.0 \\\n"
        '  -m "Archive airflow 2.9.0 per retention policy"\n'
        "\n"
        "svn mv \\\n"
        "  https://dist.apache.org/repos/dist/release/airflow/2.10.0 \\\n"
        "  https://archive.apache.org/dist/airflow/2.10.0 \\\n"
        '  -m "Archive airflow 2.10.0 per retention policy"\n'
        "```"
    )
    # No `\  # comment` continuation: every backslash ends its line.
    assert all(not ln.rstrip().endswith("#") and "\\ " not in ln for ln in commands.splitlines())


def test_step2_case_2_github_releases_backend() -> None:
    sweep = sweep_of(
        backend="github-releases",
        template="https://github.com/example-org/myproject/releases/tag/<version>",
        archive=None,
        project="myproject",
        upstream="example-org/myproject",
        lines=["**`main`** — the 1.x train, supported; latest `1.2.0`."],
    )
    out = render.step2(sweep, run("1.0.0\n1.1.0\n1.2.0\n", [{"label": "1.x", "pattern": "1.x"}]))
    assert (out["archive_count"], out["backend"], out["proposed"]) == (2, "github-releases", True)
    assert re.search(r"gh release delete", out["commands"], re.I)
    assert "gh release delete 1.0.0 --repo example-org/myproject --yes" in out["commands"]
    assert "1.2.0" not in out["commands"]
    assert "permanently" in out["deletion_warning"]


# --------------------------------------------------------------------------- Step 2: the other paths


def test_step2_archive_url_default_and_without_version_segment() -> None:
    out = render.step2(sweep_of(archive=None), run("2.10.0\n2.11.0\n", TWO_X))
    assert "https://archive.apache.org/dist/airflow/2.10.0 \\" in out["commands"]


def test_step2_atr_emits_no_shell_command() -> None:
    out = render.step2(sweep_of(backend="atr", archive=None), run("2.10.0\n2.11.0\n", TWO_X))
    assert out["archive_count"] == 1 and out["backend"] == "atr"
    assert not any(ln.startswith("svn") for ln in out["commands"].splitlines())
    assert "#   2.10.0" in out["commands"]
    assert "Auto archive prior release" in out["atr_note"]


def test_step2_s3() -> None:
    sweep = sweep_of(
        backend="s3", template="s3://releases/myproject/<version>/", archive="s3://archive/myproject/"
    )
    out = render.step2(sweep, run("2.10.0\n2.11.0\n", TWO_X))
    assert out["commands"] == (
        "```text\naws s3 mv \\\n  s3://releases/myproject/2.10.0/ \\\n"
        "  s3://archive/myproject/2.10.0/ \\\n  --recursive\n```"
    )


def test_step2_s3_https_template() -> None:
    sweep = sweep_of(
        backend="s3",
        template="https://releases.s3.eu-west-1.amazonaws.com/myproject/<version>/",
        archive="https://s3.eu-west-1.amazonaws.com/archive/myproject/<version>/",
    )
    out = render.step2(sweep, run("2.10.0\n2.11.0\n", TWO_X))
    assert "s3://releases/myproject/2.10.0/" in out["commands"]
    assert "s3://archive/myproject/2.10.0/" in out["commands"]


def test_step2_self_hosted_needs_a_template() -> None:
    sweep = sweep_of(backend="self-hosted", archive="https://archive.example.org/p/")
    with pytest.raises(render.RenderError, match="--command-template"):
        render.step2(sweep, run("2.10.0\n2.11.0\n", TWO_X))
    out = render.step2(
        sweep, run("2.10.0\n2.11.0\n", TWO_X), command_template="rsync-archive <ver> <archive-url>"
    )
    assert "rsync-archive 2.10.0 https://archive.example.org/p/2.10.0" in out["commands"]


def test_step2_refuses_a_retention_rule_error_and_unmapped_versions() -> None:
    with pytest.raises(render.RenderError, match="retention-rule-error"):
        render.step2(sweep_of(), run("2.10.0\n2.11.0\n", [{"label": "2.x", "pattern": "2.x", "keep": 0}]))
    with pytest.raises(render.RenderError, match="unmapped"):
        render.step2(sweep_of(), run("1.0.0\n", [{"label": "LTS", "pattern": "lts"}]))


def test_step2_orphans_and_prereleases_are_never_archived() -> None:
    out = render.step2(sweep_of(), run("1.10.15\n2.10.0\n2.11.0\n2.12.0rc1\n", TWO_X))
    assert out["versions"] == ["2.10.0"]
    assert "1.10.15" not in out["commands"] and "2.12.0rc1" not in out["commands"]
    assert out["not_archived"] == ["1.10.15", "2.12.0rc1"]
    assert "outcomes/orphans.md" in out["read"]


def test_step2_refuses_a_retention_output_without_mapping_complete() -> None:
    ret = run("2.10.0\n2.11.0\n", TWO_X)
    del ret["mapping_complete"]
    with pytest.raises(render.RenderError, match="mapping_complete is absent"):
        render.step2(sweep_of(), ret)


@pytest.mark.parametrize(
    ("version", "why"),
    [("2.11.0", "the latest of its line"), ("1.10.15", "an orphan"), ("2.12.0rc1", "a pre-release")],
)
def test_step2_refuses_past_retention_naming_a_kept_version(version: str, why: str) -> None:
    """A hand-edited (or otherwise inconsistent) retention output never archives what must stay."""
    ret = run("1.10.15\n2.10.0\n2.11.0\n2.12.0rc1\n", TWO_X)
    ret["past_retention"] = [*ret["past_retention"], version]
    with pytest.raises(render.RenderError, match=re.escape(f"{version} ({why})")):
        render.step2(sweep_of(), ret)


def test_step2_nothing_past_retention() -> None:
    out = render.step2(sweep_of(), run("2.11.0\n", TWO_X))
    assert out["archive_count"] == 0 and "Nothing is past retention" in out["commands"]


def test_step2_quotes_every_spliced_value() -> None:
    sweep = sweep_of(
        project="air$(id)flow", template="https://dist.apache.org/repos/dist/<bucket>/<project>/<version>"
    )
    out = render.step2(sweep, run("2.10.0\n2.11.0\n", TWO_X))
    assert '-m "Archive air\\$(id)flow 2.10.0 per retention policy"' in out["commands"]
    assert "'https://dist.apache.org/repos/dist/release/air$(id)flow/2.10.0'" in out["commands"]


# --------------------------------------------------------------------------- CLI


def test_cli_round_trip(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    load = tmp_path / "load.json"
    load.write_text(json.dumps(loaded()), encoding="utf-8")
    assert main(["archive-sweep", "trains", "--load", str(load)]) == 0
    trains = tmp_path / "trains.json"
    trains.write_text(capsys.readouterr().out, encoding="utf-8")
    listing = tmp_path / "listing.txt"
    listing.write_text("2.10.0/\n2.11.0/\nKEYS\n", encoding="utf-8")
    assert main(["archive-sweep", "retention", "--listing", str(listing), "--trains", str(trains)]) == 0
    ret = tmp_path / "retention.json"
    ret.write_text(capsys.readouterr().out, encoding="utf-8")
    assert json.loads(ret.read_text())["non_version_entries"] == ["KEYS"]
    assert main(["archive-sweep", "render", "--load", str(load), "--retention", str(ret)]) == 0
    assert json.loads(capsys.readouterr().out)["archive_count"] == 1


def test_cli_refusal_and_bad_input(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    load = tmp_path / "load.json"
    load.write_text(json.dumps(loaded(backend="self-hosted")), encoding="utf-8")
    ret = tmp_path / "retention.json"
    ret.write_text(json.dumps(run("2.10.0\n2.11.0\n", TWO_X)), encoding="utf-8")
    assert main(["archive-sweep", "render", "--load", str(load), "--retention", str(ret)]) == 2
    assert json.loads(capsys.readouterr().out)["ok"] is False
    empty = tmp_path / "trains.json"
    empty.write_text("[]", encoding="utf-8")
    assert main(["archive-sweep", "retention", "--listing", str(ret), "--trains", str(empty)]) == 2
    assert "error" in json.loads(capsys.readouterr().out)


def test_cli_free_text_rule_trains_to_retention(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """`keep last two of each line`: retention refuses the undecided trains instead of keeping one."""
    load = tmp_path / "load.json"
    load.write_text(json.dumps(loaded(rule="keep last two of each line")), encoding="utf-8")
    listing = tmp_path / "listing.txt"
    listing.write_text("2.9.0/\n2.10.0/\n2.11.0/\n", encoding="utf-8")
    trains = tmp_path / "trains.json"

    assert main(["archive-sweep", "trains", "--load", str(load)]) == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["keep_decided"] is False and "keep" not in printed["trains"][0]
    trains.write_text(json.dumps(printed), encoding="utf-8")
    assert main(["archive-sweep", "retention", "--listing", str(listing), "--trains", str(trains)]) == 2
    out = json.loads(capsys.readouterr().out)
    assert "keep_decided is false" in out["error"] and "past_retention" not in out

    # The agent decides per train: an explicit keep on every train is accepted.
    printed["trains"][0]["keep"] = 2
    trains.write_text(json.dumps(printed), encoding="utf-8")
    assert main(["archive-sweep", "retention", "--listing", str(listing), "--trains", str(trains)]) == 0
    assert json.loads(capsys.readouterr().out)["past_retention"] == ["2.9.0"]

    # Or re-runs trains with --keep 2.
    assert main(["archive-sweep", "trains", "--load", str(load), "--keep", "2"]) == 0
    trains.write_text(capsys.readouterr().out, encoding="utf-8")
    assert main(["archive-sweep", "retention", "--listing", str(listing), "--trains", str(trains)]) == 0
    assert json.loads(capsys.readouterr().out)["past_retention"] == ["2.9.0"]

    # A bare list keeps its current meaning: keep defaults to 1.
    trains.write_text(json.dumps(TWO_X), encoding="utf-8")
    assert main(["archive-sweep", "retention", "--listing", str(listing), "--trains", str(trains)]) == 0
    assert json.loads(capsys.readouterr().out)["past_retention"] == ["2.9.0", "2.10.0"]


# --------------------------------------------------------------------------- S3 locations (shared with release-promote)


@pytest.mark.parametrize(
    ("template", "listed", "moved"),
    [
        # A virtual-hosted bucket whose own name starts with `s3`: the key keeps `foo`.
        (
            "https://s3-releases.s3.eu-west-1.amazonaws.com/foo/<version>/",
            "s3://s3-releases/foo/",
            "s3://s3-releases/foo/1.0.0/",
        ),
        (
            "https://s3.eu-west-1.amazonaws.com/releases/foo/<version>/",
            "s3://releases/foo/",
            "s3://releases/foo/1.0.0/",
        ),
        (
            "https://s3-eu-west-1.amazonaws.com/releases/foo/<version>/",
            "s3://releases/foo/",
            "s3://releases/foo/1.0.0/",
        ),
        ("s3://s3-releases/foo/<version>/", "s3://s3-releases/foo/", "s3://s3-releases/foo/1.0.0/"),
    ],
)
def test_s3_bucket_and_key_follow_release_promote(template: str, listed: str, moved: str) -> None:
    sweep = sweep_of(backend="s3", template=template, archive="s3://archive/foo/")
    assert render.listing(sweep)["command"] == f"aws s3 ls {listed}"
    out = render.step2(sweep, run("1.0.0\n1.1.0\n", [{"label": "1.x", "pattern": "1.x"}]))
    assert f"  {moved} \\\n  s3://archive/foo/1.0.0/ \\\n  --recursive" in out["commands"]


def test_s3_unreadable_bucket_is_refused_by_archive_sweep() -> None:
    sweep = sweep_of(backend="s3", template="https://example.org/foo/<version>/", archive="s3://archive/foo/")
    with pytest.raises(render.RenderError, match="cannot read the S3 bucket"):
        render.listing(sweep)


# --------------------------------------------------------------------------- literal text around <version>

V_TEMPLATE = "https://dist.apache.org/repos/dist/<bucket>/foo/v<version>/"
ONE_X = [{"label": "1.x", "pattern": "1.x"}]


def test_release_dir_cuts_at_the_segment_holding_version() -> None:
    sweep = sweep_of(template=V_TEMPLATE, project="foo", archive=None)
    assert sweep.release_dir() == "https://dist.apache.org/repos/dist/release/foo/"
    assert sweep.entry_affix == ("v", "")
    assert render.listing(sweep)["command"] == "svn list https://dist.apache.org/repos/dist/release/foo/"
    rc = sweep_of(
        template="https://dist.apache.org/repos/dist/<bucket>/foo/foo-<version>-<rcN>/", project="foo"
    )
    assert (rc.release_dir(), rc.entry_affix) == (
        "https://dist.apache.org/repos/dist/release/foo/",
        ("foo-", ""),
    )


def test_prefixed_entries_map_to_versions_and_back(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    load = loaded(template=V_TEMPLATE, project="foo", archive=None, lines=["the 1.x train"])
    trains_file = tmp_path / "trains.json"
    load_file = tmp_path / "load.json"
    load_file.write_text(json.dumps(load), encoding="utf-8")
    assert main(["archive-sweep", "trains", "--load", str(load_file)]) == 0
    trains = json.loads(capsys.readouterr().out)
    assert (trains["entry_prefix"], trains["entry_suffix"]) == ("v", "")
    trains_file.write_text(json.dumps(trains), encoding="utf-8")
    listing_file = tmp_path / "listing.txt"
    listing_file.write_text("v1.0.0/\nv1.1.0/\nKEYS\n1.2.0/\n", encoding="utf-8")
    assert (
        main(["archive-sweep", "retention", "--listing", str(listing_file), "--trains", str(trains_file)])
        == 0
    )
    out = json.loads(capsys.readouterr().out)
    assert out["releases_found"] == ["1.0.0", "1.1.0"] and out["past_retention"] == ["1.0.0"]
    assert out["non_version_entries"] == ["KEYS", "1.2.0"]
    commands = render.step2(render.Sweep.from_load(load), out)["commands"]
    assert "  https://dist.apache.org/repos/dist/release/foo/v1.0.0 \\\n" in commands
    assert "  https://archive.apache.org/dist/foo/v1.0.0 \\\n" in commands
    assert "vv1.0.0" not in commands


def test_prefixed_template_refuses_a_retention_run_without_the_prefix() -> None:
    sweep = sweep_of(template=V_TEMPLATE, project="foo", archive=None)
    with pytest.raises(render.RenderError, match="re-run `archive-sweep trains`"):
        render.step2(sweep, run("v1.0.0\nv1.1.0\n", ONE_X))


def test_github_release_tags_keep_their_prefix() -> None:
    sweep = sweep_of(
        backend="github-releases",
        template="https://github.com/o/foo/releases/tag/v<version>",
        archive=None,
        upstream="o/foo",
    )
    versions, _ = retention.parse_listing("v1.0.0\nv1.1.0\n", "v", "")
    out = retention.sweep(versions, ONE_X) | {"entry_prefix": "v", "entry_suffix": ""}
    assert render.step2(sweep, out)["commands"] == "```text\ngh release delete v1.0.0 --repo o/foo --yes\n```"


def test_listing_suffix_is_stripped_and_restored() -> None:
    assert retention.parse_listing("foo-1.0.0-bin\nfoo-1.1.0-bin\nfoo-1.1.0\n", "foo-", "-bin") == (
        ["1.0.0", "1.1.0"],
        ["foo-1.1.0"],
    )
    sweep = sweep_of(
        template="https://dist.apache.org/repos/dist/<bucket>/foo/foo-<version>-bin/",
        project="foo",
        archive=None,
    )
    assert sweep.entry("1.0.0") == "foo-1.0.0-bin"
    assert sweep.archive_url("1.0.0") == "https://archive.apache.org/dist/foo/foo-1.0.0-bin"
    assert sweep.release_url("1.0.0") == "https://dist.apache.org/repos/dist/release/foo/foo-1.0.0-bin"


def test_bare_version_template_keeps_its_old_shape() -> None:
    sweep = sweep_of()
    assert (sweep.release_dir(), sweep.entry_affix) == (
        "https://dist.apache.org/repos/dist/release/airflow/",
        ("", ""),
    )
    assert render.trains(sweep)["entry_prefix"] == ""
