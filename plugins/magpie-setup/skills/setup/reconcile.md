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
[`update`](update.md)'s override reconciliation — that one runs only
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
`.apache-magpie.lock`, no personal layer, and no
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
   the personal layer, and `.apache-magpie-overrides/`. The personal
   layer is wherever `python3 -m setup_preflight.layers` says
   (`personal_layers`): `.apache-magpie-local/` when adopted — the main
   checkout's too, from a linked worktree — and
   `<git-common-dir>/apache-magpie/` (or a legacy in-tree
   `.apache-magpie-local/`) when not. All three
   absent → say there is nothing to reconcile and stop. Otherwise
   continue.
2. **Decide which store the stamp belongs in**, per
   [`locks.md`](locks.md#the-reconciled-block--what-was-checked-not-what-to-install):
   - `.apache-magpie.lock` exists (adopted, any method) → the stamp's
     `version`/`at`/`skills` block lives **in the committed lock**,
     beside the floor it already records — for the skills in
     **committed scope** (sweep step 1). A skill in scope **only through
     the personal layer** is stamped in the personal layer's
     `reconciled.json` `skills` map instead, never in the committed
     lock: the configuration it describes is one developer's, so
     committing it would record, for every contributor, a state only
     that developer has.
   - No committed lock, but the personal layer or
     `.apache-magpie-overrides/` exists (configured but not adopted) →
     the identical block lives in the personal layer's `reconciled.json`,
     a **flat JSON object** — never wrapped in a `reconciled:` key, the
     filename already says what it is.

   `verified_at`, `verify_suggested_at`, and `acknowledged` always live
   in the personal layer's `reconciled.json`, on every project
   regardless of adoption state — never in the committed lock, even
   when adopted. Read that file now if it exists; you will write to it
   either way.
3. **If you find one while reading** (step 0 or step 1 of the sweep
   below):

   <!-- BEGIN MAGPIE BLOCK: both-stores-collision — generated from tools/dev/blocks/both-stores-collision.md -->

   A `skills` entry for the same skill in both stores is an expected
   transitional state, not a fault — it needs no hand edit and no bug to
   produce. It is what the ordinary config-then-adopt path produces
   across two machines: a contributor
   runs `config` on their machine before the project adopts, a
   maintainer runs `adopt` on a different machine, and `adopt` can only
   migrate the local stamp it can see — so the contributor's local
   entry survives beside the newly committed one. When it happens, the
   local entry wins for every comparison, and `/magpie-setup:setup reconcile`
   names the collision and offers to drop the redundant local entries,
   leaving the committed lock as the single store.

   <!-- END MAGPIE BLOCK: both-stores-collision -->

   That offer is one confirmation like any other finding in Step 2 —
   declining it changes nothing, and the collision stays reported.
   A personal `skills` entry for a skill in **personal-only scope** is
   not a collision: that is where its stamp belongs. Offer to drop a
   personal entry only when the same skill is also in committed scope.
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

**An override file is named by the skill's override name, not its
`name:`.** `<override-name>` below is the filename the skill's own
*Adopter overrides* block names (`release-verify-rc` for `verify-rc`,
`security-issue-triage` for `issue-triage`), the same mapping
`setup_preflight.delegation.override_name()` applies. Looking for
`<name>.md` instead misses every prefixed override, so those skills
drop out of scope and their anchors are never checked. Both layers are
read: an override in the personal layer counts exactly like a
committed one.

1. **Enumerate the scope.** A skill is in scope when an **override
   file names it** (`.apache-magpie-overrides/<override-name>.md` or
   `<override-name>.md` in the personal layer), **or** when one of its
   `requires_config:` entries **resolves** from the personal layer
   or `.apache-magpie-overrides/`. A project that supplies a skill's
   configuration has configured that skill, whether or not it also
   overrides it — so take the broad reading rather than trying to
   guess which skills the project "meant". This is still **not** every
   skill the framework ships; how many it is depends entirely on how
   much the project configures, which is two for a project with a
   single override and most of the catalogue for one that commits a
   widely-read `project.md`.

   Record, per skill, **which layer put it in scope**. **Committed
   scope**: a committed override file names it, or one of its
   `requires_config` files **exists** in `.apache-magpie-overrides/` —
   decided by existence there, not by the lookup chain, so a personal
   copy that shadows a committed file does not take a shared skill out
   of committed scope. **Personal-only scope**: nothing in
   `.apache-magpie-overrides/` puts it in scope; only the personal layer
   does.
   Both kinds are checked identically below; the split decides only
   where the stamp is written (Step 2).

1a. **Skip what the developer declined for good.** The personal layer's
   `reconciled.json` may carry `declined.skills`, a list of skill names
   whose `requires_config` gaps the developer declined permanently
   (Step 2). For a skill on that list, do not propose its
   `requires_config` gaps, nor a policy caller it lacks altogether
   (check 3a): leave it out of every stamp and report it on
   one *auto-skipped* line. The skip covers those findings only — anchors
   of any override for the skill, committed or personal, are still
   resolved (check 2) and proposed as usual. Refresh
   `acknowledged.skills["<skill>"]` to its current `surface_hash` only
   when nothing else about the skill is left to show: none of its
   anchors moved, and it is not `unchecked` this run (check 4) —
   otherwise that acknowledgement would silence a pre-flight warning
   for a change nobody verified. **A personal override file for the
   skill (`<override-name>.md` in the personal layer) cancels the skip**:
   a developer who keeps a personal override uses that skill here, so
   its anchors and gaps are checked and proposed as usual. A skill on
   the list whose `requires_config` now resolves is not skipped either:
   it is checked, and stamped clean when it passes.

2. **Anchor resolution.** For every override file
   (`.apache-magpie-overrides/<override-name>.md` or
   `<override-name>.md` in the personal layer), read the target skill's
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
   [`update.md` Step 5](update.md#step-5--reconcile-overrides) surfaces.

3. **`requires_config` resolution.** For every skill in scope, resolve
   each `requires_config:` entry through the lookup chain
   (the personal layer's `<file>`, then `.apache-magpie-overrides/<file>`,
   [`agentic-overrides.md`](../../../../docs/setup/agentic-overrides.md)).
   An entry that resolves through neither is a finding: *"`<skill
   name>` requires `<file>`, which is not configured"* — propose
   `/magpie-setup:setup config <skill>` for it.

3a. **Caller policy grants.** When an existing vetted-ops policy is present
   (the committed `.apache-magpie-overrides/tools/vetted-ops/config.toml`,
   else the personal layer's `tools/vetted-ops/config.toml`), read its
   `[callers]` table and compare it with the canonical
   [vetted-ops README `[callers]` example](../../../../tools/vetted-ops/README.md#configuration)
   of the framework version this run checks against.
   That example is the only source of required operations: do not use a
   second hard-coded mapping, and never propose an operation it does not
   list for that caller.

   A caller is named after its skill: the skill's override name (the name
   `setup_preflight.delegation.override_name()` gives, such as
   `security-issue-sync` for `issue-sync` and `pr-management-shepherd` for
   `shepherd`), which is what the skill passes as `--caller`.
   The callers checked are:

   - **every caller the policy declares** that the README example also
     names: a missing operation is one the example grants that caller and
     the policy does not (for example the `git-*` operations added when
     skills began publishing through `vetted-op-git`);
   - **every skill installed here** (the installed families' skills, the
     default `<skills>` of [`setup config`](config.md#inputs)) whose caller
     name the README example names but the policy does not declare at all:
     the finding proposes the caller with the example's operations.
     A skill on `declined.skills` (sweep step 1a) is skipped for this
     absent-caller case only.
     When the installed set cannot be read here, check the declared callers
     and report the rest as `unchecked`, not clean.

   Honour the conditions the example's comments state: a caller limited to
   a policy whose `[repos] upstream` is a particular repository is checked
   only in such a policy, and the per-backend import additions apply only
   for the configured tracker backend (Jira, local files).
   A caller the policy declares that the example does not name (a
   project's own skill) is not compared at all.
   Never propose removing or narrowing a grant, and report an operation
   the policy grants beyond the example as nothing.

   For the import and triage callers, the example's grants are the minimum
   permissions the skill uses (for triage, the `issue-comment` its Step 6
   posts the proposal with; `security-issue-import` includes
   `body-field-get` / `body-field-set` for fold-in credits, the from-md and
   from-pr importers do not).
   For GitHub security imports using `issue-create-labeled`, also
   validate the policy's `[values] labels` allowlist against the
   labels required by each configured workflow:

   - Email and Markdown imports: `needs triage` and `security issue`.
   - PR imports: the configured scope, PR-state, and security-marker
     labels from Step 5c of `security-issue-import-from-pr`.

   Resolve project-specific label names from the adopter's current
   configuration. Do not assume every project uses the same names.
   Missing labels are findings even when all caller grants exist.
   Propose only the missing labels, preserving existing policy values.

   For a caller granted `cve-record-fetch`, `cve-record-update` or
   `cve-allocate`, check `[values] pmcs` holds the project's
   `cna_private_owner` from `<project-config>/project.md`: those operations
   refuse every PMC the policy does not list, and a policy without `pmcs`
   refuses them all.
   A missing key or a missing PMC is a finding; propose
   `pmcs = ["<pmc>"]`, never a PMC the project does not own.

   For a caller that opens pull requests (it holds, or this check proposes,
   `git-pr-create`) and labels them (`pr-add-label`, held or proposed),
   discover the labels it would set; other callers that hold `pr-add-label`
   (triage, which sets its own configured labels) are not part of this: list the `<upstream>` repository's labels
   (`gh label list --repo <upstream> --limit 300 --json name`) and compare
   them with `[values] upstream_labels`.
   Propose, by name, the repository's labels that follow a taxonomy (a
   `<dimension>:<value>` shape such as `family:tools` or `area:scheduler`),
   grouped by prefix, plus any label the project's own docs require on every
   pull request; leave other labels (`bug`, `help wanted`) out unless the
   user asks for them.
   Let the user pick the groups; never propose a pattern
   (`upstream_labels_patterns`), which the policy loader refuses for labels
   because a label reaches `gh` search qualifiers.
   A taxonomy label already listed is nothing; one the repository has and
   the policy lacks is a finding.
   When the labels cannot be listed (no network, `gh` not authenticated),
   report this part as unchecked.

   A missing caller, missing operation, missing label or missing PMC is a finding.
   Name the caller, what is missing, and the policy path.
   Show the exact minimal TOML diff: merge missing operations into the
   caller's existing array rather than creating a duplicate key, add an
   absent caller as one new key, and preserve comments, unrelated callers
   and existing permissions.

   This is a security-control change, not an automatic repair: the policy
   is `Edit`-denied to the agent, so nothing here writes it.
   The user reviews the diff and saves it; after the change the approved
   copy in `~/.config/apache-magpie/vetted-ops/` is stale until the user
   copies the policy there again (see
   [`verify` check 11a](verify.md#11a-vetted-ops-policy-approval)).
   A declined, unapplied, or unverified change leaves the finding open
   and prevents a clean reconciliation stamp.
   If the policy does not exist, mark this check not applicable:
   do not create a vetted-ops policy during reconciliation.
   If the policy, the README example or the required label values cannot
   be read or parsed, report the check as unchecked, not clean.
   An operator's own `[git]` table is not part of this check: a missing
   one is reported by `vetted-op-git`'s own refusal.

3b. **Your git values for publishing (secure setup only).** When the isolated setup is in use and a publishing skill is in
   scope, check that `~/.config/apache-magpie/vetted-ops/operator-git.toml` has a table for the project's `upstream_repo`.
   That directory is sandbox-denied, so when it cannot be read, report the check as unchecked and show the draft from
   [`config.md` Step 3a.3](config.md#step-3a3--your-git-values-for-publishing-secure-setup-only) as the line to run; never
   write the file. Without the secure setup this check does not apply.
   When `advisory_records` publishes through a pull request and `security-issue-sync` is installed, check the site repository the same way:
   its `["<site repo>"]` table, and the site policy `uvx --from ~/.claude/magpie/vetted-ops vetted-op-git --policy-from <site checkout> policy` reports
   (it runs outside the sandbox, so it can say what the sandbox cannot read); a missing one is a finding with the Step 3a.3 drafts.

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
   skills here, and that `/magpie-setup:setup reconcile` run outside the
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
   in the personal layer; else nothing, and the report says so
   rather than inventing a number. Phrase whatever is found as an
   estimate — *"your configuration looks like it was written around
   0.1.x"* — never as a fact; the two checks above do not depend on it
   either way.

## Step 1 — Present the findings

List every finding from checks 2–3a as a numbered proposal, one item per
override, `requires_config` gap, or missing caller grant or required label:

```text
1. .apache-magpie-overrides/security-issue-triage.md anchors to
   "Step 3 — Classify the disposition", renamed to
   "Step 3 — Read the report and classify" in magpie-security-issue-triage.
   → re-anchor the override to the new heading.
2. magpie-pr-management-code-review requires reviewer-routing.md,
   which is not configured.
   → /magpie-setup:setup config pr-management-code-review
```

No findings → say so plainly (*"every configured skill's anchors,
`requires_config` entries, applicable vetted-ops caller grants and required labels resolve"*), name any `unchecked` skills from
check 4, and go straight to Step 2 with nothing to confirm — writing
the stamp needs no confirmation when nothing is changing.

## Step 2 — Confirm, apply, and write the stamp

Findings present themselves for confirmation **item by item**, the same
protocol `update.md` Step 5 uses for override conflicts — the skill
does not auto-rewrite an override's anchor; re-anchoring is the
maintainer's judgement call, not pattern-matching. A `requires_config`
gap can be closed mechanically by chaining into
`/magpie-setup:setup config <skill>`; offer it per item.

For a caller policy finding (check 3a), show the minimal
TOML diff before asking. After confirmation, hand off to setup config
or let the user save the drafted policy; do not directly write the
security-control file from reconcile. A refusal does
not authorize a policy edit or a clean reconciliation stamp for that
unresolved configuration. Do not treat resolved `requires_config` files
alone as proof of a clean skill when its required caller grants or labels are missing.
Preserve existing policy content not covered by the confirmed change.

Both `acknowledged` writes below fire **on decline**, not on show — unlike
the pre-flight block's own per-skill check
([`tools/dev/preflight-block.md`](../../../../tools/dev/preflight-block.md)
step 4), which never blocks for an answer and so has no decline event to
hook, only a show. This flow blocks for a real item-by-item and
whole-sweep confirmation, so a decline here is a real event; a sweep the
operator abandons mid-flow deliberately leaves nothing recorded, so the
proposal correctly returns on the next run instead of being silently
suppressed by a write that never happened.

- **Confirmed and applied** — verify the resulting configuration
  before writing the skill's clean stamp. For caller policy
  findings, re-read and parse the saved vetted-ops policy and confirm
  that every required operation for the selected backend is present and all applicable GitHub import labels are policy-approved.
  User confirmation of a draft alone is not proof of application.
  If the policy is unchanged, missing a required grant or label, or cannot be verified,
  leave the finding unresolved and do not stamp that skill clean.
  Only after all applicable checks pass may its entry in the stamp's
  `skills:` map be written (or refreshed) with its **current**
  `surface_hash`.
- **Declined** — nothing about the project changes. Write
  `acknowledged.skills["<skill name>"]: <current surface_hash>` to the
  local file so the per-skill pre-flight does not re-propose the exact
  same finding on this skill's next invocation; the skill's entry is
  **not** added to the stamp's `skills:` map, because it is not
  actually reconciled — only shown and set aside.
  For a `requires_config` gap, or a policy caller an installed skill
  lacks altogether (check 3a), also offer **decline permanently**: on
  yes, add the skill's name to `declined.skills` in the personal
  layer's `reconciled.json`, so later sweeps skip it (sweep step 1a)
  instead of asking again every time its `surface_hash` moves. Never
  write `declined` to the committed lock: one developer's decline does
  not decide for every contributor.
- **A skill named only in `unchecked`** (sandboxed run, check 4) — no
  entry is written either way; it is neither confirmed clean nor
  declined, just unverified this run.
- **A both-stores collision** (Step 0.3) — confirming drops that
  skill's redundant `skills` entry from
  the personal layer's `reconciled.json`, leaving the committed lock
  as the single store and the three always-local keys untouched.
  Declining leaves both entries in place; the local one keeps winning
  and the collision is reported again next run.

Once every finding has been confirmed, applied, or declined:

- If **dry-run** was passed, stop here — report what would have been
  written, write nothing.
- Otherwise write `version` (the framework version — or, on a
  marketplace install, the installed plugin version — this run
  actually checked against) and `at` (today) into the target store
  chosen in Step 0, alongside the `skills:` map built above. On an
  adopted project the map splits by scope (sweep step 1): committed-scope
  skills go to the committed lock, personal-only skills to the personal
  layer's `reconciled.json` `skills` map. **Update that map in place;
  never rebuild it from this run alone.** Write the personal-only skills
  stamped this run, and remove an entry only once nothing is lost: its
  skill moved to committed scope **and** this run wrote its committed
  entry, its skill left scope altogether, or the developer confirmed a
  collision cleanup. Every other existing entry stays — a both-stores
  collision the developer chose to keep, and any skill left `unchecked`
  this run (check 4), whatever its scope now, because its previous hash
  is the only baseline its drift warnings have until a sweep verifies a
  replacement. If the
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

Scope:      <N> configured skill(s) (<C> committed, <P> personal-only), <M> override file(s)
Baseline:   <estimate, or "unknown">    (wording only — not load-bearing)

Anchor resolution:
  ✓ <override files whose anchors still resolve>
  ⚠ <override file>  →  <old heading> renamed to <new heading>
  ? <skills whose SKILL.md could not be read here — see Unchecked below>

requires_config resolution:
  ✓ <skills whose required files all resolve>
  ⚠ <skill>  needs <file>, not configured  →  /magpie-setup:setup config <skill>
  – <skill list>  auto-skipped (declined permanently; no personal override)

Both-stores collision:
  ✓ none found   OR
  ⚠ <skill> named in both the committed lock and the local file —
    expected after config-then-adopt across two machines; the local
    entry wins  →  drop the redundant local entry? [confirm]

Unchecked (sandboxed session — plugin cache not readable):
  - <none>   OR
  - <skill list>  →  re-run /magpie-setup:setup reconcile outside the sandbox

Stamp:
  written to <.apache-magpie.lock | <personal layer>/reconciled.json>
  (adopted: committed-scope skills in the lock, personal-only skills in
   <personal layer>/reconciled.json)
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
  "target skill no longer exists" case `update.md` Step 5 already
  covers, not a sandbox limitation.
- **`dry-run` with findings present** → report only; nothing is
  written, including the stamp.
