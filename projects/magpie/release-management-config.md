<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Apache Magpie: release-management configuration](#apache-magpie-release-management-configuration)
  - [Identifiers](#identifiers)
  - [Backends](#backends)
  - [Distribution URLs](#distribution-urls)
  - [Signing](#signing)
  - [Vote](#vote)
  - [Announce](#announce)
  - [Archive](#archive)
  - [Audit log](#audit-log)
  - [Category-X dependency denylist](#category-x-dependency-denylist)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Apache Magpie: release-management configuration

Magpie's **own** release-management config (Magpie self-adopts the
framework — see [`.apache-magpie.lock`](../../.apache-magpie.lock)).
This is the live config the `release-*` skills read for a Magpie
release, not a scaffold. The adopter template lives at
[`projects/_template/release-management-config.md`](../_template/release-management-config.md);
this file is that template filled with Magpie's values.

Magpie is an **ASF Top-Level Project** (established by Board
resolution — [`MISSION.md`](../../MISSION.md)), so it is pinned to the
mandatory ASF approval + announce mechanisms (`dev-list-vote`,
`announce-list`).

> [!IMPORTANT]
> **Distribution backend = `svnpubsub`** (the ASF-ratified default),
> per the [`svnpubsub` runbook](../../docs/release-management/svn-release-runbook.md).
> **Apache Trusted Releases (ATR) is the intended direction** and is
> fully documented in the [ATR release runbook](../../docs/release-management/atr-release-runbook.md),
> but ATR is in **alpha** and its adoption is **pending a PMC
> ratification vote on `dev@`**. Until that vote passes,
> `release_dist_backend` stays `svnpubsub`. After ratification, switch
> the value below to `atr` (and see `atr_platform_url`); no other change
> to this file is needed, since the approval and announce mechanisms are
> backend-independent.

## Identifiers

| Key | Value |
|---|---|
| `project_dist_name` | `magpie` |
| `product_name` | `Apache Magpie` |
| `upstream` | `apache/magpie` |
| `release_planning_issue_template` | *(none — uses the `release-prepare` default template)* |
| `release_branch_base` | `main` |
| `version_manifest_files` | `pyproject.toml` |

## Backends

| Key | Value | Allowed values |
|---|---|---|
| `release_dist_backend` | `svnpubsub` | `svnpubsub`, `atr`, `github-releases`, `s3`, `self-hosted` |
| `release_approval_mechanism` | `dev-list-vote` | `dev-list-vote`, `github-discussion`, `pr-approval`, `maintainer-roster` |
| `release_announce_backend` | `announce-list` | `announce-list`, `github-release-notes`, `site-post`, `discord-channel` |

As an ASF TLP, Magpie is pinned to `dev-list-vote` (mandatory per
[release-policy § release approval](https://www.apache.org/legal/release-policy.html#release-approval))
and `announce-list` (mandatory per
[release-policy § announcements](https://www.apache.org/legal/release-policy.html#release-announcements)).
`release_dist_backend = svnpubsub` stages the RC under `dist/dev/` and
promotes to `dist/release/` on `dist.apache.org`; see the
[`svnpubsub` runbook](../../docs/release-management/svn-release-runbook.md).
Setting it to `atr` (after PMC ratification) instead drives compose /
check / vote / finish through the ATR platform; see the
[ATR release runbook](../../docs/release-management/atr-release-runbook.md).

## Distribution URLs

| Key | Value |
|---|---|
| `release_dist_url_template` | `https://dist.apache.org/repos/dist/<bucket>/magpie/<version>/` |
| `archive_url_template` | `https://archive.apache.org/dist/magpie/` |
| `atr_platform_url` | `https://release-test.apache.org/` *(only used once `release_dist_backend = atr`; alpha host, production will be `release.apache.org`)* |

On the `svnpubsub` default, `<bucket>` resolves to `dev` while the RC
is staged for the vote and `release` after promotion. On the `atr`
backend (post-ratification) the RC lives in ATR's draft/candidate area
during Compose+Vote and **Finish** publishes to `dist/release/magpie/`.

## Signing

| Key | Value |
|---|---|
| `keys_file_url` | `https://dist.apache.org/repos/dist/release/magpie/KEYS` |
| `keyserver` | `keys.openpgp.org` |
| `rm_key_fingerprint` | *(per-RM; lives in the RM's `user.md` under `release_manager.gpg_fingerprint`)* |

The RM signs each artefact and the public key must be in `KEYS` (and,
once `release_dist_backend = atr`, also registered in the ATR platform,
which validates candidate signatures during Compose — see the ATR
runbook, Step B). The agent never holds the private key half.

## Vote

| Key | Value |
|---|---|
| `vote_dev_list` | `dev@magpie.apache.org` |
| `mail_archive` | `ponymail` |
| `mail_archive_url_template` | `https://lists.apache.org/list.html?dev@magpie.apache.org` |
| `vote_window_hours` | `72` |
| `vote_pass_rule_overrides` | *(none — ASF baseline: ≥3 binding +1, more +1 than -1)* |
| `vote_subject_template` | `[VOTE] Release Apache Magpie <version> from <version>-rcN` |
| `result_subject_template` | `[RESULT] [VOTE] Release Apache Magpie <version> from <version>-rcN` |
| `release_approver_roster_path` | `projects/magpie/pmc-roster.md` |

`vote_window_hours` is a floor per
[release-policy § release approval](https://www.apache.org/legal/release-policy.html#release-approval).
The ≥72h window and the binding-vote rule are backend-independent; on
the `atr` backend the platform sends the `[VOTE]` and tabulates, but the
window and rule are unchanged.

## Announce

| Key | Value |
|---|---|
| `announce_list` | `announce@apache.org` |
| `announce_cc_lists` | `dev@magpie.apache.org` |
| `announce_subject_template` | `[ANNOUNCE] Apache Magpie <version> released` |
| `site_repo` | `apache/magpie-site` *(TODO: confirm site repo name once the site is stood up)* |
| `site_pr_files` | *(TODO: set once the site structure exists)* |

`announce@apache.org` is mandatory for the TLP announcement per
[release-policy § announcements](https://www.apache.org/legal/release-policy.html#release-announcements).

## Archive

| Key | Value |
|---|---|
| `archive_retention_rule` | `latest_of_each_supported_line` |

Standard default per
[release-distribution](https://infra.apache.org/release-distribution.html):
only the latest version of each supported line stays on
`dist/release/magpie/`; superseded versions move to
`archive.apache.org`.

## Audit log

| Key | Value |
|---|---|
| `audit_log_path` | `audit/releases/` |

`release-audit-report` appends one markdown record per release at
`audit/releases/<version>.md`, proposed as a PR — never committed
directly.

## Category-X dependency denylist

| Key | Value |
|---|---|
| `category_x_dependencies` | *(empty — no known Category-X dependencies)* |

The [ASF Category-X list](https://www.apache.org/legal/resolved.html#category-x)
is the fallback; this per-project list is the source of truth for
denial and is the PMC's responsibility to maintain.
