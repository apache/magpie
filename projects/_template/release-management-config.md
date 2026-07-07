<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Apache Airflow: release-management configuration (filled example)](#apache-airflow-release-management-configuration-filled-example)
  - [Identifiers](#identifiers)
  - [Backends](#backends)
  - [Distribution URLs](#distribution-urls)
  - [Signing](#signing)
  - [Vote](#vote)
    - [Approval, non-list variants](#approval-non-list-variants)
  - [Announce](#announce)
    - [Announce, non-list variants](#announce-non-list-variants)
  - [Archive](#archive)
  - [Audit log](#audit-log)
  - [Category-X dependency denylist](#category-x-dependency-denylist)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Apache Airflow: release-management configuration (filled example)

**This file is a placeholder ahead of the release-management skill
family landing.** None of the `release-*` skills exist in the
framework yet (the family is proposed per
[`docs/release-management/README.md`](../../docs/release-management/README.md)
and [`docs/modes.md`](../../docs/modes.md#drafting)). The keys
below match the
[release-management spec](../../docs/release-management/spec.md#adopter-contract)
and are the values the future skills will read. New adopters
should copy this file into their own
`<project-config>/release-management-config.md` and replace every
Airflow-specific value with their project's equivalents.

This file is the *family-wide* contract. Three related scaffolds
ship in the same adopter directory and are referenced from here:

- [`release-build.md`](release-build.md), build invocation,
  expected artefact list, digest set, binary-exclude rules.
- [`release-trains.md`](release-trains.md), existing scaffold,
  shared with the security family (release-train identity).
- [`pmc-roster.md`](pmc-roster.md), PMC member roster used by
  `release-vote-tally` to classify binding vs non-binding votes.
- [`site-repo.md`](site-repo.md), site-bump PR target for
  `release-announce-draft`.

## Identifiers

| Key | Value |
|---|---|
| `project_dist_name` | `airflow` |
| `release_planning_issue_template` | `<project-config>/release-planning-issue.md` |
| `release_branch_base` | `main` |
| `version_manifest_files` | `setup.cfg`, `airflow/__init__.py` |

## Backends

Three switches select the backend each skill in the family emits
commands against. See
[`process.md` § Adopter backends](../../docs/release-management/process.md#adopter-backends)
for the dimensions.

| Key | Value | Allowed values |
|---|---|---|
| `release_dist_backend` | `svnpubsub` | `svnpubsub`, `atr`, `github-releases`, `s3`, `self-hosted` |
| `release_approval_mechanism` | `dev-list-vote` | `dev-list-vote`, `github-discussion`, `pr-approval`, `maintainer-roster` |
| `release_announce_backend` | `announce-list` | `announce-list`, `github-release-notes`, `site-post`, `discord-channel` |

ASF TLPs are pinned to `dev-list-vote` (mandatory per
[`release-policy.html § release approval`](https://www.apache.org/legal/release-policy.html#release-approval))
and `announce-list` (mandatory per
[`release-policy.html § announcements`](https://www.apache.org/legal/release-policy.html#release-announcements));
`release-vote-tally` and `release-announce-draft` refuse to run an
ASF TLP release against any other value.

`atr` selects the **[Apache Trusted Releases](https://release-test.apache.org/)**
platform: the RM composes a signed candidate in ATR (which runs the
signature/checksum/license/notice/source-header checks on upload),
ATR drives the `dev@` `[VOTE]` and tabulation, and *finishing*
publishes to `dist.apache.org`. It is an ASF-only backend and an
alternative to `svnpubsub` for the same `dev-list-vote` /
`announce-list` approval and announce mechanisms. See the
[ATR release runbook](../../docs/release-management/atr-release-runbook.md)
for the phase-by-phase flow. ATR is in alpha; until a PMC ratifies it,
`svnpubsub` remains the ratified default.

Non-ASF adopters set the values their workflow uses; the skills
emit backend-shaped paste-ready commands per
[spec § Per-skill specifications](../../docs/release-management/spec.md#per-skill-specifications).
The state-change boundaries are backend-independent.

## Distribution URLs

| Key | Value |
|---|---|
| `release_dist_url_template` | `https://dist.apache.org/repos/dist/<bucket>/airflow/<version>/` |
| `archive_url_template` | `https://archive.apache.org/dist/airflow/` |
| `release_publish_command_template` | *(`svnpubsub` default; non-ASF adopters override with backend-specific command, e.g. `gh release upload <version> <artefacts>` for `github-releases`, `aws s3 cp --recursive <local> s3://<bucket>/<version>/` for `s3`)* |

`<bucket>` resolves to `dev` (staging) or `release` (promoted)
depending on the lifecycle step the skill is executing. The
`<bucket>` semantics are `svnpubsub`-shaped; backends that have no
staging area (`github-releases` draft, `s3` versioned prefix) use
the analogous draft/promote convention and document it in
`release_publish_command_template`.

## Signing

| Key | Value |
|---|---|
| `keys_file_url` | `https://dist.apache.org/repos/dist/release/airflow/KEYS` |
| `keyserver` | `keys.openpgp.org` |
| `rm_key_fingerprint` | *(per-RM; lives in `.apache-magpie-overrides/user.md` under `release_manager.gpg_fingerprint`)* |

The agent never reads or stores the private key half. The
fingerprint is the only signing-related value the skill consumes;
it uses the fingerprint to fetch the *public* counterpart from the
keyserver and verify that the matching public block already
appears in `KEYS` (or draft a `KEYS` diff to add it via
`release-keys-sync`).
See
[spec § Boundary 1](../../docs/release-management/spec.md#boundary-1-agent-never-holds-the-rms-signing-key).

## Vote

Applies when `release_approval_mechanism = dev-list-vote`. Other
mechanisms read their own key set (see *Approval, non-list
variants* below).

| Key | Value |
|---|---|
| `vote_dev_list` | `<dev-list>` *(e.g. `dev@airflow.apache.org`)* |
| `mail_archive` | `ponymail` |
| `mail_archive_url_template` | `<mail-archive-url>` *(ASF e.g. `https://lists.apache.org/list.html?<dev-list>`)* |
| `vote_window_hours` | `72` |
| `vote_pass_rule_overrides` | *(none, uses ASF baseline: 3 binding +1 minimum, more binding +1 than -1)* |
| `vote_subject_template` | `[VOTE] Release <Product Name> <version> from <version>-rcN` |
| `result_subject_template` | `[RESULT] [VOTE] Release <Product Name> <version> from <version>-rcN` |
| `release_approver_roster_path` | `<project-config>/pmc-roster.md` *(ASF default); non-ASF: e.g. `<project-config>/release-approvers.md`)* |

The configured `vote_window_hours` is a floor per
[`release-policy.html § release approval`](https://www.apache.org/legal/release-policy.html#release-approval).
Projects may extend (e.g. `120` for a longer window) but not
shorten.

`vote_pass_rule_overrides` can only *strengthen* the baseline
(e.g. require 5 binding +1 instead of 3). Attempts to weaken the
baseline are refused by `release-vote-tally`.

### Approval, non-list variants

| Mechanism | Required keys | Notes |
|---|---|---|
| `github-discussion` | `approval_discussion_repo`, `approval_discussion_category`, `approval_window_hours`, `release_approver_roster_path` | `release-vote-draft` opens the discussion; `release-vote-tally` reads reactions/replies and classifies binding-vs-non-binding against the roster. |
| `pr-approval` | `approval_pr_branch_pattern` (e.g. `release/<version>`), `approval_pr_min_approvals`, `release_approver_roster_path` | `release-vote-draft` opens a `release-<version>` PR; `release-vote-tally` reads GitHub PR approvals from roster members. |
| `maintainer-roster` | `release_approver_roster_path`, `approval_window_hours` | Off-band approval signal; the RM records signed approvals manually, the skill verifies count + roster membership. |

## Announce

Applies when `release_announce_backend = announce-list`. Other
backends read their own key set (see *Announce, non-list
variants* below).

| Key | Value |
|---|---|
| `announce_list` | `announce@apache.org` |
| `announce_cc_lists` | `<dev-list>`, `<users-list>` *(e.g. `dev@airflow.apache.org`, `users@airflow.apache.org`)* |
| `announce_subject_template` | `[ANNOUNCE] <Product Name> <version> released` |
| `site_repo` | `<site-repo>` *(e.g. `apache/airflow-site`)* |
| `site_pr_files` | `landing-pages/site/content/en/_index.md`, `landing-pages/site/content/en/announcements/<version>.md` |

`announce@apache.org` is mandatory for ASF TLP releases per
[`release-policy.html § announcements`](https://www.apache.org/legal/release-policy.html#release-announcements).

### Announce, non-list variants

| Backend | Required keys | Notes |
|---|---|---|
| `github-release-notes` | `release_repo` (target repo for `gh release create --notes-file`) | `release-announce-draft` writes the body to the GitHub Release page; no separate site bump unless `site_repo` is also set. |
| `site-post` | `site_repo`, `site_pr_files`, `site_post_template` | Static-site post is the announcement; no mailing list send. |
| `discord-channel` | `discord_webhook_url_key` (name of secret holding the webhook URL), `discord_message_template` | The webhook URL itself never lives in this file; the skill reads it from the per-user secrets store named here. |

## Archive

| Key | Value |
|---|---|
| `archive_retention_rule` | `latest_of_each_supported_line` |

Default per
[`release-distribution`](https://infra.apache.org/release-distribution.html):
only the latest version of each supported release line stays on
`dist/release/`; older versions move to `archive.apache.org`.
Projects with longer support windows can name additional lines
to retain (e.g. `2.x-stable`), but cannot remove the latest-of-
each-line floor.

## Audit log

| Key | Value |
|---|---|
| `audit_log_path` | `<adopter-repo>/audit/releases/` |

`release-audit-report` appends one markdown record per release at
`<audit_log_path>/<version>.md`. The append is proposed as a PR
on the adopter repo, never committed directly.

## Category-X dependency denylist

| Key | Value |
|---|---|
| `category_x_dependencies` | *(empty for the template, populated per project)* |

The release-prepare skill refuses to advance the prep PR if any
identifier in this list appears in the dependency tree of the
target version. The list is the project's curated subset of the
[ASF licensing-howto Category-X list](https://www.apache.org/legal/resolved.html#category-x);
the broader Category-X list itself is consulted by the skill as a
fallback, but the per-project list is the source of truth for
denial. Reviewing and updating this list is the PMC's
responsibility, not the skill's.

Example shape (replace with the project's actual entries):

```yaml
category_x_dependencies:
  - "com.example:gpl-licensed-lib"   # GPL-2.0, Category-X
  - "another-pkg::cc-by-nc"          # CC-BY-NC, Category-X
```
