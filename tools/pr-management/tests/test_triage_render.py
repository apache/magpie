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
"""Rendering the contributor-facing bodies of triage actions."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from pr_management import cli, config, mdconfig, model
from pr_management.config import CONFIRMATION_MARKER
from pr_management.triage import render as R

from .helpers import NOW, ago, check, comment, page, pr, review, thread

URLS = {
    "<quality_criteria_url>": "https://docs.example/criteria",
    "<two_stage_triage_rationale_url>": "https://docs.example/two-stage",
    "<project_display_name>": "Apache Foo",
    "<merge_conflicts_rebase_url>": "https://docs.example/rebase",
    "<project_communication_channel>": "Slack",
    "<project_communication_url>": "https://slack.example",
}


def _cfg(channel: str = "pr-body", **kw: Any) -> config.Config:
    cfg = config.Config(
        upstream_repo="acme/product",
        contributing_docs_url="https://docs.example/contributing",
        urls=dict(URLS),
        feedback_channel=channel,
        conflicts_url="https://docs.example/rebase",
        real_ci_patterns=["Tests"],
    )
    for k, v in kw.items():
        setattr(cfg, k, v)
    return cfg


def _render(
    node: dict[str, Any],
    action: str,
    classification: str | None = None,
    *,
    cfg: config.Config | None = None,
    details: dict[str, Any] | None = None,
    overrides: dict[str, str] | None = None,
) -> R.Rendered:
    p = model.from_node(node)
    return R.render(
        p,
        cfg or _cfg(),
        action=action,
        classification=classification,
        viewer="triager",
        now=NOW,
        details=details,
        prs=[p],
        overrides=overrides,
        sec_list="security@foo.example",
    )


CASES = [
    ("draft", "deterministic_flag", {"mergeable": "CONFLICTING"}, {}),
    (
        "comment",
        "deterministic_flag",
        {"rollup": "FAILURE", "checks": [check("Static checks", "FAILURE")]},
        {},
    ),
    ("close", "deterministic_flag", {"mergeable": "CONFLICTING"}, {"flagged_count": 5}),
    ("comment", "security_language_signal", {"title": "Fix SQL injection"}, {}),
    ("ping", "stale_review", {"reviews": [review("kaxil", "CHANGES_REQUESTED", body="x")]}, {}),
    ("ping", "deterministic_flag", {"threads": [thread(comment("kaxil", "MEMBER", ago(days=3), "?"))]}, {}),
    (
        "request-author-confirmation",
        "deterministic_flag",
        {"threads": [thread(comment("kaxil", "MEMBER", ago(days=3), "?"))]},
        {},
    ),
    (
        "close",
        "stale_draft",
        {
            "draft": True,
            "body": "x\n<!-- pr-triage-fold: triaged="
            + ago(days=9)
            + " head=abc1234 action=draft by=t -->\nq\n<!-- /pr-triage-fold -->",
        },
        {},
    ),
    ("close", "stale_draft_untriaged", {"draft": True, "updated": ago(days=30)}, {}),
    ("draft", "inactive_open", {"updated": ago(days=35)}, {}),
    ("draft", "stale_workflow_approval", {"updated": ago(days=35)}, {}),
    ("close", "stale_ready_label_unhealthy", {"mergeable": "CONFLICTING"}, {"days_since_maintainer": 21}),
    (
        "strip-ready-label",
        "stale_ready_label",
        {"mergeable": "CONFLICTING"},
        {"strip_reason": "merge conflicts with main", "next_move": "rebase onto `main`"},
    ),
    ("flag-suspicious", "pending_workflow_approval", {}, {}),
]


@pytest.mark.parametrize("channel", ["pr-body", "comment"])
@pytest.mark.parametrize(("action", "classification", "node_kw", "details"), CASES)
def test_every_action_renders_without_unresolved_placeholders(
    channel: str, action: str, classification: str, node_kw: dict[str, Any], details: dict[str, Any]
) -> None:
    result = _render(pr(**node_kw), action, classification, cfg=_cfg(channel), details=details)
    assert result.body is not None
    assert result.warnings == [], result.body
    assert not R.PLACEHOLDER.search(result.body.replace("<!--", "").replace("-->", ""))


def test_pr_body_note_is_folded_and_mentions_only_the_author() -> None:
    result = _render(
        pr(mergeable="CONFLICTING", threads=[thread(comment("kaxil", "MEMBER", ago(days=3), "?"))]),
        "draft",
        "deterministic_flag",
    )
    body = result.body or ""
    assert body.startswith(
        "<!-- pr-triage-fold: triaged=2026-10-01T12:00:00Z head=abc1234 action=draft by=triager -->"
    )
    assert body.rstrip().endswith("<!-- /pr-triage-fold -->")
    assert "@nina-contributor" in body and "`@triager`" in body
    assert result.mentions == ["@nina-contributor"]
    assert result.assign_author and not result.unassign_author
    assert "[Pull Request quality criteria](https://docs.example/criteria)" in body
    assert "2026-10-01 12:00 UTC" in body
    assert "<sub>" in body
    assert "two-stage" not in body  # the long footer is replaced by the <sub> disclaimer


def test_comment_channel_ends_with_the_long_footer() -> None:
    result = _render(pr(mergeable="CONFLICTING"), "draft", "deterministic_flag", cfg=_cfg("comment"))
    body = result.body or ""
    assert body.startswith("@nina-contributor Converting to **draft**")
    assert "pr-triage-fold" not in body
    assert body.rstrip().endswith("the conversation with you._")
    assert "Apache Foo maintainer" in body
    assert not result.assign_author


def test_violations_are_one_bullet_per_category() -> None:
    cfg = _cfg(
        check_map=[
            config.CheckCategory("static", "Static checks", "https://docs.example/static"),
            config.CheckCategory("*", "Failing CI checks", None),
        ]
    )
    node = pr(
        rollup="FAILURE",
        checks=[
            check("Static checks: ruff", "FAILURE"),
            check("Static checks: mypy", "FAILURE"),
            check("Tests (a)", "FAILURE"),
        ],
    )
    body = _render(node, "draft", "deterministic_flag", cfg=cfg).body or ""
    assert body.count("**Static checks**") == 1
    assert body.count("**Failing CI checks**") == 1
    assert "ruff" not in body and "mypy" not in body


def test_other_handles_are_backtick_quoted() -> None:
    override = {
        "draft": "@<author> please ask @kaxil and @apache/committers, see #123.\n<ai_attribution_footer>\n"
    }
    result = _render(pr(), "draft", "deterministic_flag", cfg=_cfg("comment"), overrides=override)
    body = result.body or ""
    assert "`@kaxil`" in body and "`@apache/committers`" in body
    assert "@kaxil " not in body.replace("`@kaxil`", "")
    assert "[#123](https://github.com/acme/product/pull/123)" in body
    assert result.mentions == ["@nina-contributor"]


def test_an_override_replaces_the_default_body() -> None:
    override = {
        "comment": "@<author> Custom wording. [Pull Request quality criteria](<quality_criteria_url>)\n\n<violations>\n\n<ai_attribution_footer>\n"
    }
    body = (
        _render(
            pr(mergeable="CONFLICTING"),
            "comment",
            "deterministic_flag",
            cfg=_cfg("comment"),
            overrides=override,
        ).body
        or ""
    )
    assert body.startswith("@nina-contributor Custom wording.")
    assert "A few things need addressing" not in body


def test_an_override_feeds_the_folded_note_body() -> None:
    override = {"comment": "@<author> Custom wording.\n<ai_attribution_footer>\n"}
    body = _render(pr(), "comment", "deterministic_flag", overrides=override).body or ""
    assert "> Custom wording." in body and "pr-triage-fold" in body


def test_confirmation_request_carries_the_marker_in_both_channels() -> None:
    node = pr(threads=[thread(comment("kaxil", "MEMBER", ago(days=3), "?"))])
    for channel in ("pr-body", "comment"):
        result = _render(node, "request-author-confirmation", "deterministic_flag", cfg=_cfg(channel))
        assert CONFIRMATION_MARKER in (result.body or "")
        assert "`kaxil`" in (result.body or "")
        assert "@kaxil" not in (result.body or "").replace("`@kaxil`", "")


def test_maintainer_sweep_handback_variant() -> None:
    result = _render(
        pr(threads=[thread(comment("kaxil", "MEMBER", ago(days=3), "?"))]),
        "request-author-confirmation",
        "deterministic_flag",
        cfg=_cfg("comment", handback_mode="maintainer-sweep"),
    )
    assert result.template == "request-author-confirmation-maintainer-sweep"
    assert "yes / ready" in (result.body or "")


def test_ready_flip_replaces_a_fold_and_unassigns() -> None:
    node = pr(
        body="x\n<!-- pr-triage-fold: triaged="
        + ago(days=2)
        + " head=0000000 action=draft by=t -->\nq\n<!-- /pr-triage-fold -->"
    )
    result = _render(node, "mark-ready", "passing")
    assert result.template == "ready-flip"
    assert "action=ready" in (result.body or "")
    assert result.unassign_author and not result.assign_author


def test_mark_ready_without_a_fold_has_no_body() -> None:
    result = _render(pr(), "mark-ready", "passing")
    assert result.body is None and result.template is None


@pytest.mark.parametrize("action", ["rerun", "rebase", "approve-workflow"])
def test_actions_without_a_body(action: str) -> None:
    assert _render(pr(), action, "deterministic_flag").body is None


def test_suspicious_changes_never_folds_and_has_no_footer() -> None:
    result = _render(pr(), "flag-suspicious", None)
    assert result.channel == "comment"
    assert "pr-triage-fold" not in (result.body or "")
    assert "AI-assisted" not in (result.body or "")
    assert "@" not in (result.body or "")


def test_missing_url_is_a_warning_not_a_silent_placeholder() -> None:
    cfg = _cfg("comment", urls={})
    result = _render(pr(mergeable="CONFLICTING"), "draft", "deterministic_flag", cfg=cfg)
    assert any("<quality_criteria_url>" in w for w in result.warnings)


def test_close_counts_flagged_prs_from_the_sweep() -> None:
    nodes = [pr(n, mergeable="CONFLICTING", author="spammer", head=f"{n:07d}aaaa") for n in range(1, 6)]
    prs = [model.from_node(n) for n in nodes]
    result = R.render(
        prs[0],
        _cfg("comment"),
        action="close",
        classification="deterministic_flag",
        viewer="triager",
        now=NOW,
        prs=prs,
    )
    assert "**Multiple flagged PRs**: 5 of your PRs" in (result.body or "")


def test_rebase_note_when_far_behind() -> None:
    p = model.from_node(pr(mergeable="CONFLICTING"))
    p.commits_behind = 73
    body = R.render(
        p, _cfg("comment"), action="draft", classification="deterministic_flag", viewer="t", now=NOW
    ).body
    assert "**73 commits behind `main`**" in (body or "")


def test_overrides_are_read_from_the_comment_templates_file(tmp_path: Path) -> None:
    (tmp_path / "pr-management-triage-comment-templates.md").write_text(
        "# T\n\n## Template body overrides\n\nWhy: shorter.\n\n### draft\n\n```markdown\n@<author> Short.\n```\n"
    )
    found = R.template_overrides(mdconfig.Resolver(tmp_path, tmp_path))
    assert found == {"draft": "@<author> Short.\n"}


def test_cli_render_writes_the_body_and_reports(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    saved = tmp_path / "saved"
    saved.mkdir()
    (saved / "triage-pages.json").write_text(json.dumps(page(pr(7, mergeable="CONFLICTING"))))
    cfgdir = tmp_path / "cfg"
    cfgdir.mkdir()
    (cfgdir / "pr-management-triage-comment-templates.md").write_text(
        "| Placeholder | Value |\n|---|---|\n" + "".join(f"| `{k}` | `{v}` |\n" for k, v in URLS.items())
    )
    (cfgdir / "project.md").write_text("| Key | Value |\n|---|---|\n| `upstream_repo` | `acme/product` |\n")
    rc = cli.main(
        [
            "--config-dir",
            str(cfgdir),
            "triage",
            "render",
            "--saved-dir",
            str(saved),
            "--pr",
            "7",
            "--action",
            "draft",
            "--classification",
            "deterministic_flag",
            "--viewer",
            "triager",
            "--out-dir",
            str(tmp_path / "out"),
            "--now",
            "2026-10-01T12:00:00Z",
        ]
    )
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] and out["channel"] == "pr-body" and out["template"] == "draft"
    assert out["assign_author"] is True and out["mentions"] == ["@nina-contributor"]
    assert Path(out["body_file"]).read_text().startswith("<!-- pr-triage-fold:")
    assert out["body_file"].endswith("pr-7-draft.md")
