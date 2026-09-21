<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/legal/release-policy.html -->
# adopt — commit the repo's recommended defaults for every contributor

Adoption is **not** an install. Installing puts the Apache Magpie
Marketplace and
plugins into *this machine's* agent and writes nothing to the
repository. Adopting is the separate, deliberate act of a repo's
maintainers committing a recommendation that every contributor picks
up on clone:

1. **The default plugin set** — `extraKnownMarketplaces` plus an
   `enabledPlugins` floor in the repo's `.claude/settings.json`.
2. **The overrides store** — `.apache-magpie-overrides/`, where the
   project's own skill-behaviour changes live.

Neither is required to use Magpie in this repo. A contributor can
install whatever they like and ignore both; see
[`docs/setup/individual-use.md`](../../../../docs/setup/individual-use.md).
The reader-facing page for this sub-action is
[`docs/setup/team-adoption.md`](../../../../docs/setup/team-adoption.md).

## Inputs

- No positional argument. `setup adopt` adopts the repo you are in.
- `--purge-overrides` — **`unadopt` only, never `adopt`.** Also remove
  `.apache-magpie-overrides/`, which is preserved by default.
  [`uninstall`](uninstall.md) takes the same flag, with the same
  default.

## Step 0 — Pre-flight

1. **Main checkout only.** `adopt` writes committed repo files. In a
   worktree, stop and say so.
2. **Claude Code only, for the default set.** On any other client,
   skip the default set entirely and say why rather than writing a
   file that does nothing: Codex can only default-install all ten
   families, and Gemini has no workspace-extension mechanism. The
   overrides store in Step 4 still applies on every client.
3. **Is this the user's decision to make?** Adoption commits files
   that change what every contributor's agent loads. If there is any
   sign this is not a maintainer acting for the project — they say
   they are "just trying it", they are working in someone else's
   repo, they came here from an install flow — say what adoption
   commits and confirm before going further.

## Step 1 — Decide the default set

The floor is **seeded** with `magpie-setup`, `magpie-utilities` and
`magpie-agent-guard`, in that order, and that is what it stays unless
the maintainer explicitly asks for more.

It **never grows automatically** — not to match what this maintainer
installed, not to match what the framework has started shipping. A
maintainer-only family such as `magpie-security` stays a personal,
user-scope install — committing it would make every contributor pay
its always-on context cost for work only one person does.

If the user asks for a larger floor, say what it costs and let them
decide. Do not propose one. A floor they enlarge is still the floor:
every later step — the lock in Step 2, the wiring in Step 3, `verify`,
`uninstall` and `unadopt` — reads the list the lock actually carries,
in floor order, never a fixed count.

## Step 2 — Write the floor lock

The floor from Step 1 is recorded in `.apache-magpie.lock`, committed
at the repo root. This is the project's adoption record, and it is
harness-neutral: write it on **every** client, including the ones that
cannot express the derived wiring in Step 3.

```text
# .apache-magpie.lock — committed; the project's floor.

method:       marketplace
url:          apache/magpie
min_version:  0.3.0

plugins:
  - magpie-setup
  - magpie-utilities
  - magpie-agent-guard
```

