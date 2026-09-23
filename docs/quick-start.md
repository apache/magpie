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
    - [Step 3 — isolate & guard](#step-3--isolate--guard)
    - [Step 4 — set up privacy](#step-4--set-up-privacy)
    - [Step 5 — use it](#step-5--use-it)
    - [Step 6 — consider adopting Magpie](#step-6--consider-adopting-magpie)
  - [What each family solves](#what-each-family-solves)
  - [Other installation methods](#other-installation-methods)
  - [Cross-references](#cross-references)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

# Quick start

![The baseline three plugins and one family installed, then a triage run: 38 open PRs, 12 untriaged, with a proposed action for each and a confirmation prompt](../assets/quickstart/install.svg)

*Illustrative. The whole of it: install, run a skill, get an answer you confirm.*

Install Apache Magpie into the agent you already use, in a couple of
commands: one to add the **Apache Magpie Marketplace**, one per family you
want. Nothing is
committed to your repository, and nothing is changed in it.

**This install is yours, on this machine.** It needs no decision from your
project and no opt-in from your teammates. Committing anything for other
people is a separate act called **adoption** —
[Installation or Adoption?](quick-start/two-ways.md) draws the line.

**What you get.** 75 skills your agent can run, grouped into 10 **families** —
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

Six steps, in order. One and two are the install. Three and four are the
safety layers, and **both are strongly recommended** — Magpie's skills read
issues, pre-disclosure security reports and private mailing lists, so neither
is a nice-to-have. Five and six are what you do with it.

### Step 1 — install from the Apache Magpie Marketplace

Installing is a **one-time, per-machine** step for whichever agent you use. It
writes nothing to any repository and your teammates are unaffected.

![Adding the apache-magpie marketplace, then installing the baseline — magpie-setup, magpie-agent-guard, magpie-utilities — and one family, with nothing written to the repository](../assets/quickstart/step-install.svg)

→ [**Prerequisite: install Magpie from your agent's
marketplace**](setup/marketplace-install.md) has the commands, one section per
agent: Claude Code, OpenAI Codex CLI, VS Code / GitHub Copilot, Google Gemini
CLI, Cursor, `microsoft/apm`, and JetBrains IDEs.

**Take the baseline — three plugins, strongly recommended on every machine:**

- **`magpie-setup`** — install this one first; nothing else installs, upgrades,
  configures or adopts without it, and it carries the secure-isolation skills
  from [Step 3](#step-3--isolate--guard).
- **`magpie-agent-guard`** — the deterministic pre-execution guard, a hook that
  inspects each shell command before it runs and denies the dangerous shapes.
- **`magpie-utilities`** — `list-skills` and the small tools you reach for when
  you want to know what is actually installed.

Those three are exactly the **floor** a project commits when it adopts Magpie,
so taking them is taking what a project would recommend to every contributor.

Then add **one plugin per family you actually want**, against a problem you
have today; you can install more at any time. Pick them from
[What each family solves](quick-start/families.md) — the ten families, with the
problem each one solves.

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

**Check what landed** with `/plugin` → *Installed*, filtered to `magpie`:

![The Claude Code /plugin Installed tab filtered to magpie: eleven plugins from the apache-magpie marketplace, each marked enabled, with its skill count and how many times its skills have been used](../assets/installed-plugins.png)

Every row names the marketplace it came from, whether it is enabled, and how
many of its skills you have actually used — which is the honest way to decide
whether a family is earning its always-on context.

> [!IMPORTANT]
> **There is no install-everything plugin, by design.** Every installed skill
> advertises itself to the model on every turn, used or not — all ten families
> at once would be ~8.2k always-on tokens against 0.2–1.9k for a family you
> picked on purpose. See
> [Choosing a plugin](setup/marketplace.md#choosing-a-plugin-which-families).

> [!NOTE]
> **Per-family works on every agent listed.** A family plugin carries its
> skills as real directories, so nothing depends on a client following a
> symlink — measured on Codex and Gemini, not assumed.

> [!TIP]
> **Installed a family and want to use it now?**
> [Your first run with a family](quick-start/first-run.md) walks the whole
> thing in terminal steps — the pre-flight stopping, the setup wizard, the
> configuration it scaffolds, and the same command working on the retry.

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

**Or just ask for it.** Magpie's skills are model-invoked, so the slash form is
a shortcut, never the only way in — every step on this page has a plain-language
equivalent that works on every harness, including the ones with no slash
commands at all:

> set Magpie up for this project

Both reach the same skill. Use whichever you prefer; this page shows the slash
form first because it is unambiguous, and the sentence beside it because that
is what most people actually type.

![A `/magpie-setup` run in Claude Code: the picker with the baseline three already ticked, the plugins installed for the user, then the secure-agent setup proposing its changes and waiting for approval before writing anything](../assets/quickstart/magpie-setup.svg)

Nothing is written before you approve it. Afterwards, `/magpie-setup verify`
(*check that Magpie is set up correctly here*) re-runs the health check and
drift detection, and `/magpie-setup:status` (*what Magpie do I have
installed?*) prints what is currently installed.

Not sure you need this step? [Installation or Adoption?](quick-start/two-ways.md)
draws the line.

**Every skill configures itself on first use.** You do not have to remember
which projects are set up, or run anything to prepare a family before you use
it: 65 of the 75 skills open with a silent pre-flight — the ten exceptions are
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

### Step 3 — isolate & guard

**Strongly recommended, and part of the default setup rather than a later
hardening pass.** Magpie's skills read issues, pre-disclosure security reports
and private mailing lists, so this belongs in place before you point a skill at
anything real.

One run installs two different protections: a **sandbox**, which confines what
a command can reach, and the **action guard**, which decides whether a command
runs at all. A sandbox will not stop a legal `gh pr comment` from pinging four
maintainers who did not ask; a guard will not stop a command from reading
`~/.ssh`.

| Harness | What to run |
|---|---|
| **Claude Code** | `/magpie-setup:isolated-setup-install` — the guided install below. |
| **OpenAI Codex CLI** | [Codex setup lifecycle](adapters/codex.md#setup-isolated-lifecycle). |
| **Google Gemini CLI** | [Gemini setup lifecycle](adapters/gemini.md#setup-isolated-lifecycle). |
| **Anything else** | The [secure setup guide](setup/secure-agent-setup.md) and your runtime's adapter. |

```text
/magpie-setup:isolated-setup-install
```

> isolate my agent with Magpie's secure setup

![The secure-agent setup: three proposed changes, a confirmation, then the sandbox, the clean environment and the status line in place](../assets/quickstart/step-isolation.svg)

It surfaces every sudo, shell-rc and settings-file change for approval before
applying it. When it finishes you have a filesystem and network sandbox, a
clean environment with your credentials stripped, the status line below, and
the guard wired in front of every shell command.

**The footer tells you which posture you are in, on every render:**

![A session where /sandbox reports "Sandbox enabled with auto-allow for bash commands": the terminal footer opens with a yellow `[sandbox-auto]` tag, followed by the project, the branch and the model](../assets/session-sandboxed.png)

| Tag | Means |
|---|---|
| `[sandbox]` green | sandboxed, still prompting per command |
| `[sandbox-auto]` yellow | sandboxed, not prompting — auto-allow |
| `[NO SANDBOX]` bold red | not sandboxed |

![A session after /sandbox reports "Sandbox disabled": the footer opens with a bold-red `[NO SANDBOX]` tag ahead of the project, branch and model](../assets/session-no-sandbox.png)

After the tag comes the project, branch, model, and the branch's PR once it has
one — so several sessions across worktrees stay apart.

Confirm the install with `/magpie-setup:isolated-setup-verify` — *check my
agent isolation* — which reports ✓/✗/⚠ for every piece.

→ **Why each layer exists, and what it does not stop:**
[`setup/secure-agent-internals.md`](setup/secure-agent-internals.md) ·
**full install walkthrough:** [`setup/secure-agent-setup.md`](setup/secure-agent-setup.md) ·
**what the guard denies and why it is a hook rather than a rule:**
[`tools/agent-guard/README.md`](../tools/agent-guard/README.md) ·
**harness coverage:** [adapters matrix](adapters/README.md) — Codex and Cursor
have no action guard today.

---

### Step 4 — set up privacy

**Strongly recommended, and the one step about your project's data rather than
your machine.** Step 3 constrains what the agent can reach and what it may run.
Neither half has an opinion about the thing Magpie is actually for: reading a
PMC's private list, or a security report still under embargo, and sending it to
a model. That is a command that *should* run, doing exactly what it was asked —
and exporting somebody else's confidential text while it does.

```text
/magpie-setup:privacy-llm
```

> set up privacy for this project

![A privacy-llm run: the LLM stack detected, the matching variant written to the gitignored local directory, the PII redactor proven end to end, and the approved-LLM gate refusing an unregistered local model](../assets/quickstart/step-privacy.svg)

Two mechanisms, separate because they protect different people:

- **the approved-LLM gate** protects the *project* — a skill refuses to fetch
  private-list mail unless every model in the active stack is approved;
- **PII redaction** protects the *third parties a reporter names*, swapping
  them for hash-prefixed identifiers before any model sees the text.

The skill detects your stack rather than interviewing you, writes the matching
variant to the gitignored `.apache-magpie-local/`, then **proves it** by running
both. A gate that says no is the useful output: it names the unapproved model
and leaves your configuration alone until you decide.

Re-run it after `/magpie-setup upgrade` — what counts as approved can narrow
between versions.

→ **The recipes, the variants, and what each mechanism does:**
[`setup/privacy-llm.md`](setup/privacy-llm.md). The approved registry is
**provisional**, pending a ratified ASF Legal policy for AI-assisted handling
of foundation private data; that page carries the full caveat.

---

### Step 5 — use it

![Listing the installed skills, then a triage pass returning 38 open PRs with a proposed action for each and nothing posted](../assets/quickstart/step-use.svg)

Ask in plain language:

> review PR #5193

> triage the latest security reports

or call a skill by name. A marketplace install namespaces skills under the
**plugin** that provides them, as `/<plugin>:<skill>`:

```text
/magpie-pr-management:pr-triage
/magpie-security:issue-triage
```

`/magpie-utilities:list-skills` — *what Magpie skills do I have?* — prints
everything that is installed.

---

### Step 6 — consider adopting Magpie

![An adopt run: three paths staged and not committed, what a contributor gets on clone, and what it does not restrict](../assets/quickstart/step-adopt.svg)

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

The command is `/magpie-setup adopt`, or ask for it — *adopt Magpie for this
repository so everyone gets it on clone*. Nothing runs it for you: unlike
configuration, adoption is never automatic.

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
