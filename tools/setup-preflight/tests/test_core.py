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

"""The rules that were prose in `tools/dev/preflight-block.md`, as tests.

Each name states the rule; a failure here is a behaviour change in what
every skill does before it runs, not merely a refactor.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from setup_preflight.core import (
    cached_project_findings,
    configured_at_all,
    project_findings,
    skill_findings,
    verify_findings,
)
from setup_preflight.lockfile import MalformedLock

from .conftest import write_lock, write_stamp

MARKETPLACE = """\
method:       marketplace
url:          apache/magpie
min_version:  0.2.0

plugins:
  - magpie-setup
"""

STAMPED = """\
reconciled:
  version: 0.2.0
  at:      2026-01-01
  skills:
    {skill}: {digest}
"""


def stamped(skill: str, digest: str) -> str:
    """A marketplace lock carrying one reconciliation entry."""
    return MARKETPLACE + "\n" + STAMPED.format(skill=skill, digest=digest)


def codes(findings: list) -> list[str]:
    return [f.code for f in findings]


# --- project scope ------------------------------------------------------------------


def test_no_lock_is_a_supported_end_state_not_a_fault(project: Path) -> None:
    assert project_findings(project, {"magpie-setup": "0.2.0"}) == []


def test_unreadable_plugin_listing_is_unknown_never_absent(project: Path) -> None:
    """The rule the sandbox makes load-bearing: `claude plugin list --json`
    returns `[]` when the plugin cache is read-denied, which reads exactly
    like "nothing installed". Acting on it would propose installing the
    project's entire floor on every sandboxed run."""
    write_lock(project, MARKETPLACE)
    assert project_findings(project, None) == []


def test_a_genuinely_missing_plugin_is_a_finding(project: Path) -> None:
    write_lock(project, MARKETPLACE)
    found = project_findings(project, {"something-else": "9.9.9"})
    assert codes(found) == ["below-floor"]
    assert found[0].facts["missing"] == ["magpie-setup"]


def test_being_ahead_of_the_floor_is_never_a_finding(project: Path) -> None:
    write_lock(project, MARKETPLACE)
    assert project_findings(project, {"magpie-setup": "9.9.9"}) == []


def test_a_dev_build_below_the_floor_is_below_it(project: Path) -> None:
    write_lock(project, MARKETPLACE)
    found = project_findings(project, {"magpie-setup": "0.2.0.dev202609110041"})
    assert codes(found) == ["below-floor"]


def test_an_untrusted_marketplace_url_runs_nothing(project: Path) -> None:
    write_lock(project, MARKETPLACE.replace("apache/magpie", "attacker/magpie"))
    found = project_findings(project, {"magpie-setup": "0.0.1"})
    # The url check short-circuits: no install is ever proposed for a
    # marketplace the project did not name.
    assert codes(found) == ["untrusted-marketplace"]


def test_a_snapshot_method_without_a_local_lock_was_never_fetched(project: Path) -> None:
    write_lock(project, "method: git-tag\nref: v0.2.0\n")
    assert codes(project_findings(project, None)) == ["snapshot-never-fetched"]


GIT_TAG_PIN = """\
method: git-tag
url:    https://github.com/apache/magpie.git
ref:    v0.2.0
commit: 1111111111111111111111111111111111111111
"""

FETCHED = """\
# .apache-magpie.local.lock — gitignored; per-machine.

source_method:    {method}
source_url:       {url}
source_ref:       {ref}
fetched_commit:   {commit}
fetched_at:       2026-10-05T12:00:00Z
"""


def write_local_lock(
    root: Path,
    *,
    method: str = "git-tag",
    url: str = "https://github.com/apache/magpie.git",
    ref: str = "v0.2.0",
    commit: str = "1111111111111111111111111111111111111111",
) -> None:
    """The local lock in the shape `install.md` and `upgrade.md` write it."""
    (root / ".apache-magpie.local.lock").write_text(
        FETCHED.format(method=method, url=url, ref=ref, commit=commit), encoding="utf-8"
    )


