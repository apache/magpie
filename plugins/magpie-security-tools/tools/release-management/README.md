<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [`release-management`](#release-management)
  - [Prerequisites](#prerequisites)
  - [How to use](#how-to-use)
  - [Commands](#commands)
    - [`rc-cut`](#rc-cut)
    - [`verify-rc`](#verify-rc)
    - [`vote-draft`](#vote-draft)
    - [`vote-tally`](#vote-tally)
    - [`promote`](#promote)
    - [`announce-draft`](#announce-draft)
    - [`prepare`](#prepare)
    - [`archive-sweep`](#archive-sweep)
    - [`audit-report`](#audit-report)
    - [`keys-sync`](#keys-sync)
  - [Tests](#tests)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# `release-management`

**Capability:** substrate:release

**Harness:** agnostic

The deterministic core of the `release-management` skills.
[`release-config`](../release-config/README.md) resolves the configuration and runs each skill's Step 0;
this tool takes what `release-config load` printed and renders everything the skill hands the release manager:
paste-ready command blocks, mail drafts, planning-issue comments;
for `release-verify-rc` it also classifies the output of each check the voter ran,
for `release-archive-sweep` it applies the retention rule, for `release-audit-report` it renders and validates the audit record,
and for `release-keys-sync` it decides from [`release-verify list-keys`](../release-verify/README.md) output whether the RM's key is already in `KEYS`.
The agent presents the output and keeps only the judgement; the release manager runs every command on their own machine.

**It runs nothing.**
No command here invokes `git`, `gpg`, `svn`, `gh`, `aws` or `atr`, reads a key, sends mail, posts a comment, opens a PR, applies a label, casts a vote or touches the network.
A render that would emit something a skill must refuse (a `dist/release/` staging target, an MD5 or SHA-1 digest, an unconfigured backend)
exits `2` with `{"ok": false, "refused": "<why>"}` instead of printing a block.

## Prerequisites

- **Runtime:** Python 3.11+, stdlib only; run with `uv run --project <framework>/tools/release-management`.
- **CLIs:** None. It reads files the agent saved: `release-config load` output, and text the release manager pasted back.
- **Credentials / auth:** None.
- **Network:** None; it never opens a connection.

## How to use

Save the configuration once per skill run, then render each step from it:

```bash
uv run --project <framework>/tools/release-config release-config load \
  --skill rc-cut <version> <rcN> > <scratch>/rc-cut-load.json
uv run --project <framework>/tools/release-management release-management rc-cut render \
  --step 2 --load <scratch>/rc-cut-load.json --upstream <upstream> --project <project> \
  --framework <framework>
```

Every command prints one JSON object: the step's contract as the skill documents it, plus `text`, the block to show the release manager.
`--framework` is the framework root, quoted into every `repro-archive` command a block carries;
it defaults to the checkout the tool runs from, and a render that needs it refuses when neither is known.
No rendered command carries a bare `<placeholder>` where the shell would read a redirect.

## Commands

### `rc-cut`

| Command | Prints |
|---|---|
| `tag-exists --refs <file> <version>-<rcN>` | `rc_tag_exists`: whether `refs/tags/<version>-<rcN>` is among the refs the `tags` read printed. Exact match only, so `rc1` is not found among `rc10`. An empty read is `false`; a read holding any line that is not a `refs/tags/` ref is `null`, with a `blocker`. |
| `render --step 2` | Sections 1–4: signed tag and push, the source build (`repro-archive build` for `git-archive`, the verbatim `build_command` for `custom`, both under `SOURCE_DATE_EPOCH`), one block per convenience artefact, one `gpg --detach-sign --armor` per artefact and one checksum per artefact and digest. Sections 3–4 are empty under `signing_mode: ci-automated`. |
| `render --step 2b [--skip-repro-check] [--epoch N]` | The reproducibility self-check: a detached worktree of the RC tag at `rebuild/src` where every build command runs, source lint, rebuild and `compare --require-identical`; one rebuild-and-compare block per convenience artefact by its own `reproducibility` mode, rendered with its own `version`; then the worktree's removal. Skipped when the source check is off and no artefact resolves to a mode other than `off`, or on `--skip-repro-check` unless `ci-automated` makes it mandatory. |
| `render --step 2c` | The CI-signed trigger sequence and the trusted-hardware hand-off (`ci-automated` only). |
| `render --step 3 [--asf-id ID]` | Backend-shaped staging (`svnpubsub`, which requires `--asf-id`; `atr`, the Compose upload; `github-releases`, `s3`, `self-hosted`), the ATR upload block when `vote_backend` is `atr` under another dist backend (never a Finish/publish), and each `registry-staging` artefact's `stage_command`, rendered with its own `version`. |
| `render --step 4 [--record F] [--self-check S] [--convenience-outcome NAME=RESULT …] [--run-url U] [--allow-unreviewed-archive [WHY]]` | The planning-issue comment: RC id, tag and staging URLs, artefacts, the reproducibility record parsed from what `repro-archive build` printed (first occurrence of each key; `sha512` only as 128 hex digits), convenience artefacts with their own outcome (`skipped` when their reproducibility is `off`, else `unreported`, unless given), the override line and the `rc-staging` label. `record_missing` names what the release manager has not pasted back yet, including `self_check` under `ci-automated`. |

Custom builds print a reproducibility record after building: the tagged commit, epoch, SHA-512 checksum, and archive and repository SWHIDs.
Rebuild blocks preserve shell comments and heredocs and stop if the checkout cannot be entered.
The Step 2b contract reports effective per-artefact modes and uses `mixed` when active binary modes differ.

Refusals, in code rather than prose:

- **`dist/release/`** — a `svnpubsub` staging URL is normalised (`//`, `.`, `..`) and refused unless it sits under `/repos/dist/dev/` (the promotion-path denylist).
- **MD5 / SHA-1** — a `digest_set` naming either is refused, as is any digest other than `sha512` / `sha256`.
- **Unconfigured backends** — `self-hosted` without `release_publish_command_template`, an unknown backend, or Step 3 under `ci-automated`.
- **Failed reproducibility** — Step 4 refuses `differs` outcomes and `content-identical` where byte identity is required, before proposing `rc-staging`.
- **Missing inputs** — `svnpubsub` staging without `--asf-id`, or a `repro-archive` command with no known framework root (`--framework`).

### `verify-rc`

Every command takes `--load <file>` (what `release-config load --skill verify-rc <version>-rcN` printed) except `source-tree`,
and reads the files the agent saved from a check's own run: a tool's JSON, RAT's output, the Nexus probe output.
It never runs `gpg`, `curl`, RAT, a rebuild or any other check.
Until it has every input a step needs, it prints `status: null` and `pending`, naming what is missing.

| Command | Prints |
|---|---|
| `args [--staging-copy D] [--keys-file F] [--unpacked-dir D] [--previous-dir D]` | `commands`: the `release-verify` invocation of each of Steps 1–3 and 5–8 and `all`, one `--expect` per required and `--expect-optional` per optional expected artefact (in order), `--digest` (sha512 always, sha256 when listed; md5 never), `--prohibit` / `--accept` from the Binary-exclude list, `--validator`, `--manifest`; plus `unpacked_dir`. |
| `rat [--exit-code N] [--report F]` | Step 4: `paste_recipe` from the RAT config and excludes paths; `PASS` on exit 0 with nothing listed, `FAIL` on a non-zero exit or any `unapproved_files` (parsed from `!?????` lines and the `Files with unapproved licenses:` block); `SKIP` with `status: WARN` when no RAT configuration is declared. |
| `source-tree --symlinks F --validator-result CODE[:DETAIL]…` | Step 7: a `release-verify symlinks` `REVIEW` resolved from each validator's exit code (any non-zero → one `validator_failures` entry, `FAIL`); a tool `FAIL` / `PASS` / `SKIP` is final. |
| `jvm --inventory F [--staged-dir D] [--tree D] [--report F]` | Step 6b: `SKIP` without a `.jar` / `.pom` or under `jvm_artefact_checks: off`; the `maven-artifact-verify` recipe (`--digests` from `jvm_digest_set`, else the digest set; `--podling` only when `DISCLAIMER` / `DISCLAIMER-WIP` sits at the tree root); with `--report`, the step's JSON: findings for every non-passing check, `ABSENT` a `FAIL` only under `jvm_companion_location: staged`, observations that never change the status, and one `gpg --verify` per companion whose `.asc` is staged. |
| `nexus --inventory F [--issue-body F] [--rm-credentials] [--not-probed \| --existence-code N] [--state F] [--profile F] [--crawl F]` | Step 6c: the gates (JVM artefacts, checks on, organization `ASF`, a resolvable id), the id-shape check (`^orgapache[a-z0-9]+-[0-9]+$` or `snapshots`, else a `SKIP` naming the value — the id is spliced into `curl` URLs), the read-only recipe (anonymous existence and crawl; the `--netrc-file` state and profile reads only with `--rm-credentials`), and the classification: `404` not reachable, `open`, snapshots, version mismatch, missing `.asc`, incomplete companion set (`packaging=pom` exempt) as `FAIL`; `STATE-UNVERIFIED` (no credentials, a refused probe, any other code) and stale siblings as `WARN`. |
| `repro [--skip-repro] [--trusted-hardware] [--recorded-commit] [--tag-commit] [--recorded-swhid] [--atr-swhid] [--epoch] [--check F] [--compare F] [--binary NAME=identical\|differs\|known:P]…` | Step 9: whether it runs (`mandatory` under `ci-automated`, where `--skip-repro` is ignored), the recipe, and the roll-up: the source table (RM-key vs automated signing), the SWHID compared without qualifiers, each convenience artefact by its own mode, `binaries.differs` for `release-promote`. |
| `report --verdict F [--repro F] [--compare F] [--post-to URL] [--trusted-hardware] [--committer H] [--finding S=T]… [--fail-detail T]… [--warn-detail T]…` | Step 10: the report text (with the voter-obligation reminder), and with `--post-to` the comment to propose, carrying the *Reproducibility validated on trusted hardware* attestation only under `ci-automated`, Step 9 `PASS` with every artefact identical, and `--trusted-hardware`. The overall verdict is `release-verify verdict`'s; an unresolved one is refused. |

### `vote-draft`

`--preflight` is what `release-config preflight --skill vote-draft …` printed; `--load` what `release-config load --skill vote-draft <version>-rcN` printed.

| Command | Prints |
|---|---|
| `verdict --preflight F [--planning-issue U] --verify-rc-verdict PASS\|PASS-WITH-WARNINGS\|FAIL\|none [--verify-rc-for <version>-rcN]` | The Step 0 JSON: the preflight blockers, plus one for a missing planning issue and the verify-rc gate. A `PASS` counts only for this exact RC (`rc10` is not `rc1`); `FAIL` or no comment blocks; an accepted `--skip-verify-check` resolves it; `PASS-WITH-WARNINGS` proceeds with a warning. |
| `render --step 2 --load F --product-name N --tag-url … --changelog-url … [--svn-revision R] [--rc-comment F \| --repository/--commit/--swhid/--epoch/--sha512] [--canned-body F] [--expedited R] [--skip-verify-check R] [--atr-candidate-url U] [--atr-revision R] [--planning-issue U] [--project P] [--rm-name N]` | The `[VOTE]` subject (`vote_subject_template`) and body: the default template or the canned one with its placeholders substituted, the SVN revision (`svnpubsub`), the convenience-artefact block, the *How to verify* section (only the reproducibility-record lines the planning issue provides, the fixed *Agentic path* paragraph, the manual links, the ATR candidate page, the CI-signed paragraph, the voter-obligation sentence; appended to a canned body that lacks it; a canned body that has its own section is kept, with a warning and `canned_verify_missing` naming each mandatory item it leaves out: the SWHID, the ATR candidate page, the trusted-hardware reminder), the `[EXPEDITED]` / `[SKIP-VERIFY]` notices; and `atr_vote_command` under `vote_backend = atr`. The record is parsed from release-rc-cut's own planning-issue comment. |
| `render --step 3 --load F --product-name N --sent-at T [--subject S] [--expedited R]` | The planning-issue comment, standard or expedited, with the window close `--sent-at` + `vote_window_hours` in UTC. |

Refused (exit `2`): a missing staging, tag, changelog or KEYS URL; no `--svn-revision` under `svnpubsub`; no `--atr-candidate-url` under `atr`; a window below 72 hours without `--expedited`.
An `--expedited` reason naming a CVE or a security fix comes back as a `warnings` entry: rewording it is the agent's judgement.

### `vote-tally`

| Command | Prints |
|---|---|
| `verdict --preflight F [--planning-issue U] [--comments F] [--ambiguous-note-acknowledged]` | The Step 0 JSON: the preflight blockers, plus one for a missing planning issue and one for an `AMBIGUOUS` note a previous run left on it, until the RM has answered it. |
| `archive-url --load F` | `mail_archive_url_template` rendered for the vote list. |
| `preclassify --replies F` | `parsed_value` for every bare vote line (`+1`, `0`, `+0`, `-0`, `-1`, `+0.x`, optionally `(binding)` / `(non-binding)`); anything else is `needs_judgement`, for the agent. |
| `tally (--votes F \| --pr-reviews F [--login-map F]) --roster F [--mechanism M] [--force-close] [--overrides J] [--min-approvals N]` | `--pr-reviews` takes the release PR's gh `reviews` JSON: each reviewer's latest review is their vote (`APPROVED` +1, `CHANGES_REQUESTED` -1, `DISMISSED` none; `COMMENTED` skipped), logins mapped to roster emails by `--login-map`, with `pr_reviewers` saying what decided each. Binding resolution against the roster, one person one vote, fractional votes non-binding, `AMBIGUOUS` never counted (a halt without `--force-close`), and the pass rule: the ASF baseline, strengthened only, for `dev-list-vote`; `approval_pr_min_approvals` for `pr-approval`. `github-discussion` and `maintainer-roster` have no specified rule, so `result` is `null` for the agent. Reply text never reaches it. Formerly `vote-tally/scripts/tally.py`; its own `parse_roster`, not release-config's. |
| `render --load F --tally F [--product-name N] [--result R --rule T] [--rm-name N]` | The `[RESULT] [VOTE]` subject (`result_subject_template`) and body: PASSED / FAILED, the counts, the outcome lines and proposed label, the per-voter table (no reply text). Refuses a halted tally, and a `null` result without `--result` and `--rule`. |

### `promote`

| Command | Prints |
|---|---|
| `verdict --preflight <file> --target {empty,populated} --upstream O/R --project P [--vote-passed] [--attestation] [--no-planning-issue] [--planning-issue URL]` | The Step 0 JSON: `release-config preflight`'s blockers as written, plus one per planning-issue fact that fails — `vote-passed` absent (no override), the target already populated (hand off to Infra) or its check result unknown, the trusted-hardware attestation missing when `ci-automated` requires it. `rm_is_pmc: false` with nothing else failing is `handoff-non-pmc`. Fail-closed: an unset flag is the blocking side. `read` names the blocker / outcome file to load; `scope` records the release it is for (`project`, `upstream`, `dist_backend`, `staging_url`, `target_url`). |
| `render --load <file> --verdict <file> --upstream O/R --project P [--rm ID --roster-path P] [--apache-id] [--result-vote-url] [--rc-commit-sha] [--draft-tag T [--draft-tag-confirmed]]` | The Step 2 JSON: `command_block` shaped by `dist_backend` — `svn mv` + `svn list` + the final signed `<version>` tag on the RC commit (`svnpubsub`), `gh release edit --draft=false --prerelease=false --tag` (`github-releases`), `aws s3 mv --recursive` between the rendered staging and target URLs as `s3://` URIs, key prefix kept (`s3`), or `release_publish_command_template` (`self-hosted`); a held convenience artefact staged with the source is left out before the promotion runs with its `.asc` and one `.<digest>` file per `digest_set` entry (`svn rm … &&`, `--exclude`, `gh release delete-asset … &&`) — then the hand-off note (from a `handoff-non-pmc` verdict), the convenience artefacts (publish commands verbatim, a HOLD note per held artefact) and the mandatory mirror note. Refuses a verdict other than `proceed` / `handoff-non-pmc` or whose version, RC or `scope` differs from the load, a `--handoff` that disagrees with it, `self-hosted` without its template or with a held artefact staged with the source, a held staged name that is not one plain file name or a `digest_set` digest other than sha512 / sha256, an unreadable S3 bucket, `github-releases` without `--draft-tag` or with an unconfirmed discrepancy, `atr` (not supported yet) and an unknown backend. |

### `announce-draft`

| Command | Prints |
|---|---|
| `verdict --preflight <file> [--promoted] [--no-planning-issue]` | The Step 0 JSON: the preflight blockers as written (the promote-wait blocker verbatim), plus one when `promoted` is absent and one when a non-ASF project leaves `release_announce_backend` unset; `promote_clear_after_utc` is kept only while the gate is the sole blocker. |
| `render --step 2 --load <file> --product-name N --download-page U --changelog-url U [--skip-promote-wait R] [--canned-body F] [--convenience KIND=LOC …]` | The subject from `announce_subject_template` and the body for `release_announce_backend`: the `[ANNOUNCE]` email with `To:` / `Cc:` and the `@apache.org` reminder (`announce-list`), or the `github-release-notes`, `site-post` and `discord-channel` shapes. A `canned_body` gets its placeholders substituted (and the reminder prepended if it never names a bare `@apache.org`). Warns when the Download Page is a `dist.apache.org` URL. |
| `render --step 3 --load <file> --product-name N [--files F …] [--confirm-extra F …]` | The site-bump PR title, body and `gh pr create --web` line; `scope_violations` is the proposed files minus `site_pr_files` until the RM confirms them. The skip signal when `site_repo` is unset. |

### `prepare`

`--preflight` is what `release-config preflight --skill prepare …` printed; `--load` what `release-config load --skill prepare …` printed;
`--prs` what `gh pr list --json number,title,url,labels,mergedAt` printed.
Formerly skill-local scripts: `prev-tag`, `category-x` and `next-dev-version` print what `prev_tag.py`, `category_x.py` and `next_dev_version.py` printed, and exit `2` with `{"error"}` on bad input.

| Command | Prints |
|---|---|
| `verdict --preflight F [--planning-issue U --planning-label L …] [--gh-access] [--previous-tag T] [--train-confirmed]` | The Step 0 JSON: the preflight blockers as written, plus one when no `release_lines` entry covers `<version>` (a train pattern such as `2.x` containing it, or the version itself; the `prev-tag` train matching), when no line names a train or version at all until `--train-confirmed`, when `prep` / `post` has no planning issue or it lacks `release-planning` / `announced`, and when `--gh-access` is absent. Fail-closed. |
| `prev-tag --tags F --version V [--train T] [--tag-prefix P]` | 1a: the highest final release tag below the version in the train, skipping pre-releases. |
| `plan-query --upstream U --base B [--previous-tag T] [--tag-date D]` | 1a: the `gh api … commits/<tag>` read that dates the tag, and the `gh pr list --search "merged:>=<date>"` query (a non-ISO date is refused). |
| `plan --prs F --version V --product-name N --base B [--previous-tag T] [--upstream U] [--train N] [--rm N] [--template F] [--skip-empty-check [WHY]] [--opened-at T]` | 1a/1b: the empty-set hand-off (`empty_pr_set: true`), or the issue title, body (the default template, or `release_planning_issue_template` with its placeholders filled; PRs numbered and grouped by first label), the quoted `gh issue create` line and `unfilled_placeholders`. |
| `versions --target V PATH=LOCAL…` | 2a: the current version string in each manifest (`release-verify version`'s extraction, reimplemented), `current_dev_version`, and `needs_reading` for a file it cannot read. |
| `category-x --deny ID… PATH=LOCAL…` | 2b: the Category-X hard stop, whole-token and separator-insensitive. |
| `notice (--diff F \| [--old F] --new F)` | 2c: the attribution paragraphs a NOTICE change removes and adds, from a unified diff or from the whole file at both refs (`--old` omitted when the previous tag had none). Whether a removal is justified stays with the agent. |
| `changelog --prs F --version V [--date D] [--load F] [--category LABEL=SECTION…] [--assign N=SECTION…]` | 2d: the entry by section (*Features*, *Bug fixes*, *Documentation*, *Other changes*; `changelog_label_categories` from the config, else the label's words), `changelog_coverage_pct` and `coverage_ok` (≥ 90%), the `uncategorised` PRs. |
| `archive-mode --load F [--review-archive] [--previous-tag T]` | 2e: `full` (`export_ignore_reviewed` unset or `--review-archive`), `drift`, or `skipped` (`custom`), and the read-only listings to save into `$TMPDIR`. |
| `archive-review --tracked F [--gitattributes F] [--symlinks F] [--refs F] [--changed F] [--exclude P…] [--keep P…] [--reason P=WHY…] [--load F] [--voter-input P…]` | 2e: every top-level entry in its bucket (`.github/` and the agent-view dirs one level down), `needs_rm` for the *project's call* and unclassified ones, the exclude-bucket entries in `.gitattributes` form (`/file`, `dir/`) with a comment each, `refused` for a never-excludable path, a glob, an entry that would strip an always-shipped file, or one a shipped file references, `violations` for committed entries that already strip one, `refs_unchecked` (the block stays empty until each proposed path is reference-checked), the shipped symlinks that chain or whose target would be stripped, the `git grep` loop (appending to the refs file once `--refs` is passed) and the before/after `repro-archive` commands; with `--changed`, the drift check (`archive_review: "skipped"` when nothing new). |
| `prep-pr --load F --version V --product-name N --changelog F [--versions F \| --current-version S] [--previous-tag T] --archive-mode F [--notice-summary S] [--archive-review E] [--archive-entry ENTRY=WHY…] --files F… [--confirm-extra F…]` | 2f: the prep PR title, body and `files_in_scope` / `scope_violations` against the 2f set. Refuses coverage below 90%, an `archive_review` outside the enum, inconsistent with the entries or with `archive-mode` (`skipped` while the review is due), and an unknown current version. |
| `next-dev-version --version V (--config F \| --version-files A,B) [FILE…]` | 14a: the next development version per configured file. |
| `post-pr --next F --load F --product-name N [--next-version V] --files F… [--confirm-extra F…]` | 14b: the post-release bump PR title, body and scope against `version_manifest_files`. Refuses a file with no next version, files that disagree (until `--next-version`), and confirming `NOTICE` / `LICENSE` / the configured `changelog_file`. |
| `signing-eligibility --load F [--verify-rc-identical]` | A1 (🪶 ASF-only): `eligible` and every `missing_conditions` entry — `release_process.automated_signing` offered (`derived.automated_signing_offered`), `git-archive`, `reproducibility_source: on`, `byte-identical` binaries, the verify-rc report (the flag), an `atr` backend. |
| `signing-render --load F --template F --project P [--infra-ticket T]` | A4/A5: the workflow template with the slug, artefact prefix, source format and `build_command`, the unpinned actions, and the `release-management-config.md § Signing` diff. Refuses a slug or prefix it cannot write, a `build_command` that runs a signing tool (`gpg`, `signify`, `cosign sign`, `minisign`) or a key-import action, and any rendered key material or signing step. |

### `archive-sweep`

`--preflight` is what `release-config preflight --skill archive-sweep` printed; `--load` what `release-config load --skill archive-sweep` printed.

| Command | Prints |
|---|---|
| `verdict --preflight F` | The Step 0 JSON: the preflight blockers as written, `non_asf` and `dist_backend`. |
| `listing --load F [--upstream U]` | The read-only listing `command` for `release_dist_backend`: `svn list` of the release directory (`release_dist_url_template`, `release` bucket, cut before the path segment holding `<version>`), `gh release list --exclude-drafts`, `aws s3 ls`; for `atr` (ATR's release list) and `self-hosted` (the adopter's command) a `note` and no command. `read` names the backend file. |
| `trains --load F [--keep N]` | `trains.json` from `release-trains.md`: a release line naming exactly one `N.x` / `N.M.x` train becomes `{"label", "pattern"}`, any other a `loose` train for the agent to place; `keep_decided` is false for a free-text `archive_retention_rule`, whose `keep` is the agent's call. `entry_prefix` / `entry_suffix` are the literal text around `<version>` in its path segment (`v<version>` → `v`), for `retention`. |
| `retention --listing F --trains F` | Per train the newest `keep` (default 1) stay; earlier versions are `past_retention`, versions on no train `orphans`, pre-releases `prereleases` (never counted, never archived; a podling's `-incubating` qualifier is not a pre-release), loose or overlapping matches `unmapped`; `keep` below 1 is a `retention_rule_error` that empties `past_retention`. With a `trains` output naming `entry_prefix` / `entry_suffix`, an entry is read as the version between them (`v1.0.0` → `1.0.0`) and an entry without them is a non-version entry; both are echoed for `render`. Refuses a `trains` output whose `keep_decided` is false unless every train carries an explicit `keep`. Formerly `archive-sweep/scripts/retention.py`. |
| `render --load F --retention F [--upstream U] [--project P] [--command-template T]` | The Step 2 JSON, oldest first: one `svn mv <dist-release> <archive> -m "Archive <project> <ver> per retention policy"` (`svnpubsub`), `gh release delete <tag> --repo <upstream> --yes` plus `deletion_warning` (`github-releases`), `aws s3 mv … --recursive` (`s3`, bucket and key read from both templates as `promote` reads them: path-style or virtual-hosted host, or `s3://`), the adopter's template (`self-hosted`), or the instruction to archive in ATR plus `atr_note` (`atr`, no shell command). URLs and tags put the template's literal text back around the version (`…/v1.0.0`); the archive mirrors the entry name unless `archive_url_template` names `<version>`. Refuses a `retention` output whose entry prefix or suffix differs from the template's, a `retention_rule_error`, an incomplete or absent mapping, a `past_retention` naming a latest-of-line, orphan or pre-release version, `self-hosted` without `--command-template` and an unknown backend; orphans and pre-releases are listed in `not_archived`, never in `commands`. |

### `audit-report`

`--preflight` is what `release-config preflight --skill audit-report <version>` printed, `--load` what `release-config load --skill audit-report <version>` printed,
and `--step1` the Step 1 JSON the RM confirmed (with `redaction_reasons` and `injection_sources` added for Step 2).
`--schema` is the skill's `audit-record-schema.md`; without it the framework copy is read.
It never searches a mail archive, reads the planning issue, runs `svn` or opens a PR.

| Command | Prints |
|---|---|
| `verdict --preflight F [--planning-issue REF] [--upstream U] [--searched TERM]` | The Step 0 JSON: the preflight blockers as written, plus one when no planning issue was found (naming the search term and `--planning-issue`) or the reference is not a GitHub issue; `planning_issue_url` normalised to `https://github.com/<org>/<repo>/issues/<n>` from a URL, an `<org>/<repo>#<n>` or (with `--upstream`) a `#<n>` reference. |
| `gather --load F [--rc rcN] [--schema F]` | Step 1's reading plan: `product_name` (`product_name`, else `project_dist_name`); per lifecycle URL the `subject` from `vote_subject_template` / `result_subject_template` / `announce_subject_template`, the search `query` (the subject up to anything unrendered), every list to search (the `[ANNOUNCE]` under `announce_list` and each `announce_cc_lists` entry) with `mail_archive_url_template` rendered for it, and the PonyMail permalink shape; `svn info --show-item last-changed-revision <dist-release-url>` for `svnpubsub` (no recipe for other backends); `required_fields`. |
| `voters --voters F --roster F` | `[RESULT]` binding voters as roster handles, resolved with `vote-tally`'s binding rules (primary email, else `<id>@apache.org`; a bare Apache ID as written); the roster's GitHub column when it has one, else the Apache ID. A voter the roster does not resolve is in `unresolved` and never cited; none resolved is `MISSING`. |
| `check --step1 F [--schema F] [--not-ponymail]` | `fields_missing`, `fields_redacted` and `schema_violations` before Step 2, `input_gaps` (a reason or injection source missing), and `problems`: a link that is not a plain `https://` URL, a `lists.apache.org` URL that is not a `/thread/<id>` permalink, an email address or a non-handle among the voters, a non-canonical planning-issue URL. |
| `record --step1 F [--schema F]` | The Step 2 JSON: `record_markdown` with `_MISSING_` / `_REDACTED — <reason>_` markers and every value escaped, the sentinel lists, `schema_violations`, `input_gaps`; refuses an email voter and a link that is not plain `https://`. Formerly `audit-report/scripts/render_record.py`. |
| `pr --step1 F --audit-log-path P [--upstream U] [--base B] [--body-file F]` | The Step 3 JSON: `target_file` `<audit_log_path>/<version>.md`, the default title, the body with the missing and redacted (with reasons) paragraphs only when non-empty, `proposed: true`, and `gh_command`, the `gh pr create --web` line with every value quoted (`--base` defaults to the `<default-branch>` placeholder: pass `upstream_default_branch`). Refuses a non-canonical planning-issue URL. |

### `keys-sync`

`--preflight` is what `release-config preflight --skill keys-sync …` printed, `--load` what `release-config load --skill keys-sync` printed.
Each `--…-listing` is what [`release-verify list-keys --file <file>`](../release-verify/README.md) printed for the KEYS file or for the key fetched from the keyserver.
release-verify reads the keys with gpg in a throwaway `GNUPGHOME`; this tool never does.

| Command | Prints |
|---|---|
| `verdict --preflight F [--keys-listing F] [--key-listing F]` | The Step 0 JSON. The preflight blockers come through as written. The fingerprint (primary or subkey) not in KEYS → `proceed`. In KEYS, and any UID the keyserver reports is one of that entry's UIDs → `noop`, with `noop_reason` naming the shared UID (UIDs are compared as sets, never by the keyserver's order). In KEYS under none of the keyserver's UIDs, or the keyserver has no key or UID to compare → `blocked`, the Golden rule 4 hand-off naming both UIDs. A KEYS file with no key → `blocked`. While a listing it needs is missing, `verdict` is `null` and `pending` names the listing. `read` names the outcome file. |
| `check --key-listing F --fingerprint FP [--today D]` | The Step 1 JSON. Floor: RSA and DSA ≥ 2048 bits; EdDSA and ECDSA on an accepted curve (secp256k1 refused); DSA advisory. A revoked, invalid, disabled or expired key is `blocked`; an expiry within 90 days is an advisory. It also needs a usable signing-capable key: a primary without the sign capability (certify only, by gpg's `caps`) needs a signing subkey that meets the same floor, validity and expiry rules; `signers` lists the compliant ones, and a listing without `caps` keeps the primary as the signer. A listing that is release-verify's `error` (a gpg failure, a malformed key block) exits `2`, never `key_found: false`. Formerly `keys-sync/scripts/check_key.py`. |
| `keys-dir --keys-url U` | `keys_file_url` minus `/KEYS`; `error` for a `dist/dev` URL or one not ending in `/KEYS`. |
| `render --step 2 --preflight F --load F --check F --key-file F --key-listing F [--backend svnpubsub\|atr\|git\|generic]` | `keys_block_to_append` (`# <uid>` plus the one armoured public block; refused unless `--key-listing`, the Step 1 listing of the key file, holds exactly the one primary key Step 1 checked), `svn_command_sequence` and `keyserver_upload_reminder`. The sequence is `svn checkout --depth immediates` / `svn commit` for `dist.apache.org` (`atr_offer` under `release_dist_backend = atr`), a git clone, branch, commit, push and `gh pr create --web` for `github.com` (`…/blob/<branch>/<path>`, also `raw/` and `raw.githubusercontent.com`: the branch is the first segment and the path the rest, so `KEYS` may sit in a sub-directory, with a warning when it does; `keys_file_branch` (preflight `values` or config) names a branch holding `/`, which the URL must start with or the render refuses naming both; a file not named `KEYS` is refused), generic instructions otherwise. The reminder is `https://<keyserver>/upload` plus the Step 1 expiry advisory. Every UID, fingerprint and URL is quoted. |

Refused (exit `2`): a Step 1 that did not proceed; a `dist/dev` KEYS URL; a fetched file holding private-key material or not exactly one public block; a key with no UID.

## Tests

```bash
uv run --project tools/release-management pytest
```

The scripted cases of the retired model-graded `release-rc-cut`, `release-verify-rc`, `release-vote-draft`, `release-vote-tally`, `release-promote`, `release-announce-draft`, `release-prepare`, `release-archive-sweep`, `release-audit-report` and `release-keys-sync` suites live in `tests/test_rc_cut.py`, `tests/test_verify_rc.py`, `tests/test_vote_draft.py`, `tests/test_vote_tally.py`, `tests/test_promote.py`, `tests/test_announce_draft.py`, `tests/test_prepare.py`, `tests/test_archive_sweep.py`, `tests/test_audit_report.py` and `tests/test_keys_sync.py`, named after each former case;
`tests/test_prepare_scripts.py` and `tests/test_audit_record.py` hold the moved `release-prepare` script and `render_record.py` tests.
`tests/test_integration.py` renders each skill from what `release-config load` really prints.
