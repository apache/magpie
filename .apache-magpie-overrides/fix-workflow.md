<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Apache Magpie — remediation PR workflow specifics](#apache-magpie--remediation-pr-workflow-specifics)
  - [Upstream repository](#upstream-repository)
  - [Toolchain](#toolchain)
  - [Backport labels](#backport-labels)
  - [Commit trailer](#commit-trailer)
  - [PR title / body scrubbing](#pr-title--body-scrubbing)
  - [PR creation convention](#pr-creation-convention)
  - [Private-PR fallback](#private-pr-fallback)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Apache Magpie — remediation PR workflow specifics

Project-specific mechanics of how the `security-issue-fix` skill
opens a public fix PR on the project's `<upstream>` repository. Only
the bits that are **specific to this project** live here; the
generic flow (clone → branch → commit → push → `gh pr create --web`)
is described in the
[`security-issue-fix`](../skills/security-issue-fix/SKILL.md)
skill itself.

## Upstream repository

| Key | Value |
|---|---|
| Upstream repo | `apache/magpie` |
| Upstream URL | https://github.com/apache/magpie |
| Upstream `AGENTS.md` | https://github.com/apache/magpie/blob/main/AGENTS.md |
| Contributing docs root | https://github.com/apache/magpie/blob/main/CONTRIBUTING.md |
| Gen-AI disclosure reference | https://github.com/apache/magpie/blob/main/CONTRIBUTING.md#authoring-with-an-agent |
| Public security policy | https://github.com/apache/magpie/security/policy |

The authoritative configuration for the upstream repository is in
[`project.md`](project.md); this file reiterates the same values for
convenience.

## Toolchain

Developer toolchain:

- Python 3.11+ (per `pyproject.toml` `requires-python`), plus Groovy and shell scripts under `tools/`.
- `uv` (each `tools/<name>/` is its own uv project).
- `prek` pre-commit hooks (`prek install`, `prek run --all-files`); skill evals under `tools/skill-evals/`.

The `security-issue-fix` skill assumes a clean clone of `<upstream>`
reachable from the agent's working directory (path from
`.apache-magpie-overrides/user.md → environment.upstream_clone`), with a remote named
for the user's GitHub fork that `gh pr create` can push to.

## Backport labels

None. Apache Magpie releases only from `main`; there are no maintenance
branches and no `backport-to-*` labels. Fix PRs target `main` only.

## Commit trailer

Which trailer an AI-assisted commit carries is set in
[`commit-attribution.toml`](commit-attribution.toml) — `generated-by`,
`assisted-by`, `co-authored-by`, `none`, `custom`, or `contributor-choice`
— and resolved per
[`docs/setup/commit-attribution.md`](../docs/setup/commit-attribution.md).
`setup adopt` asks for it.

Apache Magpie uses `generated-by` (`.apache-magpie-overrides/commit-attribution.toml`):
`Generated-by: <agent name and version>`, added with `git commit --trailer`.
Nothing is added beyond the default wording. `Co-Authored-By:` naming an AI
agent is never used.

## PR title / body scrubbing

Every public surface (commit message, branch name, PR title, PR
body, newsfragment) must be grep-checked for leakage of:

- `CVE-` (the CVE ID),
- the tracker repo slug — none today: Apache Magpie has no private
  security tracker; add its slug here if one is created,
- `vulnerability`, `security fix`.

A leaked CVE or tracker-repo reference in a public PR breaks the
disclosure coordination; the skill refuses to push if the scrubbing
grep fails.

## PR creation convention

Always open PRs with `gh pr create --web` so the human reviewer can
check the title, body, and the Gen-AI disclosure in the browser
before submission. Pre-fill `--title` and `--body` (including the
Gen-AI disclosure block) so the reviewer only needs to review, not
edit.

## Private-PR fallback

The exceptional private-PR path (target branch `main` of the
tracker repo; CI does not run; static checks and tests run manually
by the PR author) is described in Step 9 of
[`README.md`](../README.md). No
project-specific deviation: Apache Magpie follows the generic process.