def test_a_local_lock_matching_the_pin_is_silent(project: Path) -> None:
    """The local lock records what was fetched under its own keys
    (`source_method`, `source_url`, `source_ref`, `fetched_commit`), and each
    is compared with the committed key it records."""
    write_lock(project, GIT_TAG_PIN)
    write_local_lock(project)
    assert project_findings(project, None) == []


def test_a_local_lock_with_an_unknown_key_is_unreadable(project: Path) -> None:
    write_lock(project, GIT_TAG_PIN)
    (project / ".apache-magpie.local.lock").write_text("method: git-tag\nref: v0.2.0\n", encoding="utf-8")
    found = project_findings(project, None)
    assert codes(found) == ["snapshot-unreadable"]
    assert found[0].facts == {"error": "unknown key: 'method'"}


def test_a_snapshot_ref_mismatch_is_drift(project: Path) -> None:
    write_lock(project, GIT_TAG_PIN)
    write_local_lock(project, ref="v0.1.0")
    found = project_findings(project, None)
    assert codes(found) == ["snapshot-drift"]
    assert found[0].facts["differs"] == {"ref": {"project": "v0.2.0", "machine": "v0.1.0"}}


def test_a_fetched_commit_other_than_the_pinned_one_is_drift(project: Path) -> None:
    write_lock(project, GIT_TAG_PIN)
    write_local_lock(project, commit="2222222222222222222222222222222222222222")
    found = project_findings(project, None)
    assert codes(found) == ["snapshot-drift"]
    assert found[0].facts["differs"] == {
        "commit": {
            "project": "1111111111111111111111111111111111111111",
            "machine": "2222222222222222222222222222222222222222",
        }
    }


def test_a_snapshot_method_or_url_mismatch_is_drift(project: Path) -> None:
    """A different fetch method or source needs a re-install, not an upgrade;
    the facts carry which key differs so the rule can say which."""
    write_lock(project, GIT_TAG_PIN)
    write_local_lock(project, method="git-branch", url="https://b.example/magpie")
    found = project_findings(project, None)
    assert codes(found) == ["snapshot-drift"]
    assert found[0].facts["differs"] == {
        "method": {"project": "git-tag", "machine": "git-branch"},
        "url": {"project": "https://github.com/apache/magpie.git", "machine": "https://b.example/magpie"},
    }


LOCAL = """\
method: local
source: skills/
"""


def test_the_framework_checkout_self_adoption_lock_parses(project: Path) -> None:
    """`install.md` writes `source: skills/` for `method: local`; rejecting
    it failed every skill's pre-flight in the framework checkout."""
    write_lock(project, LOCAL)
    project_findings(project, None)


def test_the_framework_checkout_has_nothing_to_drift(project: Path) -> None:
    """Its skills are the working tree: no snapshot, no floor. Routing it to
    the snapshot-drift section proposed an `upgrade` that cannot help."""
    write_lock(project, LOCAL)
    assert project_findings(project, None) == []
    assert project_findings(project, {"magpie-setup": "0.0.1"}) == []


def test_a_malformed_lock_raises_rather_than_reading_as_no_lock(project: Path) -> None:
    write_lock(project, "method: marketplace\nnonsense\n")
    with pytest.raises(MalformedLock):
        project_findings(project, None)


# --- skill scope --------------------------------------------------------------------


def test_nothing_configured_means_nothing_to_reconcile(project: Path) -> None:
    """A bare git repository: no lock, no personal layer, no overrides."""
    assert not configured_at_all(project)
    assert skill_findings(project, "magpie-x", "sha256:abc", []) == []


def test_an_unreadable_own_fingerprint_says_nothing(project: Path) -> None:
    write_lock(project, MARKETPLACE)
    assert skill_findings(project, "magpie-x", None, []) == []


def test_a_matching_fingerprint_is_silent(project: Path) -> None:
    write_lock(project, stamped("magpie-x", "sha256:abc"))
    assert skill_findings(project, "magpie-x", "sha256:abc", []) == []


def test_a_moved_fingerprint_names_the_cause_as_anchors_when_config_resolves(project: Path) -> None:
    write_lock(project, stamped("magpie-x", "sha256:OLD"))
    found = skill_findings(project, "magpie-x", "sha256:NEW", [])
    assert codes(found) == ["fingerprint-moved"]
    assert found[0].facts["cause"] == "anchors"


