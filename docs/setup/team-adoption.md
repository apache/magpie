<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Team adoption — what a repo commits for everyone](#team-adoption--what-a-repo-commits-for-everyone)
  - [Adoption is not an install](#adoption-is-not-an-install)
  - [What adoption commits](#what-adoption-commits)
  - [The committed lock — what a floor means](#the-committed-lock--what-a-floor-means)
  - [Step 1 — Decide which families to recommend](#step-1--decide-which-families-to-recommend)
  - [Step 2 — Commit the default set](#step-2--commit-the-default-set)
  - [Step 3 — Configure the repo's overrides](#step-3--configure-the-repos-overrides)
  - [Step 4 — Maintain it, and upstream what generalises](#step-4--maintain-it-and-upstream-what-generalises)
  - [What a contributor gets on clone](#what-a-contributor-gets-on-clone)
  - [Un-adopting](#un-adopting)
  - [Cross-references](#cross-references)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

# Team adoption — what a repo commits for everyone

**Adoption is a maintainer decision, not an install.** It is the repo saying:
*these are the skill families we recommend here, this is how they should behave
in this project, and anyone who clones us gets that on arrival.*

Installing Magpie is something you do to your own agent, on your own machine,
and it writes nothing to the repository. Adoption is the separate, deliberate
act of committing a recommendation for everyone else.

## Adoption is not an install

Three different things, often confused:

| | Who does it | What it touches | Reversible by |
|---|---|---|---|
| **Install** | you, once per machine | Your agent: the [Apache Magpie Marketplace](marketplace.md) and the plugins you chose. **Nothing in the repo.** | you |
| **[Individual use](individual-use.md)** | you, on any repo | Your own plugin choice, plus an optional gitignored `.apache-magpie-local/`. Works on a repo that has never heard of Magpie. | you |
| **Adoption** *(this page)* | the repo's maintainers, once | Committed files every contributor sees: the default plugin set and the repo's overrides. | a maintainer, via a PR |

Nothing here is a prerequisite for anything else. A contributor can use Magpie
on a repo that never adopts it, and an adopting repo does not oblige anyone to
install what it recommends.

## What adoption commits

Three things, all committed, all optional on their own:

**1. The floor lock — `.apache-magpie.lock`.** The project's adoption record,
written on every client: `method: marketplace`, the `url` the plugins come
from, a `min_version`, and the `plugins` list that *is* the floor. Item 2
below is derived from it, and it is the headline artefact `unadopt` removes —
`uninstall` leaves it alone. See
[The committed lock](#the-committed-lock--what-a-floor-means) below.

**2. The default plugin set — a floor, never a ceiling.** `extraKnownMarketplaces`
plus an `enabledPlugins` block in the repo's `.claude/settings.json`, derived
from the lock. A contributor who clones the repo and trusts it arrives with
`magpie-setup`, `magpie-utilities` and `magpie-agent-guard` already enabled —
no install step, no instructions to follow — and it never blocks or limits
installing more, or running a newer Magpie.

The floor's membership is deliberately small: it is **seeded** with those
three and stays there unless the maintainers explicitly ask for more. That is
a statement about what the repo recommends, not a cap on what any contributor
may run. It **never grows automatically** to match what the adopting
maintainer happens to use: a maintainer-only family such as `magpie-security`
stays a personal, user-scope install, so every contributor isn't paying its
always-on context cost for work only one person does. The committed set is the
floor everyone benefits from, not a roster of one person's preferences.

> [!NOTE]
> The committed default set is **Claude Code only** today. Codex can only
> default-install all ten families, and Gemini has no workspace-extension
> mechanism, so there is nothing useful to commit for either. Contributors on
> those agents install the families they want themselves; everything else on
> this page still applies.

**3. Repo-wide overrides** — `.apache-magpie-overrides/<skill>.md`, committed.
This is how a project changes a framework skill's behaviour without forking the
framework: the skill reads the override file at run-time, before its own default
behaviour. Use it for the rules that are genuinely this project's — its review
thresholds, its label vocabulary, its release conventions. The full contract for
what an override may contain is in
[`agentic-overrides.md`](agentic-overrides.md).

A third thing is **not** part of adoption, though it is often wanted alongside
it: pinning every contributor and CI job to one framework version. That is an
*install method* — the pinned snapshot — and it lives in
[`install-recipes.md`](../quick-start/install-recipes.md#additional-install-methods).

## The committed lock — what a floor means

**A floor is a minimum, never a ceiling or a pin.** `setup adopt` records what
it commits in `.apache-magpie.lock` — `method: marketplace`, the `url` the
plugins come from, a `min_version` set to whatever Magpie version is
installed on the maintainer's machine at adopt time, and a `plugins` list
seeded with the default set from the previous section. Both `min_version`
and `plugins` are floors: a contributor running a newer Magpie, or one with
more families installed, satisfies the lock completely and is told nothing.
Nothing the lock records is ever used to downgrade a plugin, remove one, or
pin the marketplace to a version — the `extraKnownMarketplaces` entry
derived from it is written **untagged**, so a contributor tracks the tip of
the marketplace and simply needs to meet the floor.

The lock itself is written on every client — it is the harness-neutral
record of what the project committed. The derived `.claude/settings.json`
wiring that acts on it is Claude-Code-specific and is written only where the
harness can express it; on Codex or Gemini the lock is still written and
still stands as the project's record, there is just no settings file for
either agent to derive the wiring into.

Every framework skill's pre-flight compares the machine it runs on against
this floor before doing anything else, and brings a machine that falls short
up to it — installing or updating only what the floor names, then stopping
for a restart — but only acts without asking when the lock's `url` is
`apache/magpie`; a lock naming any other marketplace is shown to the user
first. `setup upgrade` can raise the floor as the project's own Magpie moves
forward, but never lowers it. None of this ever limits what a contributor
may install for themselves — see
[What a contributor gets on clone](#what-a-contributor-gets-on-clone) below.

## Step 1 — Decide which families to recommend

Adoption starts as a conversation, not a command. Look at what the project
actually needs someone to be able to do on day one, and keep the committed
floor to that. Everything else is better left to the individuals who want it.

[What each family solves](../quick-start/families.md) is the
catalogue to decide from.

## Step 2 — Commit the default set

```text
/magpie-setup adopt
```

It shows you what it intends to write before writing anything, and it stages
rather than commits — the change lands through your normal review process like
any other. It touches only `extraKnownMarketplaces` and `enabledPlugins`, and
removes nothing: other Magpie plugins, other vendors' plugins and every other
key in `.claude/settings.json` are preserved exactly as they were.

If `.claude/settings.json` exists but does not parse as JSON, it stops and says
so rather than rewriting a file it cannot read.

## Step 3 — Configure the repo's overrides

```text
/magpie-setup override <skill-name>
```

Scaffolds `.apache-magpie-overrides/<skill-name>.md` with the sections an
override file needs, including *why these overrides exist* — write that part
honestly, because it is what a future maintainer (and the upstreaming step
below) will read to decide whether the override still earns its place.

Use `--local` to put an override in your own gitignored `.apache-magpie-local/`
instead, when the change is yours rather than the project's.

## Step 4 — Maintain it, and upstream what generalises

Adoption is ongoing, and this is the part that is easy to skip. An override
that everyone would want is a missing framework feature wearing a disguise:

```text
/magpie-setup:override-upstream <skill-name>
```

It walks the override into a pull request against `apache/magpie`. Once that
merges and the project upgrades, the local override is redundant and the skill
prompts you to delete it — the repo carries less, and every other adopter gets
the improvement.

Keep the committed set honest, too. A family that was recommended for work the
project no longer does is context every contributor pays for on every turn.

## What a contributor gets on clone

They open the repo, trust it, and the default families are enabled. Nothing to
read, nothing to install, no onboarding step that can be missed.

What they do **not** get is a constraint. The committed set is a floor, not a
ceiling or an allowlist:

- they can install any other family for themselves at any time;
- they can use Magpie here without accepting the defaults at all — see
  [individual use](individual-use.md);
- their own `.apache-magpie-local/` overrides still take effect.

## Un-adopting

```text
/magpie-setup unadopt
```

Removes the committed floor lock `.apache-magpie.lock` and the
`.claude/settings.json` wiring derived from it. It **preserves**
`.apache-magpie-overrides/` — the project's hand-written override files are
not the framework's to delete — unless you pass `--purge-overrides`. It leaves
every install alone, yours and everyone else's: un-adopting is the repo
withdrawing a recommendation, not an uninstall from anybody's agent.

To remove an *install*, that is [`uninstall.md`](uninstall.md) — a different
operation with a different blast radius.

## Cross-references

- [**Individual use**](individual-use.md) — the other half of this pair: using
  Magpie on any repo, adopted or not, with nothing committed.
- [**The Apache Magpie Marketplace**](marketplace.md) — installing the plugins
  in the first place.
- [`agentic-overrides.md`](agentic-overrides.md) — the full contract for what
  an override file may contain and how a skill applies it.
- [`install-recipes.md`](../quick-start/install-recipes.md) — install methods, including the
  pinned snapshot when the project needs one committed framework version.
- [Setup skill family](README.md) — every setup skill and its deep docs.
