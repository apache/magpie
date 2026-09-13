<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Your first run with a family](#your-first-run-with-a-family)
  - [1. Run a skill — it notices, and fixes it](#1-run-a-skill--it-notices-and-fixes-it)
  - [2. It configures, deriving what it can](#2-it-configures-deriving-what-it-can)
  - [3. It writes, and nothing is committable](#3-it-writes-and-nothing-is-committable)
  - [4. Run it again](#4-run-it-again)
  - [5. Only if you are adopting: `/magpie-setup adopt`](#5-only-if-you-are-adopting-magpie-setup-adopt)
  - [The other two things the install offers](#the-other-two-things-the-install-offers)
    - [MCP servers — backends a few skills read through](#mcp-servers--backends-a-few-skills-read-through)
    - [Companion skills — other people's packages](#companion-skills--other-peoples-packages)
  - [What you configured, and what you did not](#what-you-configured-and-what-you-did-not)
  - [Where to go next](#where-to-go-next)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Your first run with a family

Installing a family puts its skills in your agent. It does not tell them
anything about your project — which repository, which tracker, which labels
mean "ready for review". A skill that guessed at those would do the wrong
thing confidently, so instead the first one you run stops and says what it
needs.

This page is that first run, end to end, with `magpie-pr-management` as the
example. Every family works the same way; only the list of files differs, and
each family README carries its own list under *Before the first run*.

Steps 1 to 4 are the whole flow for one person. Step 5 is the separate thing a
maintainer does for the project, and most readers never need it.

The starting point is a family already installed —
[Prerequisite: install Magpie from your agent's
marketplace](../setup/marketplace-install.md) if you have not.

## 1. Run a skill — it notices, and fixes it

![A triage run whose pre-flight finds no project configuration, names what it would otherwise have to guess, and starts configuring rather than stopping](../../assets/quickstart/walkthrough/1-preflight-stops.svg)

Sixty-five of the skills open with this check. It costs three file lookups
and, once the configuration resolves, prints nothing at all — you will not see
it again.

You did not have to run anything: the skill invokes
[`/magpie-setup config`](../../skills/setup/config.md) itself and says so.
That is safe to do unasked because of what `config` touches — gitignored files
in your clone and nothing else. It stages nothing, commits nothing, and
changes nothing any teammate can see.

What it will **not** do is proceed on a guess. It did not label anything, post
anything, or fall back to a default committer team.

## 2. It configures, deriving what it can

![What config derived from the repository itself, and the single prompt covering the values it could not](../../assets/quickstart/walkthrough/2-config-wizard.svg)

It reads the skill's declared requirements, derives every value it can from the
repository itself — the `origin` remote, the label taxonomy, the CI checks that
actually run — and asks **one** question covering whatever is left. Skip any of
them; a `TODO` left in place is not an error.

> [!NOTE]
> **`config` is a finished state, not a step towards adopting.** Most people
> who install Magpie should never run `adopt`. Configuring for yourself is the
> whole flow for individual use; step 5 is for the separate case where you are
> a maintainer deciding for the project — and nothing runs it for you.

## 3. It writes, and nothing is committable

![The config result: three files written to the gitignored local directory, the exclusion added to .git/info/exclude rather than .gitignore, and a note that a TODO left in place is not an error](../../assets/quickstart/walkthrough/3-scaffolded.svg)

Everything lands in **`.apache-magpie-local/`**, which is yours:

| | `.apache-magpie-local/` | `.apache-magpie-overrides/` |
|---|---|---|
| Written by | `config` | `adopt` |
| Committed | never | yes |
| Who sees it | you, in this clone | everyone who clones the repo |
| Needs permission | no | a maintainer decision |

**Local wins, per file.** A skill takes your copy of `project.md` if you have
one and the project's otherwise, deciding file by file — so you can hold one
value of your own and take every other from the project.

Note what it did about `.gitignore`: nothing. `.gitignore` is a committed
file, and a sub-action promising to write nothing anyone else sees must not
open by editing one. The exclusion goes in `.git/info/exclude`, which is
per-clone and never committed.

A `TODO` left in place is not an error. The skill that needs a value names it
when it needs it; the skills that do not never look.

## 4. Run it again

![The same triage command, now passing both pre-flight checks and getting on with the work: 38 open PRs, 12 untriaged, with a proposed action per PR](../../assets/quickstart/walkthrough/4-it-runs.svg)

That is individual use, complete. Nothing was committed, no teammate was
affected, and you did not ask anyone's permission.

Which files each family needs is on its README under *Before the first run*:
[security](../security/README.md#before-the-first-run) ·
[release-management](../release-management/README.md#before-the-first-run) ·
[pr-management](../pr-management/README.md#before-the-first-run) ·
[issue](../issue-management/README.md#before-the-first-run) ·
[repo-health](../repo-health/README.md#before-the-first-run) ·
[contributor-growth](../contributor-growth/README.md#before-the-first-run) ·
[mentoring](../mentoring/README.md#before-the-first-run) ·
[utilities](../utilities/README.md#before-the-first-run) ·
[pairing](../pairing/README.md#before-the-first-run) ·
[setup](../setup/README.md#before-the-first-run)

Those tables are generated from the skills themselves, so they cannot drift
from what the skills actually read.

## 5. Only if you are adopting: `/magpie-setup adopt`

![The adopt wizard promoting two of the three local files to the project, leaving the unfinished one behind, and removing the local copies that are now identical](../../assets/quickstart/walkthrough/5-adopt-promotes.svg)

**Nothing runs this for you, and nothing will ask.** Step 2 mentions in one
line that adoption exists and then drops it — because adopting commits a
recommendation every contributor picks up on clone, and that is a decision the
maintainers take together, not a prompt at the end of a configure run.

**Skip it unless you are a maintainer deciding for the project.**

What you already configured is the best starting point, because it is a set of
answers that demonstrably works on this project. `adopt` offers to **promote**
it: copy the files you select into the committed store, leave anything that
still reads `TODO` or looks personal behind, and then drop the local copies
that are now byte-identical — so a correction the project commits later
actually reaches you, instead of being shadowed by your own stale twin
forever.

A maintainer who knows from the start that they are adopting can go straight
here; `adopt` scaffolds whatever `config` did not.

→ [**Team adoption**](../setup/team-adoption.md) is the full walkthrough of
what gets committed and what a contributor sees on clone.

## The other two things the install offers

Neither blocks a first run. Both are offered during install, and both are
worth coming back to once the family is doing something for you.

### MCP servers — backends a few skills read through

Some skills read from somewhere the agent cannot reach on its own: a mailing
list archive, a foundation's roster, a mail account. Those come through MCP
servers, and the wizard offers three:

| Server | What it reads | When you need it |
|---|---|---|
| `ponymail` | ASF mailing-list archives | The primary mail-read backend for the `security` and `release-management` families. **Mandatory for ASF projects**; Gmail is the fallback elsewhere |
| `apache-projects` | ASF rosters, people and releases, read-only | `contributor-nomination` and the security roster paths. **Mandatory for ASF projects** |
| `gmail-plaintext` | — (it *writes*: plain-text Gmail drafts with no tracking redirects) | Only if you draft mail from the agent. Not ASF-gated |

A skill that needs one and cannot find it says so by name, the same way a
skill names a missing configuration file. Nothing silently degrades to a worse
source.

Registering them is a per-machine step, not a per-project one — like the
plugin install itself, and unlike anything `config` writes. The walkthrough is
in
[`/magpie-setup`'s install flow](../setup/marketplace.md#auto-install-arriving-magpie-ready).

### Companion skills — other people's packages

Magpie ships skills for maintaining a project. Some of what a maintainer wants
next is not maintenance — scanning your own code for vulnerabilities, or a
method for thinking a change through before writing it — and other people have
built those well.

The install flow offers them, **never pre-ticked**, and only the ones
available on the agent you are running: a package that exists for Claude Code
alone is not offered to a Codex user with a command they cannot run.

None of them is a dependency. Every family works with none installed, Magpie
bundles none and fetches none automatically, and each entry says whose it is
so the choice stays yours.

→ [**Companion skill packages**](../setup/companion-skills.md) — what each one
adds to which family, and the install command for every agent that has it.

## What you configured, and what you did not

**Per machine, once.** The marketplace install, any MCP servers you
registered, and any companion packages. No repository records them, and a
teammate cloning this repo gets none of them — which is why an MCP server a
family depends on is named in that family's prerequisites rather than assumed.

**Per clone, yours.** Everything `config` wrote, in
`.apache-magpie-local/`. Gitignored, invisible to everyone else, and a
complete end state: a contributor can work this way indefinitely on a
repository that has never adopted Magpie.

**Per project, committed.** Only if step 5 happened: the floor lock, the
derived wiring, and the project's configuration store. A teammate who clones
an adopted repository skips steps 2 and 3 entirely — the configuration is
already there.

**Never.** Nothing above pins a version, removes a plugin, or limits what you
install or configure for yourself. The floor is a minimum in both dimensions —
a contributor running a newer Magpie with seven families installed satisfies it
completely and is told nothing.

## Where to go next

- [**What each family solves**](families.md) — the ten families, with the
  problem each one solves.
- [**Companion skill packages**](../setup/companion-skills.md) — third-party
  packages that pair with a family, and the install command per agent.
- [**Team adoption**](../setup/team-adoption.md) — what adopting commits, how
  the floor is chosen, and what a contributor sees on clone.
- [**Prerequisites for running framework skills**](prerequisites.md) — what
  individual skills need at run time: a tracker, a mail backend, and so on.