def test_a_moved_fingerprint_names_config_when_an_entry_stopped_resolving(project: Path) -> None:
    write_lock(project, stamped("magpie-x", "sha256:OLD"))
    found = skill_findings(project, "magpie-x", "sha256:NEW", ["missing.md"])
    assert codes(found) == ["config-missing", "fingerprint-moved"]
    assert found[1].facts["cause"] == "requires_config"


def test_the_local_store_wins_when_both_name_the_skill(project: Path) -> None:
    """`config` on one machine and `adopt` on another is expected and
    transitional, not a fault."""
    write_lock(project, stamped("magpie-x", "sha256:LOCKED"))
    write_stamp(project, {"skills": {"magpie-x": "sha256:LOCAL"}})
    assert skill_findings(project, "magpie-x", "sha256:LOCAL", []) == []
    found = skill_findings(project, "magpie-x", "sha256:OTHER", [])
    assert found[0].facts["in_both_stores"] is True


def test_a_stamp_that_does_not_name_this_skill_is_silent(project: Path) -> None:
    """The project simply does not configure this skill; step 7 already
    covers the case where it does and a file is missing."""
    write_lock(project, stamped("magpie-other", "sha256:abc"))
    assert skill_findings(project, "magpie-x", "sha256:abc", []) == []


def test_no_stamp_anywhere_proposes_the_one_time_sweep(project: Path) -> None:
    write_lock(project, MARKETPLACE)
    assert codes(skill_findings(project, "magpie-x", "sha256:abc", [])) == ["sweep-never-run"]


def test_requires_config_resolves_from_either_store(project: Path) -> None:
    write_lock(project, MARKETPLACE)
    (project / ".apache-magpie-overrides").mkdir()
    (project / ".apache-magpie-overrides" / "a.md").write_text("x")
    local = project / ".apache-magpie-local"
    local.mkdir()
    (local / "b.md").write_text("x")
    found = skill_findings(project, "magpie-x", None, ["a.md", "b.md", "c.md"])
    assert codes(found) == ["config-missing"]
    assert found[0].facts["files"] == ["c.md"]


# --- end-of-run scope ---------------------------------------------------------------


def test_verify_is_not_suggested_inside_the_interval(project: Path) -> None:
    write_stamp(project, {"verified_at": "2026-09-20"})
    assert verify_findings(project, 14, today=date(2026, 9, 22)) == []


def test_verify_is_suggested_once_the_interval_elapses(project: Path) -> None:
    write_stamp(project, {"verified_at": "2026-09-01"})
    assert codes(verify_findings(project, 14, today=date(2026, 9, 22))) == ["verify-overdue"]


def test_a_suggestion_already_made_rearms_the_clock(project: Path) -> None:
    write_stamp(project, {"verified_at": "2026-09-01", "verify_suggested_at": "2026-09-21"})
    assert verify_findings(project, 14, today=date(2026, 9, 22)) == []


def test_interval_zero_disables_the_suggestion(project: Path) -> None:
    write_stamp(project, {"verified_at": "2020-01-01"})
    assert verify_findings(project, 0, today=date(2026, 9, 22)) == []


def test_with_no_dates_at_all_nothing_is_overdue(project: Path) -> None:
    assert verify_findings(project, 14, today=date(2026, 9, 22)) == []


# --- memoising the project scope ----------------------------------------------------


def test_the_project_verdict_is_reused_for_identical_inputs(project: Path) -> None:
    write_lock(project, MARKETPLACE)
    (project / ".apache-magpie-local").mkdir()
    first, cached = cached_project_findings(project, {"magpie-setup": "0.1.0"})
    assert cached is False and codes(first) == ["below-floor"]
    second, cached = cached_project_findings(project, {"magpie-setup": "0.1.0"})
    assert cached is True and codes(second) == ["below-floor"]


def test_a_changed_plugin_listing_invalidates_the_cache(project: Path) -> None:
    write_lock(project, MARKETPLACE)
    (project / ".apache-magpie-local").mkdir()
    cached_project_findings(project, {"magpie-setup": "0.1.0"})
    found, cached = cached_project_findings(project, {"magpie-setup": "9.9.9"})
    assert cached is False and found == []


