<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Install & first runs](#install--first-runs)
  - [Before the first run](#before-the-first-run)
  - [Works well with](#works-well-with)
  - [Try these first](#try-these-first)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Install & first runs

Install just this family — one plugin, 8 skills. Audits and fixes for repository maintenance findings.

Once you have [added the marketplace](../setup/marketplace-install.md):

```text
/plugin install magpie-repo-health@apache-magpie
```

New to Magpie? The [quick start](../quick-start.md) walks the whole path in
one place — install, the first `/magpie-setup:setup` run, and a recording of it
happening — plus the other agents and the secure-isolation setup to run next.

The first repo-health skill you run opens with a one-minute
[welcome guide](../../plugins/magpie-setup/skills/setup/setup_preflight/guides/repo-health.md):
the typical flow, what needs configuring, what to ask it, and how to make it yours.
Dismiss it, or hide it for good, from its last line;
*"show the repo-health welcome again"* or `/magpie-setup:welcome-guide repo-health` brings it back.

## Before the first run

<!-- BEGIN generated: skill-config (tools/dev/check-skill-config.py --fix) -->

![An animated `/magpie-setup:setup config` run for the repo-health family: the check failing, the values derived from the repository, one question for the rest, and personal files written](../../assets/quickstart/wizard/repo-health.svg)

*Illustrative — the real run derives more and asks better. What is true is
the shape: it runs itself, it writes only your personal layer, and it
stages nothing.*

Every skill here resolves project-specific values from the adopter's
[`<project-config>/`](../../plugins/magpie-setup/templates/) directory — which is
your personal layer first — `.apache-magpie-local/` (gitignored) in a
project that adopted Magpie, `<git-common-dir>/apache-magpie/` in one
that did not — then `.apache-magpie-overrides/` (committed, the project's).

**For yourself:** `/magpie-setup:setup config` scaffolds and fills these locally
(`/magpie-setup config` on a [pinned-snapshot install](../setup/marketplace.md#skill-names-differ-by-install-method)).
Nothing is staged, nothing is committed, and it works on a repository that
has never adopted Magpie.

**For the project:** [`/magpie-setup:setup adopt`](../setup/team-adoption.md)
commits them for every contributor, either scaffolded directly or promoted
from what you configured locally.

**Required.** Without these a skill would act on a guess, so it stops and
says which file is missing.

| File | What it carries | Read by |
|---|---|---|
| [`fix-workflow.md`](../../plugins/magpie-setup/templates/fix-workflow.md) | Fork / clone / toolchain specifics, backport-label policy, commit-trailer wording, PR scrubbing, private-PR fallback. | `audit-finding-fix` |
| [`repo-health-config.md`](../../plugins/magpie-setup/templates/repo-health-config.md) | Per-skill switches: deprecated runner labels, zizmor rule classes, dependency managers, SPDX expression, flaky-test thresholds. | `dependency-vulnerability-audit`, `flaky-test-triage`, `license-compliance-audit`, `workflow-security-audit` |
| [`runtime-invocation.md`](../../plugins/magpie-setup/templates/runtime-invocation.md) | Build prerequisite, run-a-single-file recipe, stream-capture conventions, network/dependency handling. | `audit-finding-fix` |

**Optional.** Each has a documented fallback; absent, the skill still runs.

| File | What it carries | Read by |
|---|---|---|
| [`project.md`](../../plugins/magpie-setup/templates/project.md) | Project manifest. Identity, repositories, mailing lists, tools enabled, CVE tooling, GitHub project-board + issue-template field declarations. The single file every skill reads to resolve project-scoped references. | `dependency-license-audit`, `workflow-optimization` |

<!-- END generated: skill-config -->

<!-- BEGIN generated: companion-skills (tools/dev/check-companion-skills.py --fix) -->

## Works well with

Third-party packages, none of them required: this family works with none of
them installed, and Magpie neither bundles nor depends on any. They are named
because they are what a maintainer goes looking for next, and because the
answer differs by agent.

**[Aikido Security](https://www.aikido.dev/)** — Aikido

SAST, secrets and infrastructure-as-code scanning surfaced in the session.

*With this family:* Covers the infrastructure-as-code surface that workflow-security-audit does not read.

Available on **Claude Code** only.

**[Claude Security](https://code.claude.com/docs/en/claude-security)** — Anthropic

A multi-agent vulnerability scan of your own repository, run inside the session; each finding carries a severity, a CWE category and reproduction steps, and the ones you pick become patch files you review before applying.

*With this family:* The audits here read dependencies, workflows and licences. This reads the project's own code, which none of them do.

Available on **Claude Code** only.

Claude Code only: it drives subagents and a scan workflow that Agent Plugins 1.0 has no component for. Listed with its harness named rather than presented as the answer for everyone.

Install commands per agent are in
[**Companion skill packages**](../setup/companion-skills.md).

<!-- END generated: companion-skills -->

## Try these first

*Illustrative shapes, not real transcripts — your output will differ. Nothing
below sends, merges, or posts anything without you confirming it.*

**Audit dependencies for CVEs.**

```text
/magpie-repo-health:dependency-vulnerability-audit
```

![A dependency vulnerability audit run grouping findings into outdated-with-a-fix, unmaintained, and pinned-but-unused, having upgraded nothing](../../assets/quickstart/families/repo-health/dependency-vulnerability-audit.svg)

**Audit the Actions workflows.**

```text
/magpie-repo-health:workflow-security-audit
```

![A workflow-security-audit run: one failure where a workflow runs untrusted code with write permissions, two warnings about pinning and permissions, and nine clean files](../../assets/quickstart/families/repo-health/workflow-security-audit.svg)

**Find the flaky tests.**

```text
/magpie-repo-health:flaky-test-triage
```

![A flaky-test-triage run separating two genuine flakes from a real regression that had been hiding among them](../../assets/quickstart/families/repo-health/flaky-test-triage.svg)
