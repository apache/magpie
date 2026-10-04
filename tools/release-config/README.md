<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [`release-config`](#release-config)
  - [Prerequisites](#prerequisites)
  - [How to use](#how-to-use)
    - [`preflight` — a skill's deterministic Step 0 checks](#preflight--a-skills-deterministic-step-0-checks)
    - [`load` — the parsed config and a skill's Step 1 metadata](#load--the-parsed-config-and-a-skills-step-1-metadata)
  - [What it reads](#what-it-reads)
  - [Shared rules](#shared-rules)
  - [Per-skill rules](#per-skill-rules)
  - [Wiring](#wiring)
  - [Tests](#tests)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

# `release-config`

**Capability:** substrate:release

**Harness:** agnostic

Loads the release-management configuration an adopter keeps in `<project-config>` and runs the **deterministic** part of each `release-*` skill's `Step 0 — Pre-flight check`, printing JSON.
Required keys, argument formats, the digest-set rule, the source-archive review gate, signing-mode consistency, the vote-window floor, the promote-wait hour, the approver-roster lookup and the dist-URL rendering are all fixed rules; running them as code keeps them out of the model's context and makes them give the same answer every time.
Checks that need GitHub, the network or judgement — finding the planning issue, reading its labels, whether the RC tag exists, whether the staging URL answers, what the `KEYS` file holds — stay in the skill.

## Prerequisites

- **Runtime:** Python 3.11+, stdlib only; run via `uv run --project <framework>/tools/release-config`.
- **CLIs:** None beyond the runtime.
- **Credentials / auth:** None. It reads the RM's `user.md` only for `apache_id` and `release_manager.gpg_fingerprint`.
- **Network:** None — reads local markdown files only.

## How to use

Run it from the adopter repo root (or pass `--project-root`).
`<project-config>` resolves per file, local first: `.apache-magpie-local/<file>`, then `.apache-magpie-overrides/<file>`; `--config-dir <dir>` reads every file from one directory instead.
The skill's positional arguments and flags are passed through as the RM typed them; facts the skill read from the planning issue are passed as flags (`--promote-timestamp`, `--download-page`, `--vote-opened`, `--verify-binary`).
The command always exits `0` once it has printed JSON; `2` is a usage error.

### `preflight` — a skill's deterministic Step 0 checks

```bash
uv run --project <framework>/tools/release-config release-config preflight --skill rc-cut 2.12.0 rc1
```

```json
{
  "ok": false,
  "skill": "rc-cut",
  "blockers": ["export_ignore_reviewed is unset in release-build.md § Source archive (archive_reviewed: false): run `release-prepare prep 2.12.0` — …"],
  "warnings": [],
  "values": {"version": "2.12.0", "rc_number": "rc1", "archive_reviewed": false, "signing_mode": "rm-key", "staging_url": "…", "rc_tag": "2.12.0-rc1"}
}
```

`blockers` are hard stops, worded for the RM; `warnings` are surfaced and do not stop the skill; `values` carry what the skill's Step 0 JSON reports (`archive_reviewed`, `non_asf`, `dist_backend`, `rm_is_pmc`, `staging_url`, `promote_clear_after_utc`, …), plus `convenience_versions` (each convenience artefact's `version`, `version_scheme` and `valid` / `invalid` / `unvalidated`) for the skills that handle artefacts.

### `load` — the parsed config and a skill's Step 1 metadata

```bash
uv run --project <framework>/tools/release-config release-config load --skill promote 2.11.0-rc1 \
  --verify-binary apache-foo-2.11.0-bin.tar.gz=identical
```

Prints `sources` (which file each config came from), `config` (the `release-management-config.md` keys with defaults applied), `build` (`release-build.md`: build command, expected artefacts, digest set, source-archive and reproducibility keys, convenience artefacts), `derived` (`signing_mode`, `is_asf`, `non_asf`, `automated_signing_offered` and the file that decided it, `approver_roster_path`, `release_lines`) and, with `--skill`, `metadata` — the config-derived fields of that skill's Step 1 table under the names the table uses.
For `promote`, `metadata.convenience` splits the convenience artefacts into `publish` (verify-rc reported `identical` or `warn`) and `held` (`differs`, or no result).

## What it reads

| File | Parsed as |
|---|---|
| `release-management-config.md` | every `` | `key` | value | `` row; `*(…)*` notes mean unset; two or more backticked values make a list |
| `release-build.md` | the same tables, plus § Build invocation (first unquoted fence), § Expected artefact list and § Digest set (first prose or bullet block; a `TODO:` block is unset), § Convenience artefacts (the unquoted `yaml` fence, including each entry's optional `version` and `version_scheme`; the template's `<project>` example entry is ignored) |
| `release-trains.md` | the bullets of § Release branches currently in flight |
| `pmc-roster.md` / `release_approver_roster_path` | the first table with an Apache ID, email or handle column; `TODO` rows do not count |
| `project.md` | `organization` (default `independent`); a `release_process.automated_signing` YAML key, if the project overrides its organization |
| `organizations/<org>/organization.md` | `release_process.automated_signing` — the framework's in-tree manifest, then the adopter-local `<project-config>/organizations/<org>/organization.md` |
| `user.md` | `apache_id`, `release_manager.gpg_fingerprint` |

Blockquoted examples and `Template guidance` / `Example shape` lead-ins are never read as values.

## Shared rules

Rules more than one skill applies have one implementation, so every skill gives the same answer:

- **Source version and RC.** The source release candidate every skill takes (`<version>` plus `rcN`, tagged `<version>-rcN`): `<version>` is a dotted version of two or more numeric parts with no `.postN` (`2.11`, `2.11.0`, `2.11.0.1`); the RC is `rcN` with N ≥ 1 (`rc0` and `rc01` block).
  `rc-cut`, `verify-rc`, `vote-draft`, `vote-tally` and `promote` check the RC; `announce-draft`, `audit-report` and `prepare` check the version alone.
- **Convenience-artefact versions.** Each § Convenience artefacts entry may carry its own `version` (default the release version; `<version>` in it is rendered, e.g. `<version>.post1`), validated by the entry's optional `version_scheme`: a wheel `2.10.5.post1` passes against source release `2.10.5`.
  `promote` renders the artefact's name and `publish_command` with that version.
  `versions.SCHEMES` is the registry of validated schemes: `python` (a dotted version with an optional `.postN`, RC `rcN` with N ≥ 1).
  An invalid version under a validated scheme is a blocker; any other scheme name is accepted and reported as `unvalidated` with a warning, so the RM decides; an absent field is `unvalidated` with a warning suggesting the field.
  Add a scheme by adding a `Scheme` to `SCHEMES`.
  `rc-cut`, `verify-rc` and `promote` run the check.
- **Approver roster.** One key, `release_approver_roster_path`, default `<project-config>/pmc-roster.md`, read by `promote`, `vote-tally` and `audit-report`.
  `vote-tally` and `audit-report` block when it is unreadable or has no rows; `promote` treats an unreadable roster as a hand-off.
- **`keyserver`.** Defaults to `keys.openpgp.org` everywhere; no skill requires it.
- **ASF identity and `non_asf`.** `project.md` → `organization: ASF` is the only ASF test; `non_asf` is its negation in every skill (there is no `--non-asf` flag and no `is_asf_tlp` key).
  An ASF project must use `release_approval_mechanism: dev-list-vote` and `release_announce_backend: announce-list`; a non-ASF project may not use `announce-list`.
- **Automated signing.** Offered only when the organization manifest key `release_process.automated_signing` resolves to a value: `project.md` → `organizations/<org>/organization.md` (in-tree, then adopter-local) → framework default (not offered).
  `prepare automated-signing` blocks otherwise, and `signing_mode` is `ci-automated` only for `automated_release_signing: enabled` where it is offered.
- **Archive destination.** `archive_url_template`, defaulting to `https://archive.apache.org/dist/<project>/` (from `project_dist_name`) for both ASF backends, `svnpubsub` and `atr`; other backends need `archive_url_template`.

## Per-skill rules

| Skill | Deterministic checks |
|---|---|
| `rc-cut` | source `<version>` and `rcN`; `release-build.md` declares a build command and non-empty expected artefacts and digest set; `release_dist_backend`, `release_dist_url_template` present; digest set has `sha512`, no `md5` / `sha1`; `export_ignore_reviewed` set unless `source_archive_method: custom` or `--allow-unreviewed-archive`; with `signing_mode: ci-automated`, `reproducibility_source: on` and every convenience binary `byte-identical`; convenience-artefact versions |
| `vote-draft` | source `<version>-rcN`; `vote_window_hours`, `vote_dev_list` present; window ≥ 72 unless `--expedited` |
| `vote-tally` | source `<version>-rcN`; `release_approval_mechanism`, `result_subject_template` present; ASF pinned to `dev-list-vote`; the approver roster has a row; window (`vote_window_hours`, or `approval_window_hours` for other mechanisms) elapsed since `--vote-opened` unless `--force-close` |
| `announce-draft` | source `<version>`; `announce_list`, `announce_subject_template` present; `announce-list` if and only if ASF; promote timestamp given; one hour since it unless `--skip-promote-wait`; a Download Page URL (`--download-page` or `download_page_url`) |
| `promote` | source `<version>-rcN`; `release_dist_backend`, `release_dist_url_template` present; for an ASF project the RM on the approver roster (not on it → `rm_is_pmc: false`, a hand-off, not a blocker); reports whether the trusted-hardware attestation is required; convenience-artefact versions |
| `verify-rc` | source `<version>-rcN`; `keys_file_url`, `release_dist_url_template`, `version_manifest_files` present; the four `release-build.md` sections exist; the staging URL renders well-formed; reports `keyserver`; convenience-artefact versions |
| `archive-sweep` | `archive_retention_rule`, `release_dist_backend`, `release_dist_url_template` present; `release-trains.md` lists a release line; backend is a known one; archive destination derivable |
| `audit-report` | source `<version>`; `audit_log_path` present; the approver roster has a row |
| `keys-sync` | fingerprint from `--fingerprint`, then `rm_key_fingerprint`, then `user.md`; `keys_file_url` from `--keys-url` or config; `keyserver` from `--keyserver` or config |
| `prepare` | sub-command parsed; `automated-signing` only where the organization offers it; source `<version>`; `release_branch_base`, `version_manifest_files` present; `release-trains.md` readable |

## Wiring

Every `release-*` skill's `Step 0 — Pre-flight check` runs `release-config preflight --skill <name> …`; `rc-cut`, `vote-draft`, `announce-draft` and `promote` read their Step 1 config fields from `release-config load --skill <name> …`.
The workspace hooks (`ruff`, `mypy`, `pytest`) pick the project up from the root `pyproject.toml` `[tool.uv.workspace] members` list.

## Tests

```bash
uv run --project tools/release-config python -m pytest
```

Every skill has a passing configuration and one case per blocker, and every shared rule has cases across the skills that apply it; `load` is covered for the layered file lookup, defaults, URL rendering, the convenience-artefact split, and the shipped templates parsing as unset rather than as values.
