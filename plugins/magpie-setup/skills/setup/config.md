<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# `setup config` — configure Magpie for yourself

Scaffold and fill the project configuration a skill needs, in
`.apache-magpie-local/` — gitignored, personal, nothing staged and
nothing committed.

**This is the sub-action an individual runs.** It works on a repository
whose maintainers have never heard of Magpie, it asks the project for
nothing, and no one else can see what it wrote. A contributor never has
to run `adopt` — which commits a recommendation for everybody — merely
to make a skill work for themselves.

`adopt` is the other half: it writes the committed floor and the
project-wide configuration, either scaffolded directly or **promoted
from what this sub-action produced**. See
[`adopt.md`](adopt.md).

## Inputs

| Input | Default |
|---|---|
| `<skills>` | The families installed on this machine. `config <skill>` narrows it to one. |
| `<repo-root>` | The git repository the session is in. |

## Invoked by a skill's pre-flight

This is the common entry point, and it is **automatic**: a skill whose
required configuration does not resolve runs this sub-action, says it is
doing so, and then carries on with what the user actually asked for.

That is allowed unasked because of what this touches — only
`.apache-magpie-local/` and `.git/info/exclude`, both gitignored, both
invisible to every other person and every other clone, both undone by
deleting a directory. Nothing is staged, nothing is committed.

When entered this way:

- **Scope to the one skill** that stopped, not to every installed
  family. The user asked to triage a queue, not to sit an interview.
- **Ask once, for everything.** One batched question covering every
  value that could not be derived, then done.
- **Hand control back.** Say what was written, and let the invoking
  skill continue in the same turn. No restart is needed: these are
  files, written and read in the same session.
- **Mention adoption in one line, once** — that the project can adopt
  Magpie so contributors get this on clone, and the command that does
  it. Then drop it. Never run `adopt`, never ask whether to, and never
  raise it again on a later invocation.

## Step 0 — Pre-flight

1. **In a git repository?** If not, stop: there is no project to
   configure. Say so plainly.
2. **Is the repo already adopted?** Read `<committed-lock>`. If it
   exists, say so and name what changes: the project already publishes
   configuration, so anything written here **shadows it, per file**.
   That is legitimate — it is how you hold one value of your own — but
   it is a decision, not a default. Offer to configure only the files
   the project has *not* committed, and make that the default choice.
3. **Which skills.** Resolve `<skills>` to the set whose configuration
   is in scope.

## Step 1 — Work out what is actually needed

For each skill in scope, read its `requires_config:` frontmatter. That
is the declared **required** set — the files without which the skill
would act on a guess. Everything else it reads is optional and
degrades; do not ask about optional files unless the user asked for a
specific one by name.

Resolve each required file through the lookup chain
([`docs/setup/agentic-overrides.md`](../../../../docs/setup/agentic-overrides.md)):
already present locally, already committed by the project, or missing.
**Only the missing ones are work.**

Report the three groups before writing anything. A user who runs this
on a well-configured repo should be told "nothing to do" rather than
walked through an interview.

## Step 2 — Make the directory invisible to git

`.apache-magpie-local/` must not be committable, and this sub-action
must not edit a committed file to arrange that.

1. If `<repo-root>/.gitignore` already excludes `/.apache-magpie-local/`
   — which `install` and `adopt` both arrange — nothing to do.
2. Otherwise write `/.apache-magpie-local/` to
   **`<repo-root>/.git/info/exclude`**, creating the file if needed and
   appending if it exists. That file is per-clone and is never
   committed, pushed, or seen by anyone else.

**Do not add a `.gitignore` line here.** `.gitignore` is a committed
file; a sub-action whose whole promise is that it writes nothing anyone
else will see must not open by editing one. `adopt` adds it, because
`adopt` is already committing.

Say which of the two happened.

## Step 2a — Install the pre-flight checker

Copy the framework's `tools/setup-preflight/src/setup_preflight/`
package into `.apache-magpie-local/setup_preflight/`, replacing any copy
already there. Source it from `<snapshot-dir>/tools/setup-preflight/` on
a snapshot install, or from the installed plugin's copy on a marketplace
install — the same two places Step 3 takes its templates from.

This is what every skill's pre-flight actually runs:

```bash
PYTHONPATH=.apache-magpie-local python3 -m setup_preflight --skill … --hash …
```

