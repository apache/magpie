<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Source release contents](#source-release-contents)
  - [Files kept in the source archive](#files-kept-in-the-source-archive)
  - [Files deliberately excluded](#files-deliberately-excluded)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

# Source release contents

The signed source artefact — `apache-magpie-<version>-source.zip`, the
file the `[VOTE]` thread votes on — is produced with `git archive`,
which honours the `export-ignore` attributes declared in
[`.gitattributes`](../.gitattributes). Alongside the framework source
(`skills/`, `tools/`, `docs/`, `projects/`, the Python packaging, and
`LICENSE`/`NOTICE`) the archive deliberately keeps a small set of
repository-root metadata and configuration files.

Those files are **part of the development and release environment**, not
stray artefacts: a from-source checkout of Magpie needs them to build the
project, run its licence audit, and drive the framework's own skills. To a
reviewer scanning the archive they can look like "developer-only" noise,
so this note records what each one is and why it ships. It follows the
review discussion on the `0.1.0-rc2` `[VOTE]` thread on
`dev@magpie.apache.org`.

`release-verify-rc` re-checks the unpacked archive (symlink-lint,
validators, no `.pyc`), so a regression in what ships fails the RC before
the vote.

## Files kept in the source archive

| Path | Why it ships |
|---|---|
| `.rat-excludes` | Input to Apache RAT, passed via `--input-exclude-file` in `.github/workflows/rat.yml`. Declares the paths that legitimately carry no Apache licence header (lock files, generated markers, licence-detection test fixtures). Anyone re-running the licence audit on the source tree — including `release-verify-rc` — needs it. |
| `.asf.yaml` | ASF self-service repository configuration consumed by ASF infrastructure (GitHub settings, notifications, branch protections). Standard ASF project metadata. |
| `doap_Magpie.rdf` | The project's DOAP ("Description Of A Project") RDF descriptor — the machine-readable project record that `projects.apache.org` and ASF tooling consume. Standard ASF project metadata. |
| `.apache-magpie.lock` | The committed self-adoption pin (Magpie adopts itself: `method: local`, `source: skills/`). Part of the framework's own adoption wiring, read by `/magpie-setup`. |
| `.claude/settings.json` | Agent development-environment configuration for working on the framework from source. Part of the dev environment rather than a personal preference; more agent configs may be added over time. |
| `.github/ISSUE_TEMPLATE/`, `.github/PULL_REQUEST_TEMPLATE.md` | Not just GitHub chrome — these are referenced by shipped GitHub-vendor skills (PR / issue triage tooling) and cross-checked by validation hooks that verify inter-file links resolve. Stripping them would break those skills and fail the validators. (The genuinely CI/bot-only parts of `.github/` are excluded — see below.) |
| `.gitignore` files — the repository root one plus the nested ones (`projects/_template/.gitignore`, `tools/*/.gitignore`, `.apache-magpie-overrides/.gitignore`) | Development-environment configuration. The repository-root `.gitignore` keeps a from-source dev checkout of the framework clean; `projects/_template/.gitignore` is example content shipped for adopters to copy; the `tools/*` ones keep a from-source dev checkout of each tool package clean. |
| `.agents/skills/*` (symlinks) | The canonical agent skill view — single-hop symlinks that resolve straight to the real `skills/*` directories — kept so the shipped agent view resolves out of the box. The relay chains other agent dirs use (`.claude/skills/`, `.github/skills/`, `.kiro/skills/`) are excluded because they chain symlink → symlink, which a safe archive extractor rejects. |

## Files deliberately excluded

The following are stripped from the archive via `export-ignore` in
[`.gitattributes`](../.gitattributes) — VCS / CI / editor metadata that a
source consumer never needs:

- **Repository-root VCS / dev metadata:** `.gitattributes`,
  `.pre-commit-config.yaml`, the linter configs (`.lychee.toml`,
  `.markdownlint.json`, `.typos.toml`, `.zizmor.yml`), and
  `.apache-magpie.session-state.json`. (The repository-root `.gitignore`
  is **not** excluded — it ships as dev-environment config, above.)
- **Editor metadata:** `.idea/`.
- **CI / bot config:** `.github/workflows/`, `.github/dependabot.yml`.
- **Relay symlink dirs:** `.claude/skills/`, `.github/skills/`,
  `.kiro/skills/` (the symlink-chaining views described above).

[`.gitattributes`](../.gitattributes) is the authoritative list and
carries the per-entry rationale.
