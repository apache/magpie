<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Quick start](#quick-start)
  - [Step 1 — install from your agent's marketplace](#step-1--install-from-your-agents-marketplace)
    - [Claude Code](#claude-code)
    - [OpenAI Codex CLI](#openai-codex-cli)
    - [VS Code / GitHub Copilot](#vs-code--github-copilot)
    - [Google Gemini CLI](#google-gemini-cli)
  - [Step 2 — run `/magpie-setup`](#step-2--run-magpie-setup)
    - [Every skill configures itself on first use](#every-skill-configures-itself-on-first-use)
  - [Step 3 — use it](#step-3--use-it)
  - [What each family solves](#what-each-family-solves)
  - [What happens next — the secure isolation setup](#what-happens-next--the-secure-isolation-setup)
  - [Two ways to use Magpie](#two-ways-to-use-magpie)
    - [Install methods](#install-methods)
    - [Fallback — the pinned snapshot install](#fallback--the-pinned-snapshot-install)
    - [Working on Magpie itself — self-adoption](#working-on-magpie-itself--self-adoption)
  - [Cross-references](#cross-references)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

# Quick start

Install Apache Magpie into the agent you already use, in a couple of
commands: one to add the marketplace, one per family you want. Nothing is
committed to your repository, and nothing is changed in it.

**This install is yours, on this machine.** It needs no decision from your
project and no opt-in from your teammates — see
[two ways to use Magpie](#two-ways-to-use-magpie) if you are wondering
which is which.

**What you get.** 74 skills your agent can run, grouped into 10 **families** —
PR triage and review, issue triage, security-report handling, release
management, contributor mentoring. Install only the families you need; each one
you add costs context in every session —
[what each family solves](#what-each-family-solves) lists all ten, after the
install steps.

---

## Step 1 — install from your agent's marketplace

Pick your agent. Every path uses the
[`apache/magpie`](https://github.com/apache/magpie) repository directly as
the marketplace; no vendor directory or account is involved.

### Claude Code

Add the marketplace, then install **one plugin per family you actually want**:

```text
/plugin marketplace add apache/magpie
/plugin install magpie-setup@apache-magpie
/plugin install magpie-pr-management@apache-magpie
```

`magpie-setup` is the one to always take — it carries the secure-isolation
skills from [the next section](#what-happens-next--the-secure-isolation-setup).
Add the rest to match a problem you have today; you can install more at any
time.

Pick your families from
[What each family solves](#what-each-family-solves) below — the ten of them,
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

#### Optional: commit a default set for your teammates

Everything above installs Magpie for **you, on this machine** — nothing is
written to the repository, and your teammates are unaffected.

A project can go one step further and commit a small block to its
`.claude/settings.json` naming the marketplace and three plugins, so anyone who
clones the repo and trusts it arrives with `magpie-setup`, `magpie-utilities`
and `magpie-agent-guard` already enabled. `/magpie-setup` offers to write it —
see [the default set](setup/marketplace.md#claude-code-the-default-set).

**This is entirely optional.** The plugins work in the repo whether or not the
block is committed, and a project that never commits it is not missing
anything: the install you just did is complete. It is a convenience for
teams — nobody has to run the install by hand — not a requirement.

### OpenAI Codex CLI

```bash
codex plugin marketplace add apache/magpie
codex plugin install magpie
```

### VS Code / GitHub Copilot

Point VS Code's plugin install at the repository URL — it clones the repo
and loads Magpie as an [Agent Plugins 1.0](https://agent-plugins.org/specification)
package:

```text
https://github.com/apache/magpie
```

This path is not yet live-installed against a running VS Code — see
[Verification status](setup/marketplace.md#verification-status).

### Google Gemini CLI

```bash
gemini extensions install https://github.com/apache/magpie
```

This path is not yet live-installed either — see
[Verification status](setup/marketplace.md#verification-status).

> [!IMPORTANT]
> **The all-in-one `magpie` plugin is not recommended** unless you genuinely
> want every family. It installs all 74 skills and adds **~8.6k always-on
> tokens to every session** — context spent whether or not you invoke a Magpie
> skill that turn — against 0.2–2.0k for a family you picked on purpose.
> Reach for it only when you really do need all ten families, or on Windows
> without symlink support (per-family plugins rely on git symlinks; see the
> [Windows note](setup/marketplace.md#choosing-a-plugin-all-in-one-vs-per-family)).

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
> **Per-family plugins are Claude Code-only** today, for the packaging reason
> recorded in
> [the Apache Magpie Marketplace](setup/marketplace.md#choosing-a-plugin-all-in-one-vs-per-family).
> The three agents above can install only the all-in-one `magpie` plugin — so
> on those, the ~8.6k always-on cost is currently the price of entry. Cursor,
> Kiro, OpenCode, and `microsoft/apm` are covered there too.

---

## Step 2 — run `/magpie-setup`

The marketplace install above is complete on its own: the skills are in your
agent and you can start using them. `/magpie-setup` is what you run next when
you want Magpie wired into a **project** rather than only into your own agent —
a committed version pin, project config, overrides, or the optional default set
for your teammates.

One command. It works out which method fits this checkout, prints the plan it
intends to carry out, and waits:

```text
/magpie-setup
```

![A `/magpie-setup` run in Claude Code: the marketplace install, then the skill detecting the checkout, printing the method and plan it intends to carry out, and waiting for approval before writing anything](../assets/quickstart/magpie-setup.svg)

Nothing is written before you approve it. Afterwards, `/magpie-setup verify`
re-runs the health check and drift detection, and `/magpie-setup:status`
prints what is currently installed.

Not sure you need this step? [Two ways to use Magpie](#two-ways-to-use-magpie)
draws the line.

### Every skill configures itself on first use

You do not have to remember which projects are set up, or run anything to
prepare a family before you use it. **65 of the 74 skills open with a silent
pre-flight** — the nine exceptions are the setup skills themselves, which are
what you run to fix whatever it finds.

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
run, pre-flight and all. [What each family solves](#what-each-family-solves)
links to all ten.

---

## Step 3 — use it

Ask in plain language:

> review PR #5193

> triage the latest security reports

or call a skill by name. A marketplace install namespaces skills under the
**plugin** that provides them, as `/<plugin>:<skill>`:

```text
/magpie-pr-management:triage
/magpie-security:issue-triage
```

With the all-in-one plugin the namespace is just `/magpie:` — e.g.
`/magpie:pr-management-triage`. `/magpie-utilities:list-skills` prints
everything that is installed.

---

## What each family solves

Skills ship in ten **families**. Install the ones that match a problem you have
today — you are not meant to take all of them.

| Plugin | Skills | The problem it solves | What it offers |
|---|---|---|---|
| `magpie-setup` | 9 | Your agent can read every credential on your machine, and you have no way to tell whether it is sandboxed right now. | A filesystem sandbox, a clean-env wrapper, a status line that shows sandbox state, and a red banner before any bypass. Plus install, upgrade, and drift checks. **Take this one.** |
| `magpie-security` | 15 | Security reports arrive by mail and must be triaged, fixed, and disclosed on a clock — with nothing leaking early. | A 16-step lifecycle: intake from the mailbox, validity triage, canned responses, fix drafting, CVE allocation, advisory and publication. Drafts land in Gmail; nothing is ever sent for you. |
| `magpie-release-management` | 10 | An ASF release is a long checklist where one missed step invalidates the vote. | RC cut, RC verification (signatures, hashes, LICENSE/NOTICE, no stray binaries), the `[VOTE]` thread, the tally, promotion, `[ANNOUNCE]`, archive sweep, audit log. The agent never holds your signing key and never publishes. |
| `magpie-pr-management` | 8 | The PR queue grows faster than you can read it, and the oldest ones quietly rot. | Queue triage into ready / needs-review / waiting-on-author, deep code review with blocking vs non-blocking findings, reviewer routing, express-lane merge, stale sweep, and queue statistics. |
| `magpie-issue` | 8 | A backlog full of duplicates, unreproducible reports, and issues nobody has read in a year. | Triage with proposed labels, duplicate clustering, reproduction attempts across versions, fix drafting, reassessment of old issues, stale sweep, and backlog stats. |
| `magpie-repo-health` | 7 | Slow rot you only notice when it breaks: vulnerable deps, unpinned actions, licence drift, flaky tests. | Read-only audits for dependency CVEs, dependency licences, LICENSE/NOTICE compliance, Actions workflow security, obsolete runner labels, and flaky-test patterns — plus a skill that fixes what they find. |
| `magpie-contributor-growth` | 6 | Contributors who have earned committership go unnoticed because nobody is tracking the signal. | Activity sweeps against a review threshold, readiness tracking, sentiment signals, nomination briefs for the PMC, and committer / post-vote onboarding checklists. |
| `magpie-utilities` | 5 | You want to write your own skills, or find out what is actually installed. | Skill authoring and restructuring, a state reconciler, a live index of installed skills, and a path to report framework bugs upstream. |
| `magpie-mentoring` | 4 | Newcomers open one PR, hit a wall of unwritten conventions, and never come back. | First-contact welcome comments, plain-language explanations of an issue for someone new, good-first-issue authoring, and a sweep that keeps that backlog honest. |
| `magpie-pairing` | 2 | You want the obvious problems found before a reviewer spends their time on them. | A structured self-review of your own diff, and a multi-agent adversarial review that verifies its findings before reporting them. |

---

## What happens next — the secure isolation setup

Magpie's skills read issues, pre-disclosure security reports, and private
mailing lists. So the first skill worth running is the one that locks the
agent down:

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

---

## Two ways to use Magpie

What you did above is **install** it: the marketplace and the plugins went into
your agent, and nothing was written to any repository. That install is complete
on its own, and it is all most people ever need.

From here the two ways to use it differ in one thing only — whether anything is
committed for other people.

| | [**Individual use**](setup/individual-use.md) | [**Team adoption**](setup/team-adoption.md) |
|---|---|---|
| Who decides | You | The repo's maintainers |
| What it commits | Nothing | The default plugin set, and the repo's shared overrides |
| Which repos | Any — adopted or not, whether or not your teammates use Magpie | The one repo, for everyone who clones it |
| What a teammate sees | Nothing at all | The default families already enabled on arrival |
| Undone by | You, any time | A maintainer, via a PR |

**Individual use is the default, and it is not a waiting room.** You can work
this way indefinitely, on a repo whose maintainers have never heard of Magpie.
Nothing on this page asks the project for permission.

**Adoption is a recommendation, not a restriction.** A repo that has adopted
Magpie gives contributors a sensible floor on clone — it never limits what
anyone may install for themselves, and it never obliges a contributor to use
what it recommends.

Neither one is an install method. Installing is what you already did; these are
what you do with it.

### Install methods

Separately from the above, the framework can *reach* your agent by more than
one route:

| | Who installs it | What it touches |
|---|---|---|
| **Marketplace install** (above) | You, per machine | Your agent. Nothing in the repo. |
| **Pinned snapshot install** | The project, once | A committed version pin and a gitignored snapshot in the repo. |
| **Self-adoption** (`method:local`) | The Magpie checkout itself | Committed symlinks onto the repo's own `skills/`. |

### Fallback — the pinned snapshot install

Use the snapshot install when a marketplace is not an option or not enough:

- your agent has no plugin or marketplace mechanism at all;
- you need the **signed ASF source release** from `dist.apache.org` rather
  than a git clone;
- the project wants every contributor and CI job pinned to **one committed
  version**, with drift detection and project-specific overrides.

It puts a gitignored snapshot plus a committed `.apache-magpie.lock` in the
repo, and wires the skills into *any* agent through `.agents/skills/`:

```text
/magpie-setup install
```

**Skill names differ here.** On the snapshot install a skill is one token —
`/magpie-security-issue-triage`, the skill's directory name — not
`/magpie-security:issue-triage`. There is no plugin namespace; the `magpie-`
prefix is the namespace. See
[Skill names differ by install method](setup/marketplace.md#skill-names-differ-by-install-method).

→ [`setup/install-recipes.md`](setup/install-recipes.md) has the
copy-pasteable bootstrap. The two are complementary, not exclusive: pin the
snapshot for the project and keep the marketplace plugin for yourself if you
prefer.

### Working on Magpie itself — self-adoption

Inside a clone of [`apache/magpie`](https://github.com/apache/magpie), the
default is neither of the above: the framework **self-adopts**, linking its own
live `skills/` source so the skills you are editing are the skills that run.

```text
/magpie-setup method:local
```

`/magpie-setup` detects the framework checkout and takes this path by default —
a remote method against it is refused, because snapshotting the framework into
itself would shadow the live source with a stale copy. It fetches nothing: the
`magpie-<skill>` symlinks point at in-repo paths and are **committed**, and
`.apache-magpie.lock` records `method: local` with no URL or ref. Contributors
get it on a fresh clone with no install step at all.

Self-adoption uses the **same single-token names as the snapshot install** —
`/magpie-pairing-self-review`, not `/magpie-pairing:self-review`.

## Cross-references

- [`docs/index.md`](index.md) — what Magpie is and which skill families exist.
- [**The Apache Magpie Marketplace**](setup/marketplace.md) — the full
  reference: every agent that can add it, per-family plugins, versioning.
- [`docs/prerequisites.md`](prerequisites.md) — what individual skills need
  (GitHub auth, Gmail MCP, browser).
- [`docs/setup/README.md`](setup/README.md) — the setup skill family.
