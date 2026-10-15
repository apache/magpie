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
"""release-announce-draft: the Step 0 verdict, the [ANNOUNCE] draft and the site-bump PR.

The scripted cases of the retired model-graded suites `step-0-preflight`
(cases 1 and 2), `step-2-announce-draft` (cases 1 to 3) and `step-3-site-bump`
(cases 1 and 2) live here, named after each former case, with the same scenario
and the same assertions.
"""

from __future__ import annotations

import json
import re
from typing import Any

import pytest

from release_management.announce_draft import render
from release_management.cli import main

DOWNLOAD = "https://airflow.apache.org/docs/apache-airflow/2.11.0/installation/installing-from-pypi.html"
CHANGELOG = "https://github.com/apache/airflow/blob/2.11.0/CHANGELOG.md"
WAIT = (
    "Promote-wait gate: promote commit was at 2026-06-11T09:45:00Z; the one-hour gate clears at "
    "2026-06-11T10:45:00Z (in ~30 minutes). Pass --skip-promote-wait <reason> to override."
)
SITE_FILES = [
    "landing-pages/site/content/en/_index.md",
    "landing-pages/site/content/en/announcements/2.11.0.md",
]


def preflight(
    *,
    blockers: list[str] | None = None,
    clear: str | None = None,
    wait: bool = False,
    skip: bool = False,
    non_asf: bool = False,
    backend: str | None = "announce-list",
) -> dict[str, Any]:
    return {
        "ok": not blockers,
        "skill": "announce-draft",
        "blockers": blockers or [],
        "warnings": [],
        "values": {
            "version": "2.11.0",
            "skip_promote_wait_override": skip,
            "non_asf": non_asf,
            "promote_clear_after_utc": clear,
            "promote_wait_active": wait,
            "download_page_url": DOWNLOAD,
            "release_announce_backend": backend,
        },
    }


def loaded(
    *,
    version: str = "2.11.0",
    backend: str = "announce-list",
    subject: str | None = "[ANNOUNCE] Apache Airflow <version> released",
    keys: str | None = "https://dist.apache.org/repos/dist/release/airflow/KEYS",
    announce_list: str | None = "announce@apache.org",
    cc: list[str] | None = None,
    site_repo: str | None = "apache/airflow-site",
    site_files: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "metadata": {
            "version": version,
            "promote_timestamp": "2026-06-10T08:00:00Z",
            "keys_url": keys,
            "announce_list": announce_list,
            "announce_cc_lists": ["dev@airflow.apache.org", "users@airflow.apache.org"] if cc is None else cc,
            "subject_template": subject,
            "site_repo": site_repo,
            "site_pr_files": SITE_FILES if site_files is None else site_files,
            "release_announce_backend": backend,
            "dist_release_url": f"https://dist.apache.org/repos/dist/release/airflow/{version}/",
            "convenience_artefacts": [],
        }
    }


def announce(product: str = "Apache Airflow", **kw: Any) -> render.Announce:
    return render.Announce.from_load(loaded(**kw), product_name=product)


# The step-2-announce-draft assertions.json predicates, on `body`.
HAS = {
    "apache_org_sender_reminder": r"@apache\.org address",
    "download_page_link": r"download page[\s\S]{0,120}https?://",
    "download_link": r"download[\s\S]{0,120}https?://",
    "changelog_link": r"(?:changelog|release notes)[\s\S]{0,120}https?://",
    "keys_link": r"https?://\S*KEYS",
    "skip_promote_wait_note": r"skip-promote-wait|promote-wait gate overridden",
}


def has(key: str, body: str) -> bool:
    return re.search(HAS[key], body, re.I) is not None


# --- step-0-preflight ------------------------------------------------------ #


def test_step0_case_1_clean_pass() -> None:
    out = render.verdict(preflight(), promoted=True)
    assert {k: out[k] for k in out if k != "read"} == {
        "verdict": "proceed",
        "blockers": [],
        "skip_promote_wait_override": False,
        "non_asf": False,
        "promote_clear_after_utc": None,
    }