def test_a_refreshed_checker_invalidates_the_cache(project: Path) -> None:
    """`upgrade` replaces the checker's copy; a verdict the old code computed
    must not outlive it."""
    write_lock(project, MARKETPLACE)
    (project / ".apache-magpie-local").mkdir()
    cached_project_findings(project, {"magpie-setup": "0.1.0"})
    cache = project / ".apache-magpie-local" / ".preflight-cache.json"
    stale = json.loads(cache.read_text())
    stale["key"] = stale["key"].rsplit("|checker:", 1)[0] + "|checker:previous-code"
    cache.write_text(json.dumps(stale))
    _, cached = cached_project_findings(project, {"magpie-setup": "0.1.0"})
    assert cached is False


def test_the_cache_expires(project: Path) -> None:
    write_lock(project, MARKETPLACE)
    (project / ".apache-magpie-local").mkdir()
    cached_project_findings(project, None, now=1000.0)
    _, cached = cached_project_findings(project, None, now=1000.0 + 10_000)
    assert cached is False


def test_an_unconfigured_project_is_never_cached(project: Path) -> None:
    """Writing a cache file would create the personal layer, whose absence
    is part of what means "never configured"."""
    write_lock(project, MARKETPLACE)
    _, cached = cached_project_findings(project, None)
    assert cached is False
    assert not (project / ".apache-magpie-local").exists()


def test_an_unconfigured_unadopted_project_is_never_cached(project: Path) -> None:
    _, cached = cached_project_findings(project, None)
    assert cached is False
    assert not (project / ".git" / "apache-magpie").exists()


# --- already-shown suppression ------------------------------------------------------


def test_a_finding_already_shown_for_this_hash_does_not_repeat(project: Path) -> None:
    write_lock(project, stamped("magpie-x", "sha256:OLD"))
    write_stamp(project, {"acknowledged": {"skills": {"magpie-x": "sha256:NEW"}}})
    assert skill_findings(project, "magpie-x", "sha256:NEW", []) == []


def test_suppression_lapses_once_the_fingerprint_moves_again(project: Path) -> None:
    write_lock(project, stamped("magpie-x", "sha256:OLD"))
    write_stamp(project, {"acknowledged": {"skills": {"magpie-x": "sha256:NEW"}}})
    assert codes(skill_findings(project, "magpie-x", "sha256:NEWER", [])) == ["fingerprint-moved"]


def test_a_declined_sweep_stays_declined_until_the_version_moves(project: Path) -> None:
    write_lock(project, MARKETPLACE)
    write_stamp(project, {"acknowledged": {"sweep": "0.2.0"}})
    assert skill_findings(project, "magpie-x", "sha256:abc", []) == []


# --- where personal config lives ----------------------------------------------------


def test_an_unadopted_repo_reads_its_stamp_from_the_git_dir_home(project: Path) -> None:
    home = project / ".git" / "apache-magpie"
    home.mkdir()
    (home / "reconciled.json").write_text(json.dumps({"verified_at": "2026-09-01"}))
    assert configured_at_all(project)
    assert codes(verify_findings(project, 14, today=date(2026, 9, 22))) == ["verify-overdue"]


def test_requires_config_resolves_from_the_git_dir_home(project: Path) -> None:
    home = project / ".git" / "apache-magpie"
    home.mkdir()
    (home / "a.md").write_text("x")
    assert skill_findings(project, "magpie-x", None, ["a.md"]) == []


def test_an_adopted_repo_does_not_read_the_git_dir_home(project: Path) -> None:
    write_lock(project, MARKETPLACE)
    home = project / ".git" / "apache-magpie"
    home.mkdir()
    (home / "a.md").write_text("x")
    assert codes(skill_findings(project, "magpie-x", None, ["a.md"])) == ["config-missing"]