It has to be copied rather than referenced. Under the sandbox the
framework recommends, `~/.claude/plugins/cache/` is read-denied, so a
module left in the plugin can be read by the agent's file tool but never
*executed* by a shell — and a sandboxed marketplace install is exactly
the case the check exists for. `.apache-magpie-local/` is gitignored
(Step 2), so nothing here reaches another clone.

**Name it when you report.** This sub-action may run unattended from a
skill's pre-flight, and its licence to do so rests on touching only
gitignored paths. Copying an executable is still within that promise —
it is framework code of the same provenance as the plugin already
installed, and it goes away with the directory — but it is a step beyond
writing configuration files, so it is said out loud rather than done
quietly.

Verify the copy answers before moving on; a checker that does not run
makes every skill fall back to *step-0* of its `preflight-detail.md`:

```bash
PYTHONPATH=.apache-magpie-local python3 -m setup_preflight --skill magpie-setup
```

## Step 3 — Scaffold and fill

For each missing required file, in the order the skills need them
(`project.md` first — most others reference values it carries):

1. **Copy the template** from `<snapshot-dir>/projects/_template/<file>`,
   or from the installed plugin's copy on a marketplace install, into
   `.apache-magpie-local/<file>`.
2. **Auto-detect first.** Read what the repository already reveals
   before asking anything: the `origin` remote for `upstream_repo`, the
   label taxonomy, existing milestones, the CI checks that actually
   run, and the `<committed-lock>` if the project is adopted. Fill every
   value you can derive and say which ones you derived, so the user can
   correct a wrong guess rather than hunt for it later.
3. **Batch the rest into one question.** Prefer the harness's
   structured-question tool. One question covering every remaining
   `TODO` across every file, grouped by file — not a per-field
   interrogation, and not one question per skill.
4. **Leave what the user skips.** A `TODO` left in place is not an
   error: the skill that needs it names it when it needs it, and the
   skills that do not need it never look. Say that, so a half-filled
   file does not read as a failed run.

Never write outside `.apache-magpie-local/`. Never stage anything.
Never commit.

## Step 3b — Record what this run reconciled

For every skill in scope (Step 1) whose `requires_config:` set now fully
resolves, record that fact, keyed by that skill's frontmatter `name:`
(e.g. `code-review`). **Everything this step writes
stays inside `.apache-magpie-local/reconciled.json` — never the
committed lock, adopted project or not.** The two branches below trigger
on **different** conditions — read the "not adopted" one's scope as
looser than the "already adopted" one's; they are not the same rule
applied to two stores.