def test_step0_case_2_not_promoted() -> None:
    out = render.verdict(
        preflight(blockers=["promote timestamp unavailable", "Download Page URL unavailable"]), promoted=False
    )
    assert out["verdict"] == "blocked"
    assert out["skip_promote_wait_override"] is False and out["non_asf"] is False
    assert out["promote_clear_after_utc"] is None
    assert render.NOT_PROMOTED in out["blockers"]


def test_step0_promote_wait_only_blocker_keeps_the_clear_time() -> None:
    out = render.verdict(preflight(blockers=[WAIT], clear="2026-06-11T10:45:00Z", wait=True), promoted=True)
    assert out["verdict"] == "blocked"
    assert out["blockers"] == [WAIT]  # verbatim from release-config
    assert out["promote_clear_after_utc"] == "2026-06-11T10:45:00Z"
    assert out["read"] == ["outcomes/promote-wait.md"]


def test_step0_label_check_also_blocking_nulls_the_clear_time() -> None:
    out = render.verdict(preflight(blockers=[WAIT], clear="2026-06-11T10:45:00Z", wait=True), promoted=False)
    assert out["verdict"] == "blocked" and len(out["blockers"]) == 2
    assert out["promote_clear_after_utc"] is None


def test_step0_skip_override_proceeds() -> None:
    out = render.verdict(preflight(wait=True, skip=True), promoted=True)
    assert out["verdict"] == "proceed" and out["skip_promote_wait_override"] is True and out["read"] == []


def test_step0_non_asf_with_the_announce_backend_unset_blocks() -> None:
    """announce-list is the ASF default only; a non-ASF project must name its channel."""
    out = render.verdict(preflight(non_asf=True, backend=None), promoted=True)
    assert out["verdict"] == "blocked"
    assert out["blockers"] == [
        "release_announce_backend is unset: announce-list is the default for ASF projects only, and this project "
        "is not one — set release_announce_backend in release-management-config.md to "
        "github-release-notes / site-post / discord-channel"
    ]
    assert render.verdict(preflight(non_asf=True, backend="site-post"), promoted=True)["verdict"] == "proceed"
    # An ASF project with the key unset keeps the announce-list default.
    assert render.verdict(preflight(backend=None), promoted=True)["verdict"] == "proceed"


def test_step0_no_planning_issue_blocks() -> None:
    out = render.verdict(preflight(), promoted=True, planning_issue_found=False)
    assert out["verdict"] == "blocked" and "no planning issue found" in out["blockers"][0]


# --- step-2-announce-draft ------------------------------------------------- #


def test_step2_case_1_standard_announce() -> None:
    out = render.step2(announce(), download_page=DOWNLOAD, changelog_url=CHANGELOG)
    body = out["body"]
    assert out["subject"] == "[ANNOUNCE] Apache Airflow 2.11.0 released"
    assert out["backend"] == "announce-list"
    assert out["skip_promote_wait_logged"] is False
    assert out["asf_address_reminder_present"] is True
    for key in ("apache_org_sender_reminder", "download_page_link", "changelog_link", "keys_link"):
        assert has(key, body), key
    assert not has("skip_promote_wait_note", body)
    assert body.startswith(
        "To: announce@apache.org\nCc: dev@airflow.apache.org, users@airflow.apache.org\n"
        "Subject: [ANNOUNCE] Apache Airflow 2.11.0 released\n"
    )
    assert (
        "The Apache Airflow community is pleased to announce the release\nof Apache Airflow 2.11.0." in body
    )
    assert "The\nannounce@apache.org rejects non-@apache.org senders" in body
    assert "dist.apache.org/repos/dist/release/airflow/2.11.0" not in body  # Download Page, not dist
    assert out["download_page_is_dist"] is False and out["warnings"] == []


def test_step2_case_2_skip_promote_wait_logged() -> None:
    reason = "Critical security release; mirrors propagated within 30 minutes per infra confirmation."
    out = render.step2(announce(), download_page=DOWNLOAD, changelog_url=CHANGELOG, skip_reason=reason)
    body = out["body"]
    assert out["subject"] == "[ANNOUNCE] Apache Airflow 2.11.0 released"
    assert out["backend"] == "announce-list"
    assert out["skip_promote_wait_logged"] is True and out["asf_address_reminder_present"] is True
    for key in (
        "apache_org_sender_reminder",
        "download_page_link",
        "changelog_link",
        "keys_link",
        "skip_promote_wait_note",
    ):
        assert has(key, body), key
    assert reason in body


