<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [TODO: `<Project Name>` — remediation PR workflow specifics](#todo-project-name--remediation-pr-workflow-specifics)
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

# TODO: `<Project Name>` — remediation PR workflow specifics

Project-specific mechanics of how the `security-issue-fix` skill
opens a public fix PR on the project's `<upstream>` repository. Only
the bits that are **specific to this project** live here; the
generic flow (clone → branch → commit → push → `gh pr create --web`)
is described in the
[`security-issue-fix`](../../skills/security-issue-fix/SKILL.md)
skill itself.

## Upstream repository

| Key | Value |
|---|---|
| Upstream repo | TODO |
| Upstream URL | TODO |
| Upstream `AGENTS.md` | TODO |
| Contributing docs root | TODO |
| Gen-AI disclosure reference | TODO: URL + anchor in the project's contributing docs |
| Public security policy | TODO |

The authoritative configuration for the upstream repository is in
[`project.md`](project.md); this file reiterates the same values for
convenience.

## Toolchain

TODO: list the project's developer toolchain. Example shape:

- TODO: language + version, e.g. `Python 3.11+`.
- TODO: package manager, e.g. `uv`, `cargo`, `mvn`.
- TODO: any project-specific dev shell or test harness.

The `security-issue-fix` skill assumes a clean clone of `<upstream>`
reachable from the agent's working directory (path from
`.apache-magpie-overrides/user.md → environment.upstream_clone`), with a remote named
for the user's GitHub fork that `gh pr create` can push to.

## Backport labels

TODO: list the project's `backport-to-<branch>` labels and the
default policy. Most projects need only one or two.

## Commit trailer

TODO: the project's convention for AI-assisted commits. Example:

> Never use `Co-Authored-By:` with an AI agent as co-author. Use a
> `Generated-by:` trailer instead.

And the concrete trailer text for this project:

```text
Generated-by: TODO: model + URL to the project's Gen-AI disclosure anchor
```

## PR title / body scrubbing

Every public surface (commit message, branch name, PR title, PR
body, newsfragment) must be grep-checked for leakage of:

- `CVE-` (the CVE ID),
- TODO: the tracker repo slug of this project,
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
[`../../README.md`](../../README.md). TODO: note any
project-specific deviation from the generic process.
