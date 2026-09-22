<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/legal/release-policy.html -->

# reconcile — the one-time project-wide reconciliation sweep

Walks every skill this project actually configures or overrides,
checks whether its configuration surface still resolves, and writes
the `reconciled:` stamp — the fingerprint the shared pre-flight block
([`tools/dev/preflight-block.md`](../../../../tools/dev/preflight-block.md)
step 4) compares against on every skill invocation afterwards. See
[`locks.md`](locks.md#the-reconciled-block--what-was-checked-not-what-to-install)
for the stamp's format and
[`docs/designs/2026-09-21-marketplace-reconciliation-tracking.md`](../../../../docs/designs/2026-09-21-marketplace-reconciliation-tracking.md)
for the design this sub-action implements.

**Scope: every adopted or configured project, any install method.** A
marketplace floor and a pinned snapshot both carry a `reconciled:`
stamp; this sub-action reconciles either. It is not the same walk as
[`upgrade`](upgrade.md)'s override reconciliation — that one runs only
on the pinned-snapshot path, triggered by a snapshot refresh. This one
runs on demand, on any method, and needs no snapshot refresh to
justify it.

**This is the sub-action the shared pre-flight block names** when a
skill's own hash check finds no `reconciled:` block in either store at
all — nothing in this project has ever been reconciled, so the fix is a
project-wide pass rather than a per-skill one. A block that exists but
does not name the running skill is *not* that case: the pre-flight stays
silent there, because a project that does not configure a skill has
nothing to reconcile for it. This sub-action is also runnable directly,
any time, as a health check on the project's configuration surface.

**Nothing to reconcile is a valid, silent outcome.** No
`.apache-magpie.lock`, no `.apache-magpie-local/`, and no
`.apache-magpie-overrides/` means the project has never configured or
adopted anything — there is no configuration surface that could have
gone stale. Say so in one line and stop; do not scaffold anything, and
do not treat the absence as a finding.

## Inputs

| Flag | Effect |
|---|---|
| `dry-run` | Report every finding without applying any re-anchor, config fix, or stamp write. |

## Step 0 — Pre-flight

1. **Gate on nothing-configured.** Check for `.apache-magpie.lock`,
   `.apache-magpie-local/`, and `.apache-magpie-overrides/`. All three
   absent → say there is nothing to reconcile and stop. Otherwise
   continue.
2. **Decide which store the stamp belongs in**, per
   [`locks.md`](locks.md#the-reconciled-block--what-was-checked-not-what-to-install):
   - `.apache-magpie.lock` exists (adopted, any method) → the stamp's
     `version`/`at`/`skills` block lives **in the committed lock**,
     beside the floor it already records.
   - No committed lock, but `.apache-magpie-local/` or
     `.apache-magpie-overrides/` exists (configured but not adopted) →
     the identical block lives in `.apache-magpie-local/reconciled.json`,
     a **flat JSON object** — never wrapped in a `reconciled:` key, the
     filename already says what it is.

   `verified_at`, `verify_suggested_at`, and `acknowledged` always live
   in `.apache-magpie-local/reconciled.json`, on every project
   regardless of adoption state — never in the committed lock, even
   when adopted. Read that file now if it exists; you will write to it
   either way.
3. **If you find one while reading** (step 0 or step 1 of the sweep
   below):

   <!-- BEGIN MAGPIE BLOCK: both-stores-collision — generated from tools/dev/blocks/both-stores-collision.md -->

   A `skills` entry for the same skill in both stores is an expected
   transitional state, not a fault. It is what the ordinary
   config-then-adopt path produces across two machines: a contributor
   runs `config` on their machine before the project adopts, a
   maintainer runs `adopt` on a different machine, and `adopt` can only
   migrate the local stamp it can see — so the contributor's local
   entry survives beside the newly committed one. When it happens, the
   local entry wins for every comparison, and `/magpie-setup reconcile`
   names the collision and offers to drop the redundant local entries,
   leaving the committed lock as the single store.

   <!-- END MAGPIE BLOCK: both-stores-collision -->

   That offer is one confirmation like any other finding in Step 2 —
   declining it changes nothing, and the collision stays reported.
4. **Main-checkout only when the target is the committed lock.**
   Writing to `.apache-magpie.lock` is a committed-file write, the same
   restriction [`adopt`](adopt.md) carries and for the same reason.
   Compare `git rev-parse --git-dir` against
   `git rev-parse --git-common-dir`; if they differ (a worktree) and the
   target from step 2 is the committed lock, stop and name the main
   checkout to run from instead. When the target is the local file
   instead, there is no such restriction — run from anywhere.

## The sweep

**The sweep validates the present, not a delta.** With no stamp — or no
entry for a given skill in whichever stamp exists — there is nothing to
diff against. That costs the *report* some precision, not the check:
two questions are answerable from the current tree alone, with no
baseline required.

1. **Enumerate the scope.** A skill is in scope when an **override
   file names it** (`.apache-magpie-overrides/<skill>.md` or
   `.apache-magpie-local/<skill>.md`), **or** when one of its
   `requires_config:` entries **resolves** from `.apache-magpie-local/`
   or `.apache-magpie-overrides/`. A project that supplies a skill's
   configuration has configured that skill, whether or not it also
   overrides it — so take the broad reading rather than trying to
   guess which skills the project "meant". This is still **not** every
   skill the framework ships; how many it is depends entirely on how
   much the project configures, which is two for a project with a
   single override and most of the catalogue for one that commits a
   widely-read `project.md`.

2. **Anchor resolution.** For every override file
   (`.apache-magpie-overrides/<skill>.md` or
   `.apache-magpie-local/<skill>.md`), read the target skill's
   `SKILL.md` **and every sibling `*.md` detail file directly inside
   that skill's directory** (a multi-file skill such as `setup` or
   `pr-management-triage` keeps steps and golden rules in those detail
   files, not only in `SKILL.md`) and confirm every structural anchor
   the override references — a step heading, a golden-rule name — still
   exists somewhere in that set, markdown-decoration-stripped, the same
   way
   [`tools/dev/skill-surface-hash.py`](../../../../tools/dev/skill-surface-hash.py)
   defines an anchor and resolves it across the skill's directory, not
   just `SKILL.md`. An override anchored to a detail-file heading that
   resolves only against `SKILL.md` would read as broken when it is not
   — check the whole directory before reporting a finding. A moved or
   renamed anchor is a finding:
   *"`<override file>` anchors to `<old heading text>`, which is now
   `<new heading text>`"* — name the override file and the heading that
   moved, the same shape
   [`upgrade.md` Step 5](upgrade.md#step-5--reconcile-overrides) surfaces.

3. **`requires_config` resolution.** For every skill in scope, resolve
   each `requires_config:` entry through the lookup chain
   (`.apache-magpie-local/<file>` then `.apache-magpie-overrides/<file>`,
   [`agentic-overrides.md`](../../../../docs/setup/agentic-overrides.md)).
   An entry that resolves through neither is a finding: *"`<skill
   name>` requires `<file>`, which is not configured"* — propose
   `/magpie-setup config <skill>` for it.

4. **Sandboxed sessions cover what they can reach.** Resolving a
   skill's anchors (check 2) needs that skill's `SKILL.md` **and its
   sibling detail files**. On a pinned-snapshot install they sit inside
   the project tree at `.apache-magpie/skills/<name>/` and are readable
   under the sandbox like any other project file. On a **marketplace**
   install they sit in the agent's plugin cache
   (`~/.claude/plugins/cache/apache-magpie/<plugin>/<version>/skills/<name>/`),
   which the sandbox denies reads on. When a skill's `SKILL.md` or any
   of its detail files cannot be read, do **not** report that skill's
   anchors as clean — name it in an `unchecked` list instead, and say
   plainly that anchor resolution could not be performed for those
   skills here, and that `/magpie-setup reconcile` run outside the
   sandbox is how to finish the check for them. Check 3
   (`requires_config` resolution) needs only files already in the
   repository, so it always completes, sandbox or not. A partial answer
   with its limits stated beats a clean report this session did not
   actually produce.

5. **The baseline is a best guess, used only for wording, never for the
   pass/fail of a check.** In order: the lock's `min_version`; else the
   date of the last commit touching `.apache-magpie.lock` or
   `.apache-magpie-overrides/`, mapped to a framework version through
   the marketplace clone's own git history (or, on a snapshot install,
   the local git history of `<snapshot-dir>`); else the mtimes of files
   under `.apache-magpie-local/`; else nothing, and the report says so
   rather than inventing a number. Phrase whatever is found as an
   estimate — *"your configuration looks like it was written around
   0.1.x"* — never as a fact; the two checks above do not depend on it
   either way.

## Step 1 — Present the findings

List every finding from checks 2–3 as a numbered proposal, one item per
override or `requires_config` gap:

```text
1. .apache-magpie-overrides/issue-triage.md anchors to
   "Step 3 — Classify the disposition", renamed to
   "Step 3 — Read the report and classify" in magpie-security-issue-triage.
   → re-anchor the override to the new heading.
2. magpie-pr-management-code-review requires reviewer-routing.md,
   which is not configured.
   → /magpie-setup config pr-management-code-review
```

No findings → say so plainly (*"every configured skill's anchors and
`requires_config` entries resolve"*), name any `unchecked` skills from
check 4, and go straight to Step 2 with nothing to confirm — writing
the stamp needs no confirmation when nothing is changing.

## Step 2 — Confirm, apply, and write the stamp

Findings present themselves for confirmation **item by item**, the same
protocol `upgrade.md` Step 5 uses for override conflicts — the skill
does not auto-rewrite an override's anchor; re-anchoring is the
maintainer's judgement call, not pattern-matching. A `requires_config`
gap can be closed mechanically by chaining into
`/magpie-setup config <skill>`; offer it per item.

Both `acknowledged` writes below fire **on decline**, not on show — unlike
the pre-flight block's own per-skill check
([`tools/dev/preflight-block.md`](../../../../tools/dev/preflight-block.md)
step 4), which never blocks for an answer and so has no decline event to
hook, only a show. This flow blocks for a real item-by-item and
whole-sweep confirmation, so a decline here is a real event; a sweep the
operator abandons mid-flow deliberately leaves nothing recorded, so the
proposal correctly returns on the next run instead of being silently
suppressed by a write that never happened.

- **Confirmed and applied** — the skill's configuration now resolves
  cleanly. Its entry in the stamp's `skills:` map is written (or
  refreshed) with its **current** `surface_hash`.
- **Declined** — nothing about the project changes. Write
  `acknowledged.skills["<skill name>"]: <current surface_hash>` to the
  local file so the per-skill pre-flight does not re-propose the exact
  same finding on this skill's next invocation; the skill's entry is
  **not** added to the stamp's `skills:` map, because it is not
  actually reconciled — only shown and set aside.
- **A skill named only in `unchecked`** (sandboxed run, check 4) — no
  entry is written either way; it is neither confirmed clean nor
  declined, just unverified this run.
- **A both-stores collision** (Step 0.3) — confirming drops that
  skill's redundant `skills` entry from
  `.apache-magpie-local/reconciled.json`, leaving the committed lock
  as the single store and the three always-local keys untouched.
  Declining leaves both entries in place; the local one keeps winning
  and the collision is reported again next run.

Once every finding has been confirmed, applied, or declined:

- If **dry-run** was passed, stop here — report what would have been
  written, write nothing.
- Otherwise write `version` (the framework version — or, on a
  marketplace install, the installed plugin version — this run
  actually checked against) and `at` (today) into the target store
  chosen in Step 0, alongside the `skills:` map built above. If the
  target is the committed lock, stage it (`git add`) and say the change
  lands through the project's normal review like any other committed
  file; do not commit on the operator's behalf.
- If the whole sweep was declined outright — the operator does not want
  to act on any finding this run — write `acknowledged.sweep:
  <version>` to the local file and change nothing else, where
  `<version>` is the installed plugin version on a marketplace install
  and the framework version otherwise: the same value this run wrote,
  or would have written, as the stamp's own `version`. This
  suppresses the pre-flight's project-wide
  sweep proposal until that version changes, per
  [`agentic-overrides.md` → Reconciliation on framework upgrade](../../../../docs/setup/agentic-overrides.md#reconciliation-on-framework-upgrade);
  it does not suppress the per-skill checks for skills whose findings
  were individually declined (those are covered by
  `acknowledged.skills` above instead).

## Output to the user

```text
Reconciliation sweep

Scope:      <N> configured skill(s), <M> override file(s)
Baseline:   <estimate, or "unknown">    (wording only — not load-bearing)

Anchor resolution:
  ✓ <override files whose anchors still resolve>
  ⚠ <override file>  →  <old heading> renamed to <new heading>
  ? <skills whose SKILL.md could not be read here — see Unchecked below>

requires_config resolution:
  ✓ <skills whose required files all resolve>
  ⚠ <skill>  needs <file>, not configured  →  /magpie-setup config <skill>

Both-stores collision:
  ✓ none found   OR
  ⚠ <skill> named in both the committed lock and the local file —
    expected after config-then-adopt across two machines; the local
    entry wins  →  drop the redundant local entry? [confirm]

Unchecked (sandboxed session — plugin cache not readable):
  - <none>   OR
  - <skill list>  →  re-run /magpie-setup reconcile outside the sandbox

Stamp:
  written to <.apache-magpie.lock | .apache-magpie-local/reconciled.json>
  version: <value>   at: <today>
  skills:  <N> entries   (<K> confirmed this run, <D> declined and
                          acknowledged, <U> left unchecked)
```

## Failure modes

- **Nothing configured or adopted** → not a failure; say so and stop
  (Step 0.1).
- **Committed-lock target from a worktree** → stop and name the main
  checkout (Step 0.4).
- **A skill's `SKILL.md` is unreadable for a reason other than the
  sandbox** (renamed skill, broken symlink, corrupted snapshot) →
  surface as a finding distinct from `unchecked` — this is the same
  "target skill no longer exists" case `upgrade.md` Step 5 already
  covers, not a sandbox limitation.
- **`dry-run` with findings present** → report only; nothing is
  written, including the stamp.