def test_step2_case_3_non_asf_github_releases() -> None:
    a = render.Announce.from_load(
        loaded(
            version="1.5.0",
            backend="github-release-notes",
            subject="MyProject <version> released",
            keys=None,
            announce_list=None,
            cc=[],
        ),
        product_name="MyProject",
    )
    out = render.step2(
        a,
        download_page="https://myproject.example.com/download",
        changelog_url="https://github.com/example-org/myproject/blob/v1.5.0/CHANGELOG.md",
    )
    body = out["body"]
    assert out["subject"] == "MyProject 1.5.0 released"
    assert out["backend"] == "github-release-notes"
    assert out["skip_promote_wait_logged"] is False
    assert out["asf_address_reminder_present"] is False
    assert not has("apache_org_sender_reminder", body)
    assert has("download_link", body) and has("changelog_link", body)
    assert "To:" not in body and "Cc:" not in body
    assert "## Downloads" in body and "## Changelog" in body


def test_step2_site_post_and_discord_shapes() -> None:
    kw: dict[str, Any] = {"download_page": "https://p.example/dl", "changelog_url": "https://p.example/cl"}
    post = render.step2(announce("MyProject", backend="site-post", announce_list=None), **kw)
    assert post["body"].startswith("## MyProject 2.11.0 released")
    assert "[Download Page](https://p.example/dl)" in post["body"]
    assert post["asf_address_reminder_present"] is False
    discord = render.step2(announce("MyProject", backend="discord-channel"), **kw)["body"]
    assert (
        discord.count("\n- ") == 2 and "https://p.example/dl" in discord and "https://p.example/cl" in discord
    )


def test_step2_dist_apache_download_page_warns() -> None:
    out = render.step2(
        announce(),
        download_page="https://dist.apache.org/repos/dist/release/airflow/2.11.0/",
        changelog_url=CHANGELOG,
    )
    assert out["download_page_is_dist"] is True
    assert any("is a direct dist" in w and w.endswith("(Golden rule 5)") for w in out["warnings"])


def test_step2_convenience_lines_only_when_published() -> None:
    plain = render.step2(announce(), download_page=DOWNLOAD, changelog_url=CHANGELOG)["body"]
    assert "Convenience artefacts" not in plain
    out = render.step2(
        announce(),
        download_page=DOWNLOAD,
        changelog_url=CHANGELOG,
        convenience=[("wheel", "https://pypi.org/project/apache-airflow/2.11.0/")],
    )
    assert (
        "Convenience artefacts, built from the released source, are also available:\n  wheel: https://pypi.org/"
        in out["body"]
    )


def test_step2_canned_body_substitution_keeps_the_reminder() -> None:
    canned = (
        "Subject: [ANNOUNCE] <Product Name> <version>\n\nGet it at <download_page_url>; keys <keys_url>.\n"
    )
    out = render.step2(announce(), download_page=DOWNLOAD, changelog_url=CHANGELOG, canned_body=canned)
    assert "Apache Airflow 2.11.0" in out["body"] and DOWNLOAD in out["body"]
    assert "airflow/KEYS" in out["body"]
    assert out["body"].startswith("NOTE: This email must be sent from your @apache.org address.")
    assert out["reminder_prepended"] is True


@pytest.mark.parametrize(
    "phrasing",
    [
        "Send this from your @apache.org account.",
        "Remember: the sender must be an @Apache.org address.",
        "NOTE: use your @APACHE.ORG mailbox.",
    ],
)
def test_step2_canned_body_with_its_own_reminder_gets_no_second_one(phrasing: str) -> None:
    canned = f"{phrasing}\n\nTo: <announce_list>\n\n<Product Name> <version> is out.\n"
    out = render.step2(announce(), download_page=DOWNLOAD, changelog_url=CHANGELOG, canned_body=canned)
    assert out["reminder_prepended"] is False
    assert out["body"].startswith(phrasing)
    assert "NOTE: This email must be sent from your" not in out["body"]


