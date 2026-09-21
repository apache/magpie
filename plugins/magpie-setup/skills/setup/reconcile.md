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
skill's own hash check finds neither the committed lock nor the local
file naming that skill at all — no baseline to diff a single skill
against, so the fix is a project-wide pass rather than a per-skill one.
It is also runnable directly, any time, as a health check on the
project's configuration surface.

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
3. **A `skills` entry for the same skill in both stores is drift, not a
   configuration this framework ever writes.** If you find one while
   reading (step 0 or step 1 of the sweep below), the local entry wins
   for every comparison this run makes, and the run reports the
   collision in its summary as drift the operator should clean up (drop
   the stale committed entry, or the redundant local one, by hand).
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

1. **Enumerate the scope.** Every skill named by a file under
   `.apache-magpie-local/` or `.apache-magpie-overrides/` (a
   configuration file matching one of that skill's `requires_config:`
   entries, or an override file named `<skill>.md`) is in scope. This
   is deliberately **not** every skill the framework ships — a handful,
   the ones this project actually touches.

2. **Anchor resolution.** For every override file
   (`.apache-magpie-overrides/<skill>.md` or
   `.apache-magpie-local/<skill>.md`), read the target skill's
   `SKILL.md` and confirm every structural anchor the override
   references — a step heading, a golden-rule name — still exists,
   markdown-decoration-stripped, the same way
   [`tools/dev/skill-surface-hash.py`](../../../../tools/dev/skill-surface-hash.py)
   defines an anchor. A moved or renamed anchor is a finding:
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
   skill's anchors (check 2) needs that skill's `SKILL.md`. On a
   pinned-snapshot install it sits inside the project tree at
   `.apache-magpie/skills/<name>/SKILL.md` and is readable under the
   sandbox like any other project file. On a **marketplace** install it
   sits in the agent's plugin cache
   (`~/.claude/plugins/cache/apache-magpie/<plugin>/<version>/skills/<name>/`),
   which the sandbox denies reads on. When a skill's `SKILL.md` cannot
   be read, do **not** report that skill's anchors as clean — name it
   in an `unchecked` list instead, and say plainly that anchor
   resolution could not be performed for those skills here, and that
   `/magpie-setup reconcile` run outside the sandbox is how to finish
   the check for them. Check 3 (`requires_config` resolution) needs
   only files already in the repository, so it always completes, sandbox
   or not. A partial answer with its limits stated beats a clean report
   this session did not actually produce.

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
  to act on any finding this run — write
  `acknowledged.sweep: <installed plugin version>` to the local file
  and change nothing else. This suppresses the pre-flight's project-wide
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
    the local entry wins; drop one by hand

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