- **Not adopted** (no `<committed-lock>`, per this skill's own [Step 0
  item 2](#step-0--pre-flight)) → write that skill's current
  `surface_hash`, today's date, and the version this run is running,
  into `reconciled.json`'s `skills` map (a flat JSON object, no
  `reconciled:` wrapper) — whether Step 3 just filled the last missing
  file for it, **or** it already resolved and this run touched nothing
  for it. Read the version from the running plugin's own base-directory
  path (`…/plugins/cache/apache-magpie/<plugin>/<version>/skills/<name>`)
  on a marketplace install — no CLI call needed, and it works inside the
  sandbox where `claude plugin list --json` returns `[]` — or from
  `<local-lock>`'s fetched version on a pinned snapshot. This is the same
  `version`/`at`/`skills` shape the committed block carries, and it
  becomes the committed one the moment the project is adopted — see
  [`adopt.md` 4d](adopt.md#4d--write-the-reconciliation-stamp), the only
  surface that migrates it there.
- **Already adopted** (`<committed-lock>` exists) → write **no**
  `version`, `at`, or `skills` entry anywhere, ever. The committed stamp
  is `adopt`'s, `reconcile`'s, and `upgrade`'s to write — never
  `config`'s, because staging into a committed file from an unattended
  pre-flight run is exactly what this sub-action must never do (see
  [Hard rule 1](#hard-rules)), and this skill's own
  [Step 0](#step-0--pre-flight) carries none of the main-checkout gate
  [`reconcile.md`'s Step 0](reconcile.md#step-0--pre-flight) requires
  before it touches that same file. **Only for a skill whose missing
  configuration this run actually wrote** — Step 3 produced the file
  that made its `requires_config:` set resolve for the first time this
  run — record the per-machine fact in the always-local key
  [`locks.md`](locks.md#the-reconciled-block--what-was-checked-not-what-to-install)
  already reserves for exactly this: `acknowledged.skills["<skill
  name>"] = <that skill's current surface_hash>`, in
  `.apache-magpie-local/reconciled.json`.

  **A skill that already resolved before this run, and that Step 3
  touched nothing for, gets no entry here at all.**
  `acknowledged.skills` is a generic gate in
  [`tools/dev/preflight-block.md`](../../../../tools/dev/preflight-block.md#pre-flight--is-this-project-set-up)
  step 4: it covers *both* a stale `requires_config` finding and a
  stale-anchor finding, without distinguishing which — and `config`
  only ever investigates (and fixes) the former. Writing the key for an
  untouched skill would silence a live anchor-drift finding on a skill
  this run never looked at and did no work for; the narrower trigger
  keeps the anti-nag benefit exactly where `config` actually did
  something. The entry it does write means the next invocation of this
  skill for this project does not re-propose the specific
  `requires_config` finding this run just resolved.

**Skip this step entirely when nothing has ever been configured or
adopted here** — no `<committed-lock>`, no `.apache-magpie-local/`, and
no `.apache-magpie-overrides/` anywhere in the repo, the same
nothing-to-reconcile gate
[`reconcile.md`](reconcile.md#step-0--pre-flight) uses. That is the only
case with nothing to *possibly* record. Once any one of the three
already exists, the **not-adopted** branch above records every skill in
scope regardless of whether this run touched it; the **already-adopted**
branch records only the skill(s) this run actually wrote a config file
for — nothing for the rest, per the narrower trigger above.

This is per-skill, not a project-wide sweep: only the skill(s) actually
in this run's scope are candidates, and — on an adopted project — only
the ones this run did work for actually get written. Existing entries
for other skills, in either store, are left exactly as they are —
[`reconcile.md`](reconcile.md) is the project-wide pass.

## Step 4 — Recap

Tell the user, in this order:

1. **What was written**, by path, and that all of it is gitignored and
   invisible to everyone else.
1b. **What the reconciliation stamp recorded** (Step 3b), all of it in
   the gitignored `.apache-magpie-local/reconciled.json` — on an
   unadopted project, the skill(s) whose `skills` entry was just
   written there, whether or not this run touched a file for them; on
   an already-adopted project, only the skill(s) whose missing
   configuration **this run actually wrote**, each recorded as an
   `acknowledged.skills` entry instead, and that the committed stamp is
   untouched — `adopt`, `reconcile`, or `upgrade` write that. A skill
   that was already fully configured before this run gets nothing here
   on an adopted project, even though it is in scope — say so plainly
   rather than letting silence read as an oversight. Say plainly, too,
   when nothing was recorded at all because this project has never
   configured or adopted anything (Step 3b's gate).
2. **What is still `TODO`**, by file, and which skill will ask for each
   one.
3. **What now works** — the skills whose required set is complete.
4. **What this did not do** — it wrote nothing committable, changed
   nothing for any teammate, and took no position on what the project
   should recommend.
5. **One line about adoption, as information.** That the project can
   adopt Magpie so every contributor gets this on clone, and that
   `/magpie-setup adopt` is how. State it; do not ask, do not offer to
   run it, and do not raise it again on a later invocation. Adoption is
   a decision the maintainers take together, and a prompt at the end of
   a configure run is not where that happens.

## When the user meant `adopt`

If the request was about the *project* rather than the person — "set
this up for the team", "commit the config", "make everyone get this" —
this is the wrong sub-action. Say so in one line and route to
[`adopt.md`](adopt.md) rather than writing a local copy nobody else
will see.

## Hard rules

1. **Nothing outside `.apache-magpie-local/` and
   `.git/info/exclude`.** No `.gitignore` edit, no `.claude/settings.json`
   edit, no lock file, no staging, no commit. This includes Step 3b's
   reconciliation stamp: even on an already-adopted project, it never
   touches the committed lock — only `.apache-magpie-local/reconciled.json`.
2. **Never fabricate a value.** A value you cannot derive is a question
   or a `TODO`, never a plausible-looking guess. A wrong `upstream_repo`
   sends a skill at the wrong repository.
3. **Never weaken the baseline.** Configuration supplies facts; it
   cannot disable a safety, confidentiality, or privacy rule. That is
   the same additive-only guardrail overrides carry.
4. **Say when shadowing.** Writing a local file the project has already
   committed is allowed and is sometimes exactly right — but it is
   always reported, at the time, with what the project's value was.
