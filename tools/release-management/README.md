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
for `release-verify-rc` it also classifies the output of each check the voter ran.
The agent presents the output and keeps only the judgement; the release manager runs every command on their own machine.

**It runs nothing.**
No command here invokes `git`, `gpg`, `svn`, `gh`, `aws` or `atr`, reads a key, sends mail or touches the network.
A render that would emit something a skill must refuse (a `dist/release/` staging target, an MD5 or SHA-1 digest)
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

## Tests

```bash
uv run --project tools/release-management pytest
```

The scripted cases of the retired model-graded `release-rc-cut` suites live in `tests/test_rc_cut.py`, and those of `release-verify-rc` in `tests/test_verify_rc.py`, named after each former case.
