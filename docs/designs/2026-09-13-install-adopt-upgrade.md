<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Install, adopt, upgrade](#install-adopt-upgrade)
  - [What was wrong](#what-was-wrong)
  - [Decisions](#decisions)
  - [The adoption floor](#the-adoption-floor)
    - [The record](#the-record)
    - [`adopt` writes it](#adopt-writes-it)
    - [The derived wiring, and its merge rules](#the-derived-wiring-and-its-merge-rules)
    - [`setup` arrives pre-filled](#setup-arrives-pre-filled)
    - [`upgrade` splits on adoption](#upgrade-splits-on-adoption)
    - [The pre-flight](#the-pre-flight)
    - [The surfaces that report on it](#the-surfaces-that-report-on-it)
  - [Installing: one page, one command per agent](#installing-one-page-one-command-per-agent)
  - [What a family page shows](#what-a-family-page-shows)
    - [The benefit callout](#the-benefit-callout)
    - [The screenshots](#the-screenshots)
    - [The half of a capture's guarantee that survives](#the-half-of-a-captures-guarantee-that-survives)
    - [What was retired](#what-was-retired)
    - [What a family page asks you to configure](#what-a-family-page-asks-you-to-configure)
    - [Companion skill packages](#companion-skill-packages)
  - [Where the build departed from the design](#where-the-build-departed-from-the-design)
  - [Alternatives considered](#alternatives-considered)
  - [Risks](#risks)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Install, adopt, upgrade

| | |
|---|---|
| **Status** | Built. [Where the build departed from the design](#where-the-build-departed-from-the-design) records the two places it did. |
| **Created** | 2026-09-10, rewritten 2026-09-13 as one document |
| **Replaces** | The two designs and four implementation plans this was split across while it was being built (`2026-09-10-repo-committed-setup-*`, `2026-09-13-install-adopt-upgrade-design`, `-plan-a/b/c`). They described phases; this describes the result. |
| **Spec surface** | [`tools/spec-loop/specs/adoption-and-setup.md`](../../tools/spec-loop/specs/adoption-and-setup.md) |

There are exactly three things a person can do with Magpie, and the whole
design follows from keeping them apart:

- **Install it** — put the plugins in your agent. One command per agent, once
  per machine. Writes nothing to any repository.
- **Configure it** — tell those skills about this project, in
  `.apache-magpie-local/`: gitignored, this clone only, nobody's permission
  required. A skill whose configuration is missing runs this itself. Complete
  on its own, and all most people ever need.
- **Adopt it** — commit, for one repository, the floor and the project's
  configuration. A decision its maintainers make together, reversible in a
  pull request, never run automatically, and never a prerequisite for the
  first two.

Everything below is either one of those three, or the consequence of a reader
being able to tell which one they are looking at.

**Configuring is not a lesser adopting.** It is the finished state for
individual use, which the framework's own docs call "not a waiting room". The
original design had no such step, so the only route to a configured skill was
`adopt` — which stages committed files for every contributor. A solo
contributor on a repository whose maintainers have never heard of Magpie had
to commit something for the team in order to work alone. That was the defect
this split closes.

## What was wrong

The marketplace install became the default path in 0.2.0 and committed nothing
to the repository, by design. Four consequences followed, all from the same
root: **the marketplace path recorded nothing about itself.**

1. **Install and adopt read as one blurred flow.** The quick start opened with
   `marketplace add`, then `/magpie-setup`, then an "optional: commit a default
   set" aside. A person who only wanted to try Magpie could not tell where
   trying it ended and committing something for their colleagues began.

2. **Adoption forgot the version it was made against.** The default-plugin
   block that lets a contributor arrive Magpie-ready existed as copy-paste JSON
   in the marketplace reference; no code path wrote it. And nothing anywhere
   recorded which Magpie version the project had validated against, so nothing
   could detect that a contributor was three releases behind.
   `.apache-magpie.lock` — the file whose entire job is recording the project's
   version — existed only on the pinned-snapshot path.

3. **Every page repeated the marketplace install.** The reference carried it
   per harness, the quick start for four of them, each of the ten family
   READMEs again, and `magpie-setup.svg` spent its opening seconds recording
   it. A one-time prerequisite, re-explained as though it were part of every
   flow.

4. **Every family page opened with a recording of the same thing.** The nine
   `families/<family>-first-run.svg` recordings all showed a pre-flight failing
   on an unadopted repo. That is *setup's* arc, and already the subject of
   `magpie-setup.svg`. Nine copies of it taught a reader nothing about what the
   nine families do — and all nine had sat as "recording pending" placeholders
   since the day they were added.

## Decisions

Each of these settled a fork, and each shapes what follows.

1. **The lock records a floor, never a pin.** `min_version` is a minimum.
   Installed plugins may be — and normally will be — newer. Nothing downgrades
   anything, and the marketplace is added *untagged* so contributors track the
   tip and satisfy the floor by default. The plugin list is a floor in the same
   sense: contributors may install more, and nothing is ever removed.

2. **The floor is framework-defined, not "whatever the maintainer installed."**
   `magpie-setup`, `magpie-utilities`, `magpie-agent-guard`. A maintainer-only
   family such as `magpie-security` would otherwise cost every contributor
   always-on context for work one person does. A maintainer may add to the
   floor deliberately, and is shown each addition's always-on cost as they do.

   A consequence worth stating, because it removes work the original request
   implied: **with a fixed floor there is nothing to re-sync when a maintainer
   installs another family.** No per-install hook is needed — which is
   fortunate, since on most harnesses no code runs on plugin install at all.

3. **One committed file for every install method.** `.apache-magpie.lock` gains
   `method: marketplace` alongside `svn-zip` / `git-tag` / `git-branch`, rather
   than a second adoption file with overlapping meaning. Every adopted project
   then has exactly one committed record, and the pre-flight has one file to
   read.

4. **`.claude/settings.json` is derived, not authoritative.** It is regenerated
   from the lock. The lock is harness-neutral; the wiring is per-harness. This
   is what lets a Codex or Gemini adopter have a meaningful adoption record at
   all.

   On Claude Code that file is also the store behind `--scope project`, which
   settles who writes it: the install step names all three scopes rather than
   defaulting past them — `user` (this machine, every repo), `local`
   (`.claude/settings.local.json`, this repo, gitignored) and `project` (this
   file, committed, everyone) — installs at `user` or `local`, and **never
   passes `project`**. A request for the whole project to get Magpie is a
   request to adopt, and hands off to `adopt`, which runs those same commands
   at `--scope project` and writes the floor the flag alone would leave
   missing. Adoption is a maintainer's act with a record, not a flag on one
   person's install.

5. **Adopting is optional and never a prerequisite.** Plugins work in a
   repository with or without the committed record. A maintainer who declines
   has a supported end state, not a partial install, and setup must not
   describe the result as incomplete.

6. **The agent runs the install; it does not dictate commands to type.**
   `claude plugin list --json`, `claude plugin install`, `claude plugin update`
   and `claude plugin marketplace add` are CLI commands the agent can run —
   the `/plugin …` slash form is not, and conflating the two is what kept the
   install a transcription exercise for the user. Both surfaces that install
   use the CLI: the pre-flight bringing a machine up to a project's floor, and
   the install skill installing the families the user just picked. Where no
   such CLI exists the same decision is made and the same commands print,
   minus the action.

   Three other conditions send it back to printing, and each is reported with
   the reason rather than silently swallowed: a **plugin store the process
   cannot write to** — a sandboxed agent is the common case, and Claude Code's
   own default sandbox denies `~/.claude/plugins/` — a **marketplace other
   than `apache/magpie`** (decision 7), and an **install that stops for a
   marketplace-declared command**. That last one is why `--yes` is never
   passed: the flag exists to accept such a command sight unseen, Magpie's
   catalogue declares none, so an install that demands the flag is not the
   catalogue this step assumed it was talking to.

7. **Auto-install is restricted to the framework's own marketplace.** Both
   surfaces act without asking *only* when the source is `apache/magpie` —
   the lock's `url` for the pre-flight, the `from:` argument for the install
   skill. Any other value is reported and requires explicit confirmation — see
   [Risks](#risks). The third-party companion packages the install offers sit
   on the far side of the same line: their commands are always printed, never
   run.

8. **The install is a prerequisite with one page**, not a step repeated in
   every flow that assumes it.

9. **Configuration has a gitignored home and a committed one, and the same
   lookup chain as overrides.** `<project-config>` resolves per file, local
   first: `.apache-magpie-local/` then `.apache-magpie-overrides/`. One rule
   for everything an adopter writes, rather than one rule for configuration
   and another for overrides.

   The cost is real and is accepted: after a project commits a file you also
   hold locally, yours keeps winning. It is reported rather than silent —
   `verify` lists every shadowing file, and `adopt` drops the copies that are
   byte-identical as it promotes, so the project's later corrections reach
   you.

10. **A skill runs `config` for you; nothing ever runs `adopt` for you.** The
   pre-flight that finds missing configuration invokes `config` unasked,
   because what it touches is gitignored, invisible to everyone else and
   undone by deleting a directory — and unlike a plugin install it needs no
   session restart, so the skill continues in the same turn. Adoption commits
   a recommendation for every contributor; it is mentioned in one line and
   never offered.

11. **A family page shows that family working, and those pictures are written
   rather than captured.** `magpie-setup.svg` stays a real recording — it is
   the one run a reader has not done yet. Everything else is a committed
   transcript rendered deterministically.

## The adoption floor

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
which is exactly what PEP 440 ordering gives. String ordering gets both that
and `0.10.0` against `0.9.0` backwards.

**A floor plugin the marketplace no longer ships** is reported as drift by
`verify` with a repair offer, and is *not* something the pre-flight silently
installs around: it means the project's floor names something that no longer
exists, which is a fact for a maintainer to fix in a pull request.

### `adopt` writes it

`setup adopt` writes three artefacts, `git add`s all three, and commits none —
the version bump lands through the project's normal review, like any other
committed file:

1. **`.apache-magpie.lock`** — `method: marketplace`, `url: apache/magpie`,
   `min_version` set to the Magpie version installed on this machine right now
   (the version the maintainer is actually validating against), and the plugin
   floor.
2. **The derived wiring** — `.claude/settings.json`, regenerated from the lock
   under the merge rules below. The `extraKnownMarketplaces` entry stays
   **untagged** per decision 1.
3. **The overrides store** — `.apache-magpie-overrides/`, scaffolded from
   `projects/_template/`.

### The derived wiring, and its merge rules

The repository's `.claude/settings.json` is not Magpie's file. This repository's
own carries `sandbox` and `permissions` blocks that must survive untouched, and
an adopter's will carry whatever they put there.

- Merge **only** `extraKnownMarketplaces` and `enabledPlugins`. Every other key
  is preserved byte for byte.
- If `extraKnownMarketplaces` already defines `apache-magpie`, leave the
  existing definition alone — an adopter pinning `apache/magpie@0.2.0` has made
  a deliberate choice.
- If `enabledPlugins` exists, **add** missing floor members and **remove
  nothing**. A project that has enabled other plugins, Magpie's or anyone
  else's, keeps them.
- If the file does not exist, create it with those two keys and nothing else.
- If the file exists but is not valid JSON, stop and say so. Do not rewrite it.

**Harness reach.** Claude Code expresses the whole floor through that file.
Codex expresses part of it: its catalogue marks `magpie-setup`
`INSTALLED_BY_DEFAULT` and every other family `AVAILABLE`, so the floor's
central plugin arrives on its own and the rest stay opt-in. That became
possible only once each family plugin carried its own skills as real
directories — while an all-in-one plugin existed, defaulting anything on meant
defaulting everything on. The remaining harnesses have no repo-side
pre-install mechanism, and setup says so plainly rather than writing a file
that does nothing.

### `setup` arrives pre-filled

`/magpie-setup` in a project whose lock says `method: marketplace` reads the
floor and presents it as the proposed configuration, rather than starting from
the framework defaults. The user may change it. This is the "next time someone
runs setup they get it pre-configured" half of the model, and it costs nothing
beyond reading a file that is already being read for the drift check.

Running plain `setup` still writes nothing to the repository. Changing the
committed floor is `adopt`, and only `adopt`. Install therefore *points at*
`/magpie-setup adopt` rather than offering to write the same files a second
way: one writer of the lock, one writer of the derived wiring.

### `upgrade` splits on adoption

| | Not adopted | Adopted |
|---|---|---|
| Updates the plugins | yes | yes |
| Writes to the repo | **nothing** | raises `min_version`, regenerates the wiring, stages both |
| Commits | — | never |

`min_version` only ever **rises**. An upgrade run on a machine that is somehow
behind the committed floor does not lower it.

### The pre-flight

Two steps in [`tools/dev/preflight-block.md`](../../tools/dev/preflight-block.md),
which regenerates into the 65 skills that carry the block. The existing
snapshot-method branch is unchanged.

**Why the check lives in the skill body at all.** A marketplace install
delivers *skills only*. Nothing in it configures the repository, and on most
harnesses **no code runs** when a plugin is installed or upgraded — there is no
post-install step to rely on. Claude Code's `SessionStart` hook rides on
`magpie-setup`, so for an install without that plugin, and for every
non-Claude install, this agentic check is the one thing standing between a
stale or unadopted repo and a skill acting on wrong assumptions. That rationale
is addressed to maintainers, so it lives here rather than in the block: the
generator copies its source file verbatim, HTML comments included, so every
line of it is paid on all 65 copies. Keep the block itself to rules the running
agent needs.

1. **Lock present and `method: marketplace`** → read installed state from
   `claude plugin list --json` and compare against the floor:
   - a floor plugin absent → install it;
   - a floor plugin present but below `min_version` → update it;
   - everything at or above the floor → **silent**, as today.
2. **Anything but a silent pass** → say what happened, and stop for a restart.
   That covers all three non-silent branches: something was installed or
   updated, there was no CLI so the commands were only printed, or `url` named
   another marketplace so nothing ran. In each the machine is still below the
   floor — Claude Code loads plugins at session start, so a newly installed
   version is not live this turn, and what was only printed has not run at all.
   The skill cannot continue either way; what this buys the user is not having
   to work out the command.

```text
⚠ magpie-pr-management 0.2.0 installed; this project's floor is 0.3.0.

  ✓ ran: claude plugin update magpie-pr-management@apache-magpie

  Restart the session to load it, then re-run this command.
```

Where no `claude` CLI is present the same comparison runs and the same lines
print, with `run:` in place of `✓ ran:`.

The pre-flight never removes a plugin, never downgrades one, never pins a
marketplace, and never touches a plugin absent from the committed floor. It
must also never treat a *missing* record as an unadopted repo in a way that
makes adoption feel required — that would convert an optional convenience into
a de-facto prerequisite, contradicting decision 5.

### The surfaces that report on it

- **`verify`** — reports the floor, what is installed against it, and drift in
  either direction. Being *ahead* of the floor is not drift and is not a fault.
  A floor absent entirely is reported as fine, with one line noting it is
  available.
- **`status`** — prints the floor alongside the installed set.
- **`uninstall` / `unadopt`** — `unadopt` removes the lock along with the keys
  it derived, leaving the rest of `.claude/settings.json` intact; `uninstall`
  leaves the lock alone, because the project's floor is not this machine's
  install. Both must say which they did, and both preserve
  `.apache-magpie-overrides/` by default.

## Installing: one page, one command per agent

[`docs/setup/marketplace-install.md`](../setup/marketplace-install.md) —
*"Prerequisite: install Magpie from your agent's marketplace"* — carries the
install once, one section per harness: Claude Code, OpenAI Codex CLI, VS Code /
GitHub Copilot, Google Gemini CLI, Cursor, `microsoft/apm`, Kiro CLI, JetBrains
IDEs. Each section is the commands and nothing else. Kiro is the one with no
marketplace — it installs skills one at a time from a GitHub subdirectory — and
the page says so rather than omitting it.

[`docs/setup/marketplace.md`](../setup/marketplace.md) keeps the reference —
manifest families, which families to pick, skill-name differences, versioning,
verification status — and links for the commands rather than carrying them. It
loses commands, not reasoning.

Everything else links to it. The ten family READMEs keep exactly one install
line, their own `/plugin install magpie-<family>@apache-magpie`: that line is
not duplication, because it differs per page. The marketplace *add* is, and it
was carried twelve times.

A twelfth check in
[`check-doc-sync.py`](../../tools/dev/check-doc-sync.py) keeps it that way: the
add — and the Codex, Gemini and `apm` equivalents — may appear in those two
pages and nowhere else under `docs/`. `docs/designs/` is exempt, because a
design records what was decided and rewriting the record to satisfy a linter
would make it wrong. The repository README keeps its copy deliberately: the
front page shows the shortest path in, not a link to it.

Without that check the repetition returns the next time someone documents an
install, and nothing notices. It is not in any earlier version of this design;
it is here because the design's central claim — that the install is carried
once — otherwise has no guard, and this repository has twice had a documented
fact drift because nothing checked it.

## What a family page shows

### The benefit callout

Each family README carries, between its intro prose and its screenshots, three
bullets saying what the family buys you:

```markdown
> [!TIP]
> **Why this family**
> - Review your own diff before a maintainer spends their time on it
> - Findings split into blocking and non-blocking, so the nits do not drown
>   the real problems
> - Nothing is sent, posted, or merged — the report is the output
```

`> [!TIP]` over an HTML banner or an SVG header because it is the only coloured
notice that renders as a coloured notice on GitHub — where these pages are
read — and degrades to a readable blockquote in mkdocs, in a plain `cat`, and
in the source release tarball.

### The screenshots

Two or three per family, one for every command that family's *Try these first*
section already tells a newcomer to run — twenty-eight in all, authored rather
than captured:

```text
assets/quickstart/families/pairing/
  self-review.txt          ← authored source; the literal terminal text
  self-review.svg          ← generated
  multi-agent-review.txt
  multi-agent-review.svg
```

[`tools/dev/render-screenshot.sh`](../../tools/dev/render-screenshot.sh)
renders a transcript to a static SVG on the recorder's palette and prepends the
Apache header. Colour comes from the line itself — a `>` prompt, a `✓`/`⚠`/`✗`
status glyph, an ALL-CAPS section label — so a transcript stays something you
read as a terminal rather than as markup. No Node: the recorder needs
`svg-term-cli`, this runs on a bare clone and in CI.

Every argument the repository already made for SVG holds — the output is text,
it reviews as a diff, it carries its own licence header, it stays sharp at any
width, and it costs a fraction of a PNG set in every source release. What
changed is only that the content is *written*, which is what makes
twenty-eight of them maintainable.

### The half of a capture's guarantee that survives

A capture guarantees the picture matches the program. Authoring does not, and
that is the real cost. The design buys back the half it can: **rendering is
deterministic** — same `.txt`, same `.svg`, byte for byte, on any machine — so
[`check-quickstart-recording.py`](../../tools/dev/check-quickstart-recording.py)
can prove every committed `.svg` still regenerates from its source. Edit one
without re-rendering and the build fails. Forcing `LC_ALL=C` inside the
renderer is part of that rather than a detail: `awk`'s `length()` is
locale-dependent, and a renderer whose output moved between machines could not
be checked at all.

What nothing can prove is that a transcript still matches what the skill prints
today. That gap is accepted deliberately — a screenshot's job here is to show
the shape of a run, not to serve as a test oracle — and
[`assets/quickstart/README.md`](../../assets/quickstart/README.md) says so
plainly rather than letting a reader assume the check is stronger than it is.
Transcripts are written to be robust to cosmetic change: no version strings, no
dates, no counts a minor change would move.

### What was retired

- **The nine `families/<family>-first-run.svg`.** They showed setup's arc, not
  the family's.
- **`assets/examples/`.** Two placeholder recordings doing the same job as the
  authored screenshots, by capture, for one family.
- **`record-svg.sh` drops from eleven targets to one.** `/magpie-setup` is the
  exception worth a capture.
- **The checker's placeholder machinery.** It existed because ten recordings
  meant ten capture sessions, and blocking commits until someone sat down with
  asciinema would have got the hook disabled. One recording is a thing a person
  does once; a screenshot is a file you write. A missing file is now an error.

The checker was reworked rather than replaced: it keeps the parse,
licence-header, size-cap, embed and orphan checks, and gains transcript/SVG
pairing, per-family coverage, a check that a screenshot names a skill its family
actually ships, and the regeneration-staleness check.

### What a family page asks you to configure

The same `requires_config:` frontmatter that drives `config` generates, per
family, the table of what that family needs before it will run — required and
optional split, with a *Read by* column naming the skills. It replaced a
hand-maintained table in nine of the ten family READMEs, which had drifted
exactly as far as an unguarded table does: `security` listed none of the
thirteen files its skills read, `repo-health` none of three,
`release-management` one of five.

Above it sits an **animated** `/magpie-setup config` run for that family,
generated from the same frontmatter by `render-wizard.py`. A still frame of a
wizard is a wizard with the interesting part removed; what a first-time reader
needs to see is the shape of the conversation — auto-detect first, one batched
question, gitignored files out. It is illustrative rather than a recording, and
the embed says so.

### Companion skill packages

Magpie ships skills for maintaining a project. Some of what a maintainer wants
next is not maintenance — scanning your own code, or a method for thinking a
change through — and other people have built those well. A registry names
them, per family, and the install flow offers them alongside the families and
the MCP servers.

Three rules make it a pointer rather than an advert:

- **Per harness, not per package.** Superpowers installs on six agents with
  six different commands; Claude Security on one. A package is offered only
  where it can actually be installed, and a package available on one agent
  says so rather than being presented as the answer for everyone.
- **Never a dependency, and never pre-ticked.** Every family works with none
  installed. An entry whose `why` cannot say what it adds to a *named* family
  is refused by the checker.
- **The marketplace is its own decision.** Where a package lives in a
  catalogue Magpie does not publish, `install` and `marketplace` are separate
  fields, the offer names whose catalogue it is, and the add is a step of its
  own. Nothing is added on anybody's behalf — the same rule as decision 7,
  reaching a different surface.

## Where the build departed from the design

Two places, both deliberate, both worth recording because the design argued
for the other thing.

**The per-skill configuration wizard became `config`, and writes locally.**
The design put the wizard behind the pre-flight and had it write into
`.apache-magpie-overrides/` — the *committed* store — then stage the result.
That was wrong for the case it exists to serve. A contributor whose skill
lacks configuration is usually one person on a repository that has not adopted
Magpie, and making them stage committed files for the whole team in order to
work alone is the same defect this design opens by naming. So the wizard is
`config`, it writes gitignored `.apache-magpie-local/`, and `adopt` promotes
from it when a maintainer decides the project should publish those answers.

Everything else the design specified for it shipped as specified: the
`requires_config:` frontmatter, the *optional* set derived rather than
hand-written, the `--fix` checker and its pre-commit hook, the validation that
every named file exists in `projects/_template/` — which found three that did
not — and the wizard living in one place rather than propagated into 65 skill
bodies.

**`magpie-setup.svg` is generated rather than re-cut.** The design listed
re-cutting it as work needing a terminal, a scratch project and a human,
because the committed recording opened with the marketplace install that had
become a prerequisite. Rather than schedule the human, the artefact is now
generated by `render-wizard.py` — the whole first run including the
secure-agent setup, deterministic and checked like everything else — and the
recorder is retired. Nothing in the repository is captured any more, which
also ends the standing risk that the one artefact needing a person stays wrong
because a person is hard to schedule.

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
pin makes every contributor's upgrade wait on a pull request to the adopting
repository, and turns the project's record into a ceiling on individual
installs. A floor gets the same "everyone has at least what this project needs"
guarantee with none of that. It costs the ability to say "everyone is on exactly
the same version", which is the pinned-snapshot install's job and remains
available.

**A floor that grows to match what the maintainer installed.** Rejected: a
maintainer-only family like `magpie-security` would cost every contributor
always-on context for work one person does, and it would need a re-sync hook on
a set of harnesses where nothing runs on install.

**Pre-flight proposing rather than installing.** Rejected by the maintainer
during design, with the trade understood: it mutates global plugin state from
inside an unrelated skill's pre-flight. Decision 7 and the
never-remove/never-downgrade/never-pin rule are what make it acceptable.

**Keeping the family recordings and adding screenshots alongside.** Rejected:
the recordings' content is setup's, so keeping them means nine copies of the
quick start's recording filed under ten families.

**Capturing family screenshots from real runs.** Rejected: it is the capture
session this work exists to retire, and every shot is re-captured whenever
output moves. The nine placeholders that never became recordings are the
evidence.

## Risks

**A committed lock can direct the pre-flight to install from an arbitrary
marketplace.** This is the significant one. A repository the user merely opened
could carry a lock naming an attacker's marketplace, and an auto-installing
pre-flight would add it. Decision 7 is the mitigation: auto-install runs only
for `url: apache/magpie`; anything else is reported and confirmed explicitly.
The floor's plugin list is likewise honoured only for plugins from that
marketplace.

**"Automatic" still ends in a restart.** Claude Code loads plugins at session
start, so the pre-flight can install the right version but cannot use it this
turn. The message says so plainly rather than implying the retry will work in
the same session.

**Authored screenshots can drift from real output.** The checker can prove a
`.svg` matches its `.txt`; it cannot prove the `.txt` matches what the skill
prints today. Genuine, unclosed, and accepted — see
[the half of a capture's guarantee that survives](#the-half-of-a-captures-guarantee-that-survives).

**Sixty-five regenerated pre-flight blocks in one change.** The block grew by
roughly a dozen lines and every copy moved with it. Mitigated by the existing
generation-and-check tooling, which fails the build on drift between
`preflight-block.md` and its copies.
