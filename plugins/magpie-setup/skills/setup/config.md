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

## Step 4 — Recap

Tell the user, in this order:

1. **What was written**, by path, and that all of it is gitignored and
   invisible to everyone else.
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
   edit, no lock file, no staging, no commit.
2. **Never fabricate a value.** A value you cannot derive is a question
   or a `TODO`, never a plausible-looking guess. A wrong `upstream_repo`
   sends a skill at the wrong repository.
3. **Never weaken the baseline.** Configuration supplies facts; it
   cannot disable a safety, confidentiality, or privacy rule. That is
   the same additive-only guardrail overrides carry.
4. **Say when shadowing.** Writing a local file the project has already
   committed is allowed and is sometimes exactly right — but it is
   always reported, at the time, with what the project's value was.
