<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

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
> **Hybrid backend while ATR is in alpha: SVN for artefacts, ATR for the
> vote.** The two concerns are decoupled:
> - **`release_dist_backend = svnpubsub`** — the signed artefacts are
>   staged to `dist/dev/` and promoted to `dist/release/` on
>   `dist.apache.org` by `svn mv`, per the
>   [`svnpubsub` runbook](../../docs/release-management/svn-release-runbook.md).
>   SVN remains the **durable, ASF-hosted, canonical** home of the release
>   bits. ATR's **Finish**/publish is **not** used while this is
>   `svnpubsub`.
> - **`release_vote_backend = atr`** — the mandatory `dev@` `[VOTE]` is
>   administered by the [ATR platform](../../docs/release-management/atr-release-runbook.md):
>   the signed artefacts are *also* uploaded to ATR (Compose) so it runs
>   the signature / checksum / licence / source-header checks and then
>   **sends and tabulates** the `[VOTE]`. This is why artefacts land in
>   **both** places during the RC.
>
> **Why the split:** ATR is in **alpha**, so we do not yet trust it to
> *host or publish* the release (that stays on SVN, ratified). But its
> automated checks and vote administration are useful now. Full adoption
> (flipping `release_dist_backend` to `atr`, so ATR also hosts/publishes
> via Finish) is **pending a PMC ratification vote on `dev@`** and a move
> of ATR from alpha to beta/GA. After that, set `release_dist_backend =
> atr` and drop the SVN staging/promote steps; the approval and announce
> mechanisms are backend-independent and need no change.

## Identifiers

| Key | Value |
|---|---|
| `project_dist_name` | `magpie` |
| `product_name` | `Apache Magpie` |
| `upstream` | `apache/magpie` |
| `git_upstream_remote` | `upstream` |
| `release_planning_issue_template` | *(none — uses the `release-prepare` default template)* |
| `release_branch_base` | `main` |
| `version_manifest_files` | `pyproject.toml` |

## Backends

| Key | Value | Allowed values |
|---|---|---|
| `release_dist_backend` | `svnpubsub` | `svnpubsub`, `atr`, `github-releases`, `s3`, `self-hosted` |
| `release_vote_backend` | `atr` | `manual`, `atr` |
| `release_approval_mechanism` | `dev-list-vote` | `dev-list-vote`, `github-discussion`, `pr-approval`, `maintainer-roster` |
| `release_announce_backend` | `announce-list` | `announce-list`, `github-release-notes`, `site-post`, `discord-channel` |

As an ASF TLP, Magpie is pinned to `dev-list-vote` (mandatory per
[release-policy § release approval](https://www.apache.org/legal/release-policy.html#release-approval))
and `announce-list` (mandatory per
[release-policy § announcements](https://www.apache.org/legal/release-policy.html#release-announcements)).

`release_dist_backend = svnpubsub` stages the RC under `dist/dev/` and
promotes to `dist/release/` on `dist.apache.org` by `svn mv`; see the
[`svnpubsub` runbook](../../docs/release-management/svn-release-runbook.md).
Flipping it to `atr` (after PMC ratification) instead drives compose /
check / vote / **finish** — including hosting and publishing — through the
ATR platform; see the [ATR release runbook](../../docs/release-management/atr-release-runbook.md).

`release_vote_backend` selects how the mandatory `dev-list-vote` is
*administered*, independently of where the artefacts are hosted:
- `manual` — the RM sends the `[VOTE]` email by hand and tallies replies
  from the mail archive (the classic flow the `svnpubsub` runbook
  describes).
- `atr` — the signed artefacts are uploaded to ATR (Compose) so it runs
  the automated policy checks and then **sends and tabulates** the `[VOTE]`
  on `dev@`. **`release_vote_backend = atr` with `release_dist_backend =
  svnpubsub` is the current hybrid** (see the callout above): SVN hosts and
  promotes; ATR only checks and drives the vote. ATR's Finish/publish is
  not used until `release_dist_backend` itself becomes `atr`.

## Distribution URLs

| Key | Value |
|---|---|
| `release_dist_url_template` | `https://dist.apache.org/repos/dist/<bucket>/magpie/<version>/` |
| `archive_url_template` | `https://archive.apache.org/dist/magpie/` |
| `atr_platform_url` | `https://release-test.apache.org/` *(used whenever `release_vote_backend = atr` or `release_dist_backend = atr`; alpha host, production will be `release.apache.org`)* |

On the `svnpubsub` dist backend, `<bucket>` resolves to `dev` while the
RC is staged for the vote and `release` after promotion. Under the
current hybrid (`release_dist_backend = svnpubsub`, `release_vote_backend
= atr`) the artefacts live in `dist/dev/magpie/<version>-rcN/` **and** are
uploaded to ATR's candidate area for the checks + vote — but promotion is
still `svn mv dist/dev → dist/release`, not ATR Finish. Only once
`release_dist_backend = atr` (post-ratification) does the RC live solely
in ATR and **Finish** publish to `dist/release/magpie/`.

## Signing

| Key | Value |
|---|---|
| `keys_file_url` | `https://dist.apache.org/repos/dist/release/magpie/KEYS` |
| `keyserver` | `keys.openpgp.org` |
| `rm_key_fingerprint` | *(per-RM; lives in the RM's `user.md` under `release_manager.gpg_fingerprint`)* |

The RM signs each artefact and the public key must be in `KEYS` (and,
whenever `release_vote_backend = atr` or `release_dist_backend = atr`,
also registered in the ATR platform, which validates candidate signatures
during Compose — see the ATR runbook, Step B). The agent never holds the
private key half.

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
The ≥72h window and the binding-vote rule are backend-independent; when
`release_vote_backend = atr` the platform sends the `[VOTE]` to
`vote_dev_list` and tabulates replies, but the window and rule are
unchanged (ATR *drives* the mandatory `dev@` vote, it does not replace the
PMC's binding decision). The `[VOTE]` body still points voters at the SVN
`dist/dev/magpie/<version>-rcN/` staging URL for downloads while
`release_dist_backend = svnpubsub`.

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
