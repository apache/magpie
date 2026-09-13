<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Quick start](#quick-start)
  - [Installation or Adoption?](#installation-or-adoption)
  - [The walkthrough](#the-walkthrough)
    - [Step 1 — install from the Apache Magpie Marketplace](#step-1--install-from-the-apache-magpie-marketplace)
    - [Step 2 — run `/magpie-setup`](#step-2--run-magpie-setup)
    - [Step 3 — lock the agent down](#step-3--lock-the-agent-down)
    - [Step 4 — use it](#step-4--use-it)
    - [Step 5 — consider adopting Magpie](#step-5--consider-adopting-magpie)
  - [What each family solves](#what-each-family-solves)
  - [Other installation methods](#other-installation-methods)
  - [Cross-references](#cross-references)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

# Quick start

Install Apache Magpie into the agent you already use, in a couple of
commands: one to add the **Apache Magpie Marketplace**, one per family you
want. Nothing is
committed to your repository, and nothing is changed in it.

**This install is yours, on this machine.** It needs no decision from your
project and no opt-in from your teammates. Committing anything for other
people is a separate act called **adoption** —
[Installation or Adoption?](quick-start/two-ways.md) draws the line.

**What you get.** 74 skills your agent can run, grouped into 10 **families** —
PR triage and review, issue triage, security-report handling, release
management, contributor mentoring. Install only the families you need; each one
you add costs context in every session —
[what each family solves](quick-start/families.md) lists all ten, after the
install steps.

---

## Installation or Adoption?

**Installing** puts the marketplace and the plugins into your agent and writes
nothing to any repository. That is what the steps below do, and it is all most
people ever need. **Adoption** is the separate, later act of a repo's
maintainers committing a floor that everyone who clones it picks up.

The two differ in one thing only — whether anything is committed for other
people — and you do not have to choose before installing.
[**Installation or Adoption?**](quick-start/two-ways.md) compares them side by side.

---

## The walkthrough

Five steps, in order. One and two are the install; the rest are what you do
with it.

### Step 1 — install from the Apache Magpie Marketplace

Pick your agent. Every path uses the
[`apache/magpie`](https://github.com/apache/magpie) repository directly as
the marketplace; no vendor directory or account is involved.

**Claude Code**

Add the marketplace, then install **one plugin per family you actually want**:

```text
/plugin marketplace add apache/magpie
/plugin install magpie-setup@apache-magpie
/plugin install magpie-pr-management@apache-magpie
```

`magpie-setup` is the one to always take — it carries the secure-isolation
skills from [Step 3](#step-3--lock-the-agent-down).
Add the rest to match a problem you have today; you can install more at any
time.

Pick your families from
[What each family solves](quick-start/families.md) below — the ten of them,
with the problem each one solves.

Each family's README opens with an **Install & first runs** section — the one
command for that family and a few things to try once it is in:
[setup](setup/README.md#install--first-runs) ·
[security](security/README.md#install--first-runs) ·
[release-management](release-management/README.md#install--first-runs) ·
[pr-management](pr-management/README.md#install--first-runs) ·
[issue](issue-management/README.md#install--first-runs) ·
[repo-health](repo-health/README.md#install--first-runs) ·
[contributor-growth](contributor-growth/README.md#install--first-runs) ·
[utilities](utilities/README.md#install--first-runs) ·
[mentoring](mentoring/README.md#install--first-runs) ·
[pairing](pairing/README.md#install--first-runs)

**Optional: adopt Magpie for your teammates.**

Everything above installs Magpie for **you, on this machine** — nothing is
written to the repository, and your teammates are unaffected.

A project can go one step further and commit a small block to its
`.claude/settings.json` naming the marketplace and three plugins, so anyone who
clones the repo and trusts it arrives with `magpie-setup`, `magpie-utilities`
and `magpie-agent-guard` already enabled. Committing that block is **adoption**:
[`/magpie-setup adopt`](setup/team-adoption.md) writes it, alongside the
committed floor and the repo's shared overrides — see
[the default set](setup/marketplace.md#claude-code-the-default-set).

**This is entirely optional.** The plugins work in the repo whether or not the
block is committed, and a project that never commits it is not missing
anything: the install you just did is complete. It is a convenience for
teams — nobody has to run the install by hand — not a requirement.

**OpenAI Codex CLI**

```bash
codex plugin marketplace add apache/magpie
codex plugin install magpie
```

**VS Code / GitHub Copilot**

Point VS Code's plugin install at the repository URL — it clones the repo
and loads Magpie as an [Agent Plugins 1.0](https://agent-plugins.org/specification)
package:

```text
https://github.com/apache/magpie
```

This path is not yet live-installed against a running VS Code — see
[Verification status](setup/marketplace.md#verification-status).

**Google Gemini CLI**

```bash
gemini extensions install https://github.com/apache/magpie
```

This path is not yet live-installed either — see
[Verification status](setup/marketplace.md#verification-status).

> [!IMPORTANT]
> **There is no install-everything plugin, by design.** Every installed skill
> advertises itself to the model on every turn, used or not — all ten families
> at once would be ~8.6k always-on tokens against 0.2–2.0k for a family you
> picked on purpose. Install `magpie-setup` plus the families you actually
> want; adding another later is one more install. See
> [Choosing a plugin](setup/marketplace.md#choosing-a-plugin-which-families).

> [!TIP]
> **Working in IntelliJ IDEA, PyCharm or another JetBrains IDE?** There is
> nothing extra to install. A JetBrains IDE hosts an agent rather than
> distributing skills itself, so you run the install above for the agent you
> use inside it — with Claude Code's JetBrains plugin, the same
> `/plugin marketplace add apache/magpie` from the IDE's Claude Code window.
> And you only do it once: plugin state lives in a single user-scope store, so
> a marketplace added in the terminal is already there in the IDE. Details, and
> why JetBrains' own agent Junie is a separate matter, in
> [the Apache Magpie Marketplace](setup/marketplace.md#jetbrains-ides-intellij-idea-pycharm-goland-).

> [!NOTE]
> **Per-family works on every agent above.** A family plugin carries its skills
> as real directories, so nothing depends on a client following a symlink —
> measured on Codex and Gemini, not assumed. Cursor, Kiro, OpenCode, and
> `microsoft/apm` are covered in
> [the Apache Magpie Marketplace](setup/marketplace.md#choosing-a-plugin-which-families).

---

### Step 2 — run `/magpie-setup`

The marketplace install above is complete on its own: the skills are in your
agent and you can start using them. `/magpie-setup` is what you run next when
you want Magpie wired into a **project** rather than only into your own agent —
a committed floor, project config, or overrides. Committing those for everyone
who clones the repo is **adoption** —
[`setup/team-adoption.md`](setup/team-adoption.md).

One command. It works out which method fits this checkout, prints the plan it
intends to carry out, and waits:

```text
/magpie-setup
```

![A `/magpie-setup` run in Claude Code: the marketplace install, then the skill detecting the checkout, printing the method and plan it intends to carry out, and waiting for approval before writing anything](../assets/quickstart/magpie-setup.svg)

Nothing is written before you approve it. Afterwards, `/magpie-setup verify`
re-runs the health check and drift detection, and `/magpie-setup:status`
prints what is currently installed.

Not sure you need this step? [Installation or Adoption?](quick-start/two-ways.md)
draws the line.

**Every skill configures itself on first use.** You do not have to remember
which projects are set up, or run anything to prepare a family before you use
it: 65 of the 74 skills open with a silent pre-flight — the nine exceptions are
the setup skills themselves, which are what you run to fix whatever it finds.

The first time you call a skill in a project, that pre-flight works out how
Magpie is installed here and whether this project is adopted. If anything is
unresolved it **stops and proposes `/magpie-setup`** rather than guessing:

- a pinned-snapshot project whose snapshot was never fetched on this machine,
  or that is on a different framework version than the project pins;
- a marketplace install in a project with no `<project-config>/` directory,
  where every `<placeholder>` in the skill is unresolved.

The alternative to stopping is a skill that runs against the wrong tracker, so
it stops. Once the project is set up the check costs three file checks and
prints nothing, on every invocation thereafter.

Each family's README opens with a recording of exactly this — its own first
run, pre-flight and all. [What each family solves](quick-start/families.md)
links to all ten.

---

### Step 3 — lock the agent down

Part of setting up, not an afterthought. Magpie's skills read issues,
pre-disclosure security reports, and private mailing lists, so the isolation
and privacy layers belong in place before you point a skill at anything real.

The first skill worth running is the one that locks the agent down:

```text
/magpie-setup:isolated-setup-install
```

It walks you through the install interactively and surfaces every sudo,
shell-rc, and settings-file change for approval before applying it. When it
finishes, your agent runs with:

- **A filesystem sandbox** — Bash subprocesses run under Seatbelt (macOS) or
  bubblewrap (Linux) and see only the paths you allow. Your `~/.ssh`,
  `~/.aws`, and tokens are out of reach.
- **A clean environment** — the `claude-iso` wrapper strips host environment
  variables before the agent starts.
- **Visible state** — the status line says whether the sandbox is on, and a
  bold red banner fires before any bypass prompt.

![Sandboxed session: status-line prefix `[sandbox]` rendered green](../assets/session-sandboxed.png)

Green `[sandbox]` in the footer is the steady state. Confirm the whole
install with `/magpie-setup:isolated-setup-verify`, which reports ✓/✗/⚠
for every piece.

→ Full walkthrough: [`setup/secure-agent-setup.md`](setup/secure-agent-setup.md).
Why each layer exists: [`setup/secure-agent-internals.md`](setup/secure-agent-internals.md).
How your data reaches a model, and what never leaves the machine:
[`setup/privacy-llm.md`](setup/privacy-llm.md).

---

### Step 4 — use it

Ask in plain language:

> review PR #5193

> triage the latest security reports

or call a skill by name. A marketplace install namespaces skills under the
**plugin** that provides them, as `/<plugin>:<skill>`:

```text
/magpie-pr-management:triage
/magpie-security:issue-triage
```

`/magpie-utilities:list-skills` prints everything that is installed.

---

### Step 5 — consider adopting Magpie

Everything so far was yours alone: the plugins live in your agent, and your
repository has not changed. **Adoption is the separate act of deciding this for
the project** — and it belongs to the repo's maintainers, together, not to
whoever installed first.

Adopting commits a **floor**: an `.apache-magpie.lock` recording what the
project recommends, and a default plugin set in the repo's
`.claude/settings.json` derived from it. A contributor who clones the repo and
trusts it then arrives with those families already enabled — no install step,
no instructions to follow. It is a floor, never a ceiling: nobody is stopped
from installing more or running a newer Magpie, and a maintainer can reverse
the whole thing in a PR.

Worth doing once the project — not one maintainer — agrees on what it wants to
recommend. It obliges nobody: a contributor who would rather not use Magpie at
all is unaffected.

→ [**Team adoption**](setup/team-adoption.md) is the full walkthrough: what
gets committed, how the floor is chosen, and what a contributor sees on clone.
Still deciding? [**Installation or Adoption?**](quick-start/two-ways.md)
compares the two side by side.

---

## What each family solves

Skills ship in ten **families**, and you are not meant to take all of them.
[**What each family solves**](quick-start/families.md) lists every one with the
problem it solves and what it offers, so you can pick against a problem you
have today.

---

## Other installation methods

The marketplace is not the only route. A project can install the framework as a
**pinned snapshot** committed to the repo — the answer when an agent has no
marketplace at all, when you need the signed ASF source release, or when every
contributor and CI job should sit on one committed version. A clone of the
framework itself takes a third route and **self-adopts**.

→ [**Other installation methods**](quick-start/other-install-methods.md) covers
all three, with the copy-pasteable bootstrap for each. They are complementary, not exclusive:
pin the snapshot for the project and keep the marketplace plugin for yourself
if you prefer.

---

## Cross-references

- [`docs/index.md`](index.md) — what Magpie is and which skill families exist.
- [**The Apache Magpie Marketplace**](setup/marketplace.md) — the full
  reference: every agent that can add it, per-family plugins, versioning.
- [`docs/prerequisites.md`](quick-start/prerequisites.md) — what individual skills need
  (GitHub auth, Gmail MCP, browser).
- [`docs/setup/README.md`](setup/README.md) — the setup skill family.