def test_the_git_dir_home_is_found_from_a_linked_worktree(tmp_path: Path) -> None:
    main = tmp_path / "main"
    wt_gitdir = main / ".git" / "worktrees" / "wt"
    wt_gitdir.mkdir(parents=True)
    (wt_gitdir / "commondir").write_text("../..\n")
    home = main / ".git" / "apache-magpie"
    home.mkdir()
    (home / "a.md").write_text("x")
    wt = tmp_path / "wt"
    wt.mkdir()
    (wt / ".git").write_text(f"gitdir: {wt_gitdir}\n")
    assert configured_at_all(wt)
    assert skill_findings(wt, "magpie-x", None, ["a.md"]) == []


def test_a_legacy_in_tree_dir_still_works_and_is_reported(project: Path) -> None:
    legacy = project / ".apache-magpie-local"
    legacy.mkdir()
    (legacy / "a.md").write_text("x")
    (legacy / "reconciled.json").write_text(json.dumps({"verified_at": "2026-09-01"}))
    info = project / ".git" / "info"
    info.mkdir()
    (info / "exclude").write_text("# comment\n/.apache-magpie-local/\n")
    assert configured_at_all(project)
    assert skill_findings(project, "magpie-x", None, ["a.md"]) == []
    assert codes(verify_findings(project, 14, today=date(2026, 9, 22))) == ["verify-overdue"]
    [finding] = project_findings(project, None)
    assert finding.code == "legacy-local-dir"
    assert finding.scope == "project"
    assert finding.facts == {
        "legacy_dir": str(legacy),
        "personal_dir": str(project / ".git" / "apache-magpie"),
        "personal_dir_exists": False,
        "exclude_file": str(info / "exclude"),
        "exclude_has_entry": True,
    }
    # Reading and reporting moved nothing and created nothing.
    assert not (project / ".git" / "apache-magpie").exists()
    assert (legacy / "a.md").is_file()


def test_the_git_dir_home_wins_over_the_legacy_dir(project: Path) -> None:
    legacy = project / ".apache-magpie-local"
    legacy.mkdir()
    (legacy / "reconciled.json").write_text(json.dumps({"verified_at": "2026-09-01"}))
    home = project / ".git" / "apache-magpie"
    home.mkdir()
    (home / "reconciled.json").write_text(json.dumps({"verified_at": "2026-09-20"}))
    assert verify_findings(project, 14, today=date(2026, 9, 22)) == []


def test_an_adopted_repo_with_an_in_tree_local_dir_is_not_legacy(project: Path) -> None:
    write_lock(project, LOCAL)
    (project / ".apache-magpie-local").mkdir()
    assert project_findings(project, None) == []


def test_a_legacy_dir_outside_a_git_repo_is_reported_with_nowhere_to_go(tmp_path: Path) -> None:
    (tmp_path / ".apache-magpie-local").mkdir()
    [finding] = project_findings(tmp_path, None)
    assert finding.facts["personal_dir"] is None
    assert finding.facts["exclude_file"] is None


def test_not_a_git_repo_and_not_adopted_has_nothing_configured(tmp_path: Path) -> None:
    assert not configured_at_all(tmp_path)
    assert skill_findings(tmp_path, "magpie-x", "sha256:abc", []) == []
    assert list(tmp_path.iterdir()) == []


def test_reading_never_creates_the_personal_layer(project: Path) -> None:
    skill_findings(project, "magpie-x", "sha256:abc", ["a.md"])
    verify_findings(project, 14, today=date(2026, 9, 22))
    cached_project_findings(project, None)
    assert sorted(p.name for p in project.iterdir()) == [".git"]
    assert list((project / ".git").iterdir()) == []


def test_an_unadopted_repo_caches_in_the_git_dir_home(project: Path) -> None:
    (project / ".git" / "apache-magpie").mkdir()
    cached_project_findings(project, None)
    _, cached = cached_project_findings(project, None)
    assert cached is True
    assert (project / ".git" / "apache-magpie" / ".preflight-cache.json").is_file()
    assert not (project / ".apache-magpie-local").exists()


def test_a_legacy_dir_appearing_invalidates_the_cache(project: Path) -> None:
    (project / ".git" / "apache-magpie").mkdir()
    first, _ = cached_project_findings(project, None)
    assert first == []
    (project / ".apache-magpie-local").mkdir()
    found, cached = cached_project_findings(project, None)
    assert cached is False and codes(found) == ["legacy-local-dir"]