def test_step2_canned_body_naming_only_a_full_address_still_gets_the_reminder() -> None:
    """`announce@apache.org` in `To:` is not a sender reminder."""
    canned = "To: <announce_list>\n\n<Product Name> <version> is out.\n"
    out = render.step2(announce(), download_page=DOWNLOAD, changelog_url=CHANGELOG, canned_body=canned)
    assert out["reminder_prepended"] is True
    assert out["body"].startswith("NOTE: This email must be sent from your @apache.org address.")


def test_step2_missing_facts_are_placeholders_never_invented() -> None:
    out = render.step2(announce(), download_page=None, changelog_url=None)
    assert "<download_page_url>" in out["body"] and "<changelog_url>" in out["body"]
    assert len(out["warnings"]) == 2


def test_step2_default_subject_template() -> None:
    assert render.step2(announce(subject=None), download_page=DOWNLOAD, changelog_url=CHANGELOG)[
        "subject"
    ] == ("[ANNOUNCE] Apache Airflow 2.11.0 released")


# --- step-3-site-bump ------------------------------------------------------ #


def test_step3_case_1_standard_site_bump() -> None:
    out = render.step3(announce())
    assert {k: out[k] for k in ("pr_title", "pr_body", "files_in_scope", "scope_violations", "proposed")} == {
        "pr_title": "chore: update site for Apache Airflow 2.11.0 release",
        "pr_body": "Site bump for Apache Airflow 2.11.0.\n\nFiles updated:\n- landing-pages/site/content/en/_index.md\n- landing-pages/site/content/en/announcements/2.11.0.md\n\nConstraints:\n- Download links use the closer.lua CDN selector, not direct dist.apache.org URLs.\n- Merge after the [ANNOUNCE] email is sent.\n\nGenerated by `release-announce-draft` (magpie-release-announce-draft).",
        "files_in_scope": SITE_FILES,
        "scope_violations": [],
        "proposed": True,
    }
    assert out["pr_command"].startswith("gh pr create --web --repo apache/airflow-site --title ")


def test_step3_case_2_no_site_repo() -> None:
    assert render.step3(announce(site_repo=None)) == {
        "skipped": True,
        "reason": "site_repo is not configured in release-management-config.md; no site-bump PR will be opened.",
    }


def test_step3_scope_violation_is_a_set_difference_until_confirmed() -> None:
    extra = "landing-pages/site/content/en/blog/2.11.0.md"
    out = render.step3(announce(), files=[*SITE_FILES, extra])
    assert out["scope_violations"] == [extra] and out["files_in_scope"] == SITE_FILES
    assert extra not in out["pr_body"]
    confirmed = render.step3(announce(), files=[*SITE_FILES, extra], confirmed_extra=[extra])
    assert confirmed["scope_violations"] == [] and confirmed["confirmed_out_of_scope"] == [extra]
    assert f"- {extra}" in confirmed["pr_body"]


def test_cli_verdict_and_renders(tmp_path, capsys) -> None:
    pre = tmp_path / "pre.json"
    pre.write_text(json.dumps(preflight()), encoding="utf-8")
    assert main(["announce-draft", "verdict", "--preflight", str(pre), "--promoted"]) == 0
    assert json.loads(capsys.readouterr().out)["verdict"] == "proceed"
    load = tmp_path / "load.json"
    load.write_text(json.dumps(loaded()), encoding="utf-8")
    base = ["announce-draft", "render", "--load", str(load), "--product-name", "Apache Airflow"]
    assert main([*base, "--step", "2", "--download-page", DOWNLOAD, "--changelog-url", CHANGELOG]) == 0
    assert json.loads(capsys.readouterr().out)["asf_address_reminder_present"] is True
    assert main([*base, "--step", "3"]) == 0
    assert json.loads(capsys.readouterr().out)["proposed"] is True
    load.write_text(json.dumps(loaded(backend="carrier-pigeon")), encoding="utf-8")
    assert main([*base, "--step", "2"]) == 2


def test_cli_rejects_a_malformed_convenience_pair(tmp_path) -> None:
    load = tmp_path / "load.json"
    load.write_text(json.dumps(loaded()), encoding="utf-8")
    with pytest.raises(SystemExit):
        main(["announce-draft", "render", "--step", "2", "--load", str(load), "--convenience", "wheel"])