- **`min_version` is the Magpie version installed on this machine right
  now** — the version the maintainer is actually validating against.
  Read it from `claude plugin list --json`, or from the running agent's
  equivalent. Record it **verbatim**: a `.devNNNN` build adopted
  mid-cycle is written as it stands, not rounded up or down to a
  release. [`locks.md`](locks.md#method-marketplace--the-adoption-floor)
  explains why PEP 440 makes that correct.
- **`plugins` is the floor from Step 1**, in floor order, and nothing
  else. A family the maintainer happens to have installed does not
  enter the floor because it is installed — only because they asked for
  it in Step 1.
- **`url` is `apache/magpie`.** See
  [`locks.md`](locks.md#url-is-a-security-boundary) — a floor naming
  any other marketplace loses the pre-flight's automatic behaviour, so
  do not write one unless the user has a reason and knows the cost.

**If a lock already exists**, this is a re-adoption. Show the diff
between the existing floor and the one Step 1 produced, and let the
maintainer confirm. Never lower `min_version`: if the existing floor is
*higher* than the installed version, keep the existing value and say
so — a floor going backwards would silently withdraw a requirement the
project already made.

`git add` the lock. **Never commit** — the floor lands through the
project's normal review process, like any other committed file.

## Step 3 — Write the derived wiring

`.claude/settings.json` is **derived from the lock in Step 2**, not
authored here: `extraKnownMarketplaces` names `url`, and
`enabledPlugins` contains `plugins`, each as `<plugin>@apache-magpie`.
The lock is the source of truth; this file is how Claude Code acts on
it.

**On Claude Code, let the client write it.** `--scope project` is the
scope whose store *is* this file, so the install commands do the whole
of this step:

```bash
claude plugin marketplace add apache/magpie --scope project
claude plugin install <plugin>@apache-magpie --scope project
```

— the second once per plugin in the floor. That is why
[`install.md`](install.md#step-m4--install-what-the-user-picked)
refuses the flag and sends people here: run alone it hands a project
the plugin list with no floor beside it, and no `.apache-magpie.lock`
to say what the list was derived from.

Run the commands, then read the result against the **merge rules**
below before staging. Those rules are the contract however the file
got written: the CLI is not Magpie's code, and a settings file it
changed in a way they forbid is a finding rather than a fait accompli.
Where the CLI is absent, or its result breaks a rule, write the file
yourself to the same rules.

**Write the marketplace entry untagged** — `"repo": "apache/magpie"`,
with no `@version`. The floor is a minimum, and tagging the marketplace
would convert it into a ceiling that stops contributors receiving any
later release.

On a client that cannot express this — Codex can only default-install
all ten families, Gemini has no workspace-extension mechanism — skip
this step and say so. The lock from Step 2 still stands and is still
the project's record; what is missing is only the automatic wiring.

Show the maintainer the exact diff — the one you intend to write, or
the one the CLI just made — before anything is staged. **`git add` it.
Never commit** — the change lands through the project's normal review
process, like any other committed file.

### Merge rules

`.claude/settings.json` is not Magpie's file. This repository's own
carries `sandbox` and `permissions` blocks; an adopter's will carry
whatever they put there.

- **Touch only two keys** — `extraKnownMarketplaces` and
  `enabledPlugins`. Every other top-level key is preserved exactly as
  it was.
- **Leave an existing `apache-magpie` marketplace definition alone.**
  An adopter pinning `apache/magpie@0.2.0` has made a deliberate
  choice; do not rewrite it to track `main`.
- **Add whichever of the floor's entries are missing from an existing
  `enabledPlugins`, and remove nothing** — not other Magpie plugins,
  not other vendors' plugins. The floor's entries are the lock's
  `plugins` list, in floor order, each as `<plugin>@apache-magpie`.
  That list is **seeded** with `magpie-setup@apache-magpie`,
  `magpie-utilities@apache-magpie`, `magpie-agent-guard@apache-magpie`
  — a project whose maintainers enlarged it in Step 1 has more, and
  the lock is what you read, never a fixed count.
- **If the file does not exist**, create it with exactly those two
  keys: `extraKnownMarketplaces` defining `apache-magpie`, and
  `enabledPlugins` containing the floor.
- **If the file exists but does not parse as JSON, stop and say so.**
  Do not rewrite a file you cannot read; a malformed settings file is
  the user's to fix. Nothing was written — stop without staging.

## Step 4 — The project's configuration store

`.apache-magpie-overrides/` is the committed half of the lookup chain
in [`docs/setup/agentic-overrides.md`](../../../../docs/setup/agentic-overrides.md).
There are two ways to fill it, and the maintainer may well need both
in one run.

### 4a — Promote what is already configured locally

Look for `.apache-magpie-local/`. Anything a maintainer configured for
themselves with [`config`](config.md) is, by definition, a set of
answers that already works on this project — which makes it the best
starting point for what the project should publish.

If the directory holds configuration files:

1. **List them, and say what each would become.** Promoting is
   publishing: a value that was private to one clone becomes a fact
   every contributor reads. Name any that look personal rather than
   project-wide — a local clone path, a personal mail address — and
   recommend leaving those behind.
2. **Ask which to promote.** One structured multi-select, everything
   pre-ticked *except* what step 1 flagged.
3. **Copy** each selected file into `.apache-magpie-overrides/`.
   If a file of that name is already committed and differs, show the
   difference and ask before overwriting — you are editing something
   the project already decided.
4. **Drop the redundant local copies.** After copying, remove every
   local file that is now **byte-identical** to its committed twin.
   They would otherwise shadow it forever under the local-wins rule,
   so that the project's later corrections would never reach the
   maintainer who adopted it.
5. **Name what still differs.** Any local file left behind — because
   it was not promoted, or because it differs from what was committed
   — is reported, by path, with one line saying it still shadows the
   project's copy for this clone only. That is a legitimate end state;
   it is just never a silent one.

Never delete a local file that differs, and never delete one the user
declined to promote. The rule is: redundant copies go, deliberate ones
stay and are named.

### 4b — Scaffold whatever is still missing

For the required configuration no skill can find in either directory,
scaffold from `<snapshot-dir>/projects/_template/` exactly as
[`install.md` Step 9](install.md#step-9--scaffold-apache-magpie-overrides-fresh-only)
does — same exclusions, same `project.md` pre-population, same
auto-detect-before-asking discipline `config` uses.

A maintainer who knows they are adopting can arrive here directly,
without having run `config` first; this step is what makes that work.

`git add` the store; do not commit.

### 4c — Review the project's existing process

Configuration says what the project *is*. This step asks a different
question: where does the project already do something **differently**
from the framework's defaults, and should that difference be written
down as an override rather than discovered later by a contributor
whose PR got triaged against a rule the project does not follow?

**Scope: families new to the floor.** This step reviews only the
families that Step 1 added to the floor on *this* run:

- **First adoption** — every family in the floor.
- **Re-adoption** — only the families Step 2's floor diff *adds*. A
  family reviewed on an earlier run is not re-reviewed, including one
  whose deviations the maintainer rejected: rejecting is a decision,
  and re-asking would relitigate it.
- **No families added** — say so in one line and go to Step 5. Do not
  read anything.

There is no state file for this. `.apache-magpie.lock`'s `plugins:`
list is the record of what has been reviewed, and Step 2 has already
computed the diff.

#### 4c-i — Find the documents, then confirm them

Glob for the places a project's process is usually written:

```text
CONTRIBUTING*        GOVERNANCE*        MAINTAINERS*
docs/process/*       docs/contributing/*
.github/PULL_REQUEST_TEMPLATE*          .github/ISSUE_TEMPLATE/*
README*
```

**List what was found and let the maintainer correct the list** — one
structured multi-select, everything pre-ticked, plus the option to add
a path the glob missed. Projects keep this material in places no glob
predicts: a wiki export, `docs/dev/`, a `RELEASE_POLICY.md`.

Read **only** the confirmed set. If the maintainer confirms an empty
set — no such documents, or none worth reading — say the step is
skipped and go to Step 5.

#### 4c-ii — Compare against the new families' defaults only

For each family from the scope above, compare the confirmed documents
against the defaults of **that family's** skills. Nothing else. A
project adopting `magpie-pr-management` and `magpie-issue` is never
asked about release policy, because it did not adopt the release
family and will never run those skills.

#### 4c-iii — Propose one deviation at a time

For each candidate, show three things and nothing more:

1. **The evidence** — `<path>:<line>` and the sentence, quoted.
2. **The framework default it contradicts** — named skill, named
   behaviour.
3. **The override that would be written** — the actual text.

Then: **accept** / **edit** / **reject** / **skip the rest**.

**No evidence, no proposal.** A deviation must quote a line from a
confirmed document. Something that is merely plausible for a project
of this kind — "most Apache projects require two approvals" — is not a
deviation, it is a guess, and a guess written into an override store
becomes a rule the project never agreed to. If the documents do not
say it, do not raise it.

**Drop anything that would weaken a gate.** A document sentence that
would, as an override, weaken a confirmation gate or the safety,
confidentiality or privacy baseline is **not** proposed. Name it, say
which baseline it would have crossed, and move on. This is the
[hard rule](../../../../docs/setup/agentic-overrides.md#hard-rules)
every override surface already carries; this step is the first one that
*generates* override content, so it states the rule rather than
inheriting it silently.

#### 4c-iv — Write the accepted ones

Each accepted deviation becomes an override file at
`.apache-magpie-overrides/<framework-skill>.md`, in the forms the
contract allows — skip a step, replace a step, add a step, pre-empt a
decision-table row. It must also say *why*, citing the document it came
from, exactly as
[`docs/setup/agentic-overrides.md`](../../../../docs/setup/agentic-overrides.md#what-an-override-file-should-explain)
requires: an override whose reason is "adopt proposed it" is
unmaintainable the moment the project's policy changes.

If a file for that skill is already committed and differs, show the
difference and ask before overwriting — you are editing something the
project already decided, the same rule as
[4a](#4a--promote-what-is-already-configured-locally) step 3.

`git add` each file. **Never commit** — these land through the
project's normal review process like every other file this sub-action
writes. Never write to `.apache-magpie-local/` here: a deviation read
out of a committed document is the project's, not this maintainer's.

### `.gitignore`

Add `/.apache-magpie-local/` to the adopter repo's `.gitignore` if it
is not there, and stage it. `adopt` is already writing committed
files, so this is the sub-action that may do it — `config`
deliberately does not, and uses `.git/info/exclude` instead.

### 4d — Write the reconciliation stamp

**Scope: every skill the committed configuration now covers**, resolved
the same way [`reconcile.md`'s sweep](reconcile.md#the-sweep) enumerates
scope — a skill named by a file under `.apache-magpie-overrides/` (a
config file matching one of that skill's `requires_config:` entries, from
4a/4b, or an override file named `<skill>.md`, from 4c). Nothing this run
did not just configure or override enters the stamp.

For each skill in scope, write its current `surface_hash` into the lock's
`reconciled.skills` map, alongside `version` (the `min_version` Step 2
already wrote — the same "what version is this validated against"
question, answered once) and `at` (today). See
[`locks.md`](locks.md#the-reconciled-block--what-was-checked-not-what-to-install)
for the block's shape.

This is the **one path where the stamp enters git.** Everywhere else in
this framework the stamp is a gitignored, per-machine record; here it
rides along inside the same commit the maintainer is already making
deliberately for the floor and the configuration store — not a separate
decision, and not something this sub-action asks about again. `git add`
the lock — Step 2 already staged it for the floor, so this updates the
same staged file rather than opening a new one. **Never commit.**

Nothing configured or overridden this run (4a, 4b, and 4c all found
nothing to do) → leave the `reconciled:` block exactly as it was. A
re-adoption run that changes only the floor, with no configuration
change, stamps nothing new.

## Step 5 — Recap

Tell the user, in this order:

1. **What is staged** — the paths (the lock — including its
   reconciliation stamp entries from 4d, the derived wiring, the
   configuration store, and `.gitignore` if it changed), and that
   nothing is committed.
1b. **What was promoted and what was dropped** — which local files
   became the project's, which redundant local copies were removed,
   and which local files remain and still shadow a committed one for
   this clone.
1c. **What the process review found** — the override files written and
   the family each came from; the documents read that yielded nothing,
   by path, so a maintainer expecting a deviation from one of them
   knows it was read and not skipped; and any candidate dropped for
   weakening a gate, with the baseline it would have crossed. If the
   step was out of scope — no families added — say that instead, in
   one line.
2. **What the floor means** — a minimum, not a pin. Contributors on a
   newer Magpie are fine and will be told nothing; contributors behind
   it are brought up to it by the pre-flight in any skill they run.
   Nothing is ever downgraded or removed.
3. **What a contributor will get on clone** — the floor plugins the lock
   names, enabled after they trust the repo; no install step for them.
4. **What this does not do** — it does not limit what anyone may
   install for themselves, and it does not install anything for the
   maintainer running it.
5. **Keeping it honest** — an override everyone would want is a
   missing framework feature; `setup:override-upstream <skill>` walks
   it into a PR against `apache/magpie`, after which the local
   override can go.

## Unadopt

`setup unadopt` withdraws the recommendation:

- remove `.apache-magpie.lock`, the committed floor itself. The project
  is withdrawing its recommendation, not only the wiring derived from
  it — leaving the lock in place would mean every contributor's
  pre-flight kept enforcing a floor the project no longer wants.
- remove the `apache-magpie` entry from `extraKnownMarketplaces` and
  the floor entries from `enabledPlugins` — the wiring derived from
  that lock. Read the entries off the lock's `plugins` list before you
  delete it, in floor order, each as `<plugin>@apache-magpie`: a floor
  a maintainer enlarged carries more than the seeded
  `magpie-setup@apache-magpie`, `magpie-utilities@apache-magpie`,
  `magpie-agent-guard@apache-magpie`, and leaving one behind would
  commit a plugin entry whose marketplace definition you just removed.
  **Leave every other key and every other plugin exactly as they are.**
  If that empties a key, remove the empty key rather than leaving `{}`.
- preserve `.apache-magpie-overrides/` unless `--purge-overrides` is
  passed.

**Leave every install alone** — the user's own, and everyone else's.
Un-adopting is the repo withdrawing a recommendation; it uninstalls
nothing. Removing the *install* is
[`uninstall.md`](uninstall.md), a different operation with a
different blast radius: `uninstall` leaves `.apache-magpie.lock` in
place; only `unadopt` removes it. Say which one you did.

Stage, never commit. Show the diff first.

## If the user meant "install"

Before 0.2.0, `adopt` was an alias of `install`. Someone typing it
from memory or from an old runbook probably wants the install.

If the repo has no Magpie install at all, say plainly that `adopt`
now means something else — it commits a recommendation for every
contributor — and offer `setup install` instead. **Do not silently do
either one.** Ask which they meant.
