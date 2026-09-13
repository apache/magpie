<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Install, adopt, upgrade: the adoption floor and what each page shows](#install-adopt-upgrade-the-adoption-floor-and-what-each-page-shows)
  - [Problem](#problem)
  - [Scope](#scope)
  - [Decisions](#decisions)
  - [Subsystem A — the adoption floor](#subsystem-a--the-adoption-floor)
    - [The record](#the-record)
    - [`adopt` writes it](#adopt-writes-it)
    - [`setup` arrives pre-filled](#setup-arrives-pre-filled)
    - [`upgrade` splits on adoption](#upgrade-splits-on-adoption)
    - [The pre-flight](#the-pre-flight)
    - [Follow-on surfaces](#follow-on-surfaces)
  - [Subsystem B — the marketplace install as a prerequisite](#subsystem-b--the-marketplace-install-as-a-prerequisite)
  - [Subsystem C — family intros](#subsystem-c--family-intros)
    - [The benefit callout](#the-benefit-callout)
    - [The screenshots](#the-screenshots)
    - [What is retired](#what-is-retired)
  - [Sequencing](#sequencing)
  - [Acceptance criteria](#acceptance-criteria)
  - [Alternatives considered](#alternatives-considered)
  - [Risks](#risks)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Install, adopt, upgrade: the adoption floor and what each page shows

| | |
|---|---|
| **Status** | Design approved; implementation not started |
| **Created** | 2026-09-13 |
| **Supersedes** | Subsystem C of [2026-09-10 repo-committed setup](2026-09-10-repo-committed-setup-design.md) (the family recordings). Amends its Subsystem A: the default set moves from an install-time offer into `adopt`, and gains a version floor. Subsystem B is untouched. |
| **Spec surface** | [`tools/spec-loop/specs/adoption-and-setup.md`](../../tools/spec-loop/specs/adoption-and-setup.md) |

## Problem

Three things a reader cannot currently work out, all of them the same root
cause: **the marketplace path records nothing about itself.**

1. **Install and adopt read as one blurred flow.** The quick start opens with
   `marketplace add`, then `/magpie-setup`, then an "optional: commit a default
   set" aside. A person who only wants to try Magpie cannot tell where trying
   it ends and committing something for their colleagues begins.

2. **Adoption forgets the version it was made against.** `adopt` writes an
   *untagged* `apache/magpie` marketplace entry and three plugin names into
   `.claude/settings.json`. Nothing anywhere records which Magpie version the
   project validated against, so nothing can detect that a contributor is three
   releases behind. `.apache-magpie.lock` — the file whose entire job is
   recording the project's version — exists only on the pinned-snapshot path.

3. **Every page repeats the marketplace install.** The quick start carries it
   four times (once per harness), each of the ten family READMEs carries it
   again, and `magpie-setup.svg` spends its opening seconds recording it. It is
   a one-time prerequisite being re-explained as though it were part of every
   flow.

A fourth, smaller problem travels with the third: the nine
`families/<family>-first-run.svg` recordings all show the same arc — a
pre-flight failing on an unadopted repo. That arc belongs to *setup*, and is
already the subject of `magpie-setup.svg`. Nine recordings of it teach a reader
nothing about what the nine families actually do.

## Scope

Three subsystems. A is the functional change; B and C are the reader-facing
consequence and depend on A's vocabulary.

| | Delivers | Depends on |
|---|---|---|
| **A** | `method: marketplace` in the committed lock; `adopt` writes the floor; `upgrade` raises it; pre-flight enforces it | — |
| **B** | The marketplace install extracted into one per-harness prerequisite page; quick start and family READMEs stop repeating it | A's vocabulary |
| **C** | Family benefit callouts and authored screenshots; the nine family recordings retired | B's page existing to link to |

**Out of scope.** The pinned-snapshot install path and its two lock files keep
their current semantics unchanged — A *adds* a fourth method, it does not
rework the three that exist. Subsystem B of the 2026-09-10 design (the
per-skill first-run wizard) is not started and is not started here. The
secure-isolation setup is untouched.

## Decisions

Six forks, settled during design. Each shapes what follows.

1. **The lock records a floor, never a pin.** `min_version` is a minimum.
   Installed plugins may be — and normally will be — newer. Nothing downgrades
   anything, and the marketplace is added *untagged* so contributors track the
   tip and satisfy the floor by default. The plugin list is a floor in the same
   sense: contributors may install more, and nothing is ever removed.

2. **One committed file for every install method.** `.apache-magpie.lock` gains
   `method: marketplace` alongside `svn-zip` / `git-tag` / `git-branch`, rather
   than a second adoption file with overlapping meaning. Every adopted project
   then has exactly one committed record, and the pre-flight has one file to
   read.

3. **`.claude/settings.json` is derived, not authoritative.** It is regenerated
   from the lock. The lock is harness-neutral; the wiring is per-harness. This
   is what lets a Codex or Gemini adopter have a meaningful adoption record at
   all, on harnesses with no auto-install mechanism to write into.

4. **The pre-flight installs, then reports, on Claude Code; elsewhere it
   prints the command.** `claude plugin list --json`, `claude plugin install`
   and `claude plugin update` are CLI commands the agent can run. Where no such
   CLI exists the same check runs and the same message prints, minus the
   action.

5. **Auto-install is restricted to the framework's own marketplace.** The
   pre-flight acts without asking *only* when the lock's `url` is
   `apache/magpie`. Any other value is reported and requires explicit
   confirmation — see [Risks](#risks).

6. **Families get authored screenshots; setup keeps the one recording.** A
   family's screenshots are rendered from committed transcript files, not
   captured from live runs. Setup's `magpie-setup.svg` stays a real recording,
   re-cut to start *after* the prerequisite.

Decision 1 is the one the rest hangs off, and it settles a fork the 2026-09-10
design left implicit. That design fixed the plugin floor at three and argued
it must not grow to match what a maintainer happened to install, because a
maintainer-only family like `magpie-security` would cost every contributor
always-on context for work one person does. **That argument stands and is
extended**: the floor is now a floor in two dimensions rather than one, and
neither dimension is a ceiling.

## Subsystem A — the adoption floor

### The record

```text
# .apache-magpie.lock — committed; the project's floor.

method:       marketplace
url:          apache/magpie
min_version:  0.2.0

plugins:
  - magpie-setup
  - magpie-utilities
  - magpie-agent-guard
```

Read as: *this project expects at least Magpie 0.2.0, and expects at least
these three plugins to be available.* Neither line is a ceiling. A contributor
running 0.4.0 with seven families installed satisfies this lock completely and
is told nothing.

`min_version` replaces `ref` for this method deliberately. On `git-tag` and
`svn-zip`, `ref` **is** a pin and re-fetching to that exact version is the
whole point; reusing the key here would make two opposite semantics share one
name in one file. The three existing methods keep `ref` and keep pinning.

**One version, compared as PEP 440.** Every Magpie plugin's version tracks the
framework's `pyproject.toml`, so `min_version` is a single framework version
and not a per-plugin constraint. Between releases that version carries a
`.devNNNN` suffix, and a floor may legitimately record one — a maintainer who
adopted against `0.2.0.dev202609110041` is correctly satisfied by `0.2.0`,
which is exactly what PEP 440 ordering gives. Comparison is therefore PEP 440,
not string ordering; `0.10.0` must not compare below `0.9.0`.

**A floor plugin the marketplace no longer ships** is reported as drift by
`verify` with a repair offer, and is *not* something the pre-flight silently
installs around: it means the project's floor names something that no longer
exists, which is a fact for a maintainer to fix in a PR.

### `adopt` writes it

`setup adopt` gains the lock as its first artefact, ahead of the two it already
writes:

1. **`.apache-magpie.lock`** — `method: marketplace`, `url: apache/magpie`,
   `min_version` set to the Magpie version installed on this machine right now
   (the version the maintainer is actually validating against), and the plugin
   floor.
2. **The derived wiring** — `.claude/settings.json`, regenerated from the lock
   under the merge rules already specified in `adopt.md`: two keys touched,
   every other key preserved, nothing removed. The `extraKnownMarketplaces`
   entry stays **untagged** per decision 1.
3. **The overrides store** — `.apache-magpie-overrides/`, unchanged.

All three are `git add`-ed and none is committed. The version bump lands
through the project's normal review, like any other committed file.

The plugin floor is seeded with the framework's three and the maintainer may
add to it. When they do, show the always-on context cost of each addition as
they add it — the cost argument becomes information rather than a rule.

### `setup` arrives pre-filled

`/magpie-setup` in a project whose lock says `method: marketplace` reads the
floor and presents it as the proposed configuration, rather than starting from
the framework defaults. The user may change it. This is the "next time someone
runs setup they get it pre-configured" half of the model, and it costs nothing
beyond reading a file that is already being read for the drift check.

Running plain `setup` still writes nothing to the repo. Changing the committed
floor is `adopt`, and only `adopt`.

**Consequence for the 2026-09-10 design.** Its Subsystem A put an offer at
`install.md` Step M5 to write the default-set block and scaffold the store.
That offer becomes a **pointer**: install says the repo is not adopted and
names `/magpie-setup adopt`, rather than writing files a second way. One writer
of the lock, one writer of the derived wiring.

### `upgrade` splits on adoption

| | Not adopted | Adopted |
|---|---|---|
| Updates the plugins | yes | yes |
| Writes to the repo | **nothing** | raises `min_version`, regenerates the wiring, stages both |
| Commits | — | never |

`min_version` only ever **rises**. An upgrade run on a machine that is somehow
behind the committed floor does not lower it.

### The pre-flight

Two steps are added to [`tools/dev/preflight-block.md`](../../tools/dev/preflight-block.md),
which regenerates into the 65 skills that carry the block. The existing
snapshot-method branch is unchanged.

**Why the check has to live in the skill body at all.** A marketplace install
delivers *skills only*. Nothing in it configures the repository, and on most
harnesses **no code runs** when a plugin is installed or upgraded — there is no
post-install step to rely on. Claude Code's `SessionStart` hook covers only the
all-in-one plugin, so for every other install shape this agentic check is the
one thing standing between a stale or unadopted repo and a skill that acts on
wrong assumptions. That rationale is addressed to maintainers, so it lives here
rather than in the block: the generator copies the source file verbatim,
HTML comments included, so every line of it is paid on all 65 copies. Keep the
block itself to rules the running agent needs.

1. **Lock present and `method: marketplace`** → read installed state from
   `claude plugin list --json` and compare against the floor:
   - a floor plugin absent → install it;
   - a floor plugin present but below `min_version` → update it;
   - everything at or above the floor → **silent**, as today.
2. **Anything but a silent pass** → say what happened, and stop for a restart.
   That covers all three non-silent branches: something was installed or
   updated, there was no CLI so the commands were only printed, or `url` named
   another marketplace so nothing ran. In each the machine is still below the
   floor — Claude Code loads plugins at session start, so the newly installed
   version is not live this turn, and what was only printed has not run at
   all. The skill cannot continue either way; the difference this makes is
   that the user does not have to work out the command.

```text
⚠ magpie-pr-management 0.2.0 installed; this project's floor is 0.3.0.

  ✓ ran: claude plugin update magpie-pr-management@apache-magpie

  Restart the session to load it, then re-run this command.
```

Where no `claude` CLI is present the same comparison runs and the same lines
print, with `run:` in place of `✓ ran:`.

The pre-flight never removes a plugin, never downgrades one, never pins a
marketplace, and never touches a plugin absent from the committed floor.

### Follow-on surfaces

- **`verify`** — reports the floor, what is installed against it, and drift in
  either direction. Being *ahead* of the floor is not drift and is not a fault.
- **`status`** — prints the floor alongside the installed set.
- **`uninstall` / `unadopt`** — `unadopt` removes the lock along with the keys
  it derived; `uninstall` leaves the lock alone, because the project's floor is
  not this machine's install. Both must say which they did.

## Subsystem B — the marketplace install as a prerequisite

A new page, **`docs/setup/marketplace-install.md`** — *"Prerequisite: install
Magpie from your agent's marketplace"* — carries the install once, with one
section per supported harness: Claude Code, OpenAI Codex CLI, VS Code /
GitHub Copilot, Google Gemini CLI, Cursor, `microsoft/apm`, JetBrains IDEs.
Each section is the commands and nothing else.

[`docs/setup/marketplace.md`](../setup/marketplace.md) keeps the reference —
manifest families, per-family vs all-in-one, skill-name differences,
versioning, verification status — and links to the new page for the commands
rather than carrying them.

Everything else links to it and stops repeating it.

**Amended 2026-09-13, after part of this subsystem shipped ahead of its
plan.** The quick start was restructured directly: the two ways to use
Magpie now open the page, the isolation and privacy setup became Step 2b
ahead of the families table, and three sections became sub-pages
(`docs/quick-start/{prerequisites,install-recipes,families}.md`). None of
that was in this design, and the renumbering table it originally carried —
Step 2 becoming Step 1, and so on — no longer describes the page. What
remains of B is therefore smaller and differently shaped:

| Remaining | State |
|---|---|
| `docs/setup/marketplace-install.md`, one section per harness | not started |
| `marketplace.md` links to it instead of carrying commands | not started |
| Quick-start Step 1 becomes a prerequisite pointer | not started — 3 `marketplace add` blocks remain |
| The teammates block becomes a top-level adopt step | partly done — renamed and adoption named, still a `####` inside Step 1 |
| Ten family READMEs drop the marketplace add | not started — all 10 still repeat it |

Already shipped, and not to be redone: the families table extraction, the
two-modes reordering, Step 2b, and naming adoption at its four call sites.

The ten family READMEs keep exactly one install line — their own
`/plugin install magpie-<family>@apache-magpie` — above it a one-line pointer
to the prerequisite. The family-specific line is not duplication; the
marketplace add is.

## Subsystem C — family intros

### The benefit callout

Each family README gains, between its intro prose and its screenshots, a
GitHub-flavoured alert summarising what the family buys you:

```markdown
> [!TIP]
> **Why this family**
> - Review your own diff before a maintainer spends their time on it
> - Findings separated into blocking and non-blocking, so the nits do not
>   drown the real problems
> - Nothing is sent, posted, or merged — the report is the output
```

`> [!TIP]` is chosen over an HTML banner or an SVG header because it is the
only coloured notice that renders as a coloured notice on GitHub — where these
pages are read — and degrades to a readable blockquote in mkdocs, in a plain
`cat`, and in the source release tarball.

### The screenshots

Two to three per family, authored rather than captured:

```text
assets/quickstart/families/pairing/
  self-review.txt          ← authored source; the literal terminal text
  self-review.svg          ← generated
  multi-agent-review.txt
  multi-agent-review.svg
```

A new **`tools/dev/render-screenshot.sh`** renders a transcript to a static SVG
on the shared dark theme and prepends the Apache header. Generation is
deterministic, so the checker can assert that each `.svg` still regenerates
identically from its `.txt` — the staleness guard that hand-authored SVGs
cannot have.

Every argument the repo already made for SVG holds: the output is text, it
reviews as a diff, it carries its own licence header, it stays sharp at any
width, and it costs a fraction of a PNG set in every source release. What
changes is only that the content is *written* rather than captured, which is
what makes twenty of them maintainable.

### What is retired

- **The nine `families/<family>-first-run.svg`** are deleted. They showed
  setup's arc, not the family's.
- **`magpie-setup.svg`** is re-cut to begin *after* the prerequisite: the
  `/magpie-setup` run only. It currently ships as a placeholder, so nothing
  real is lost.
- **`check-quickstart-recording.py`** is reworked rather than replaced. It
  keeps the parse, licence-header, size-cap, embedded-by-the-docs and orphan
  checks, and gains transcript/SVG pairing, the regeneration-staleness check,
  and per-family screenshot coverage. `record-svg.sh` stays for the one
  recording.

## Sequencing

1. **A** — the lock format, `adopt`, `upgrade`, the pre-flight block and its 65
   regenerated copies, then `verify` / `status` / `uninstall`. Self-contained
   and independently shippable.
2. **B** — the prerequisite page, then the quick start and the ten family
   READMEs. Needs A's vocabulary (floor, adopt, `min_version`) to describe.
3. **C** — the renderer, the transcripts, the callouts, the checker rework, and
   the re-cut recording. Needs B's page to exist to link to.

## Acceptance criteria

These land in
[`tools/spec-loop/specs/adoption-and-setup.md`](../../tools/spec-loop/specs/adoption-and-setup.md),
which is how setup behaviour is specified and validated here.

**Subsystem A**

- `adopt` on a marketplace install writes `.apache-magpie.lock` with
  `method: marketplace`, `url: apache/magpie`, a `min_version` equal to the
  version installed at the time, and the plugin floor; stages it; commits
  nothing.
- The derived `.claude/settings.json` preserves every unrelated key, adds only
  missing floor members, removes nothing, and leaves the marketplace entry
  untagged.
- `setup` in an adopted project presents the committed floor as the proposed
  configuration and still writes nothing to the repo.
- A pre-flight on a machine at or above the floor prints nothing.
- A pre-flight below the floor installs or updates only floor plugins, reports
  exactly what ran, and stops for a restart — never removing, downgrading or
  pinning.
- A pre-flight whose lock names a `url` other than `apache/magpie` asks before
  running anything.
- Version comparison is PEP 440: `0.10.0` satisfies a `0.9.0` floor, and
  `0.2.0` satisfies a `0.2.0.dev202609110041` floor.
- `upgrade` writes nothing to the repo when the project is not adopted, and
  raises — never lowers — `min_version` when it is.
- `unadopt` removes the lock; `uninstall` leaves it; each says which it did.

**Subsystem B**

- The marketplace add appears in exactly one page. A grep for
  `plugin marketplace add` outside `docs/setup/marketplace-install.md` and its
  reference page finds nothing in the quick start or any family README.
- Every family README links to the prerequisite and carries exactly one install
  command, its own.

**Subsystem C**

- Every family README carries a benefit callout immediately before its
  screenshots.
- Each `.svg` under `assets/quickstart/families/` regenerates byte-identically
  from its `.txt`; the checker fails on drift, on an orphan in either
  direction, and on a family with no screenshots.
- No `*-first-run.svg` remains, and no document references one.

## Alternatives considered

**A separate adoption file, leaving `.apache-magpie.lock` snapshot-only.**
Rejected: two committed files with overlapping meaning, two files for the
pre-flight to read, and an unanswerable "which wins" the moment a project has
both. The lock's job is already "the project's committed version record"; a
fourth method is a smaller change than a second file.

**`.claude/settings.json` as the sole record.** Rejected on reach. It is the
mechanism Claude Code auto-installs from and it stays exactly that — but a
Codex, Gemini or Copilot adopter would then have no adoption record at all, and
the pre-flight would have to parse a Claude-specific file to learn a
harness-neutral fact.

**Pinning rather than a floor.** Rejected by the maintainer during design. A
pin makes every contributor's upgrade wait on a PR to the adopting repo, and
turns the project's record into a ceiling on individual installs. A floor gets
the same "everyone has at least what this project needs" guarantee with none of
that. It costs the ability to say "everyone is on exactly the same version",
which is the pinned-snapshot install's job and remains available.

**Pre-flight proposing rather than installing.** Rejected by the maintainer
during design, with the trade understood: it mutates global plugin state from
inside an unrelated skill's pre-flight. The mitigations in decision 5 and the
never-remove/never-downgrade/never-pin rule are what make it acceptable.

**Keeping the family recordings and adding screenshots alongside.** Rejected:
the recordings' content is setup's, so keeping them means nine copies of the
quick start's recording filed under ten families.

**Capturing family screenshots from real runs.** Rejected: it is the capture
session the 2026-09-10 work retired, twenty windows instead of fourteen, and
each shot re-captured whenever output moves.

## Risks

**A committed lock can direct the pre-flight to install from an arbitrary
marketplace.** This is the significant one. A repository the user merely opened
could carry a lock naming an attacker's marketplace, and an auto-installing
pre-flight would add it. Decision 5 is the mitigation: auto-install runs only
for `url: apache/magpie`; anything else is reported and confirmed explicitly.
The floor's plugin list is likewise honoured only for plugins from that
marketplace.

**"Automatic" still ends in a restart.** Claude Code loads plugins at session
start, so the pre-flight can install the right version but cannot use it this
turn. The message must say so plainly rather than implying the retry will work
in the same session.

**Authored screenshots can drift from real output.** The checker can prove a
`.svg` matches its `.txt`; it cannot prove the `.txt` matches what the skill
prints today. This is a genuine, unclosed gap — accepted because the
alternative is the capture treadmill, and because a screenshot's job here is to
show the shape of a run, not to serve as a test oracle. Transcripts should be
written to be robust to cosmetic change: no version strings, no counts that a
minor change would move.

**Sixty-five regenerated pre-flight blocks in one change.** The block grows by
roughly a dozen lines and every copy moves with it. Mitigated by the existing
generation-and-check tooling, which already fails the build on drift between
`preflight-block.md` and its copies.
