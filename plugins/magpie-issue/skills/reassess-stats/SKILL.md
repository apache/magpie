---
# SPDX-License-Identifier: Apache-2.0
# https://www.apache.org/licenses/LICENSE-2.0
name: magpie-issue-reassess-stats
family: issue
mode: Meta
requires_config:
  - issue-tracker-config.md
description: |
  Read-only dashboard over a directory of `verdict.json` files
  produced by `issue-reassess` campaigns. Surfaces a health
  rating, classification distribution, partial-fix surfaces,
  oldest-unresolved buckets, and per-component breakdowns.
  Output is HTML by default; markdown fallback available.
  Read-only on tracker state; consumes campaign artefacts.
when_to_use: |
  When a maintainer asks "what's the state of the reassessment
  campaign", "give me the dashboard for the recent sweep", or
  "which issues still fail across pool runs". Also as a
  pre-release check on whether the EOL pool has dropped, and
  as a periodic health-of-the-backlog view.
capability: capability:stats
surface_hash: sha256:17acede01fa2f929
license: Apache-2.0
---

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- Placeholder convention (see ../../AGENTS.md#placeholder-convention-used-in-skill-files):
     <project-config>          → adopter's project-config directory
     <issue-tracker>           → URL of the project's general-issue tracker
     <issue-tracker-project>   → project key within the tracker
     <upstream>                → adopter's public source repo
     <default-branch>          → upstream's default branch
     Substitute these with concrete values from the adopting
     project's <project-config>/ before running any command below. -->

# issue-reassess-stats

<!-- BEGIN MAGPIE PREFLIGHT — generated from tools/dev/preflight-block.md -->

## Pre-flight — is this project set up?

Do this **first, before anything else in this skill**, and do it silently: a
couple of file checks, or one CLI call for a marketplace install.

**This block decides one thing: whether to stay silent.** Each step either
passes silently or sends you to `preflight-detail.md` — a file in this
skill's own directory, alongside this one — which carries that step's branch
handling, the rules constraining it, and the reasoning. The text here is
deliberately not enough to act on: **never act on a non-silent outcome
without reading that file first.** If it cannot be read, say so and continue
into the work the user asked for rather than improvising the branch.

1. **Is a lock present?** If `.apache-magpie.lock` exists, read its
   `method`.

2. **A snapshot method** (`svn-zip` / `git-tag` / `git-branch`) →
   compare with `.apache-magpie.local.lock`:
   - local lock missing → the snapshot was never fetched on this
     machine;
   - `ref` / `commit` differ → this machine is on a different framework
     version than the project pins.
   Anything unresolved → **stop and propose `/magpie-setup`** (or
   `/magpie-setup upgrade` for a version mismatch).

3. **`method: marketplace`** → the lock is the project's **floor**: a
   minimum version and a minimum plugin set, never a pin. Compare the
   machine against it.

   **First, check `url`.** If it is anything other than `apache/magpie`,
   run **nothing** → *detail, step 3*.

   Otherwise read the installed state — `claude plugin list --json`, or
   the running agent's equivalent. **An empty or unreadable result is
   unknown, never absent**: run nothing, propose nothing, say nothing,
   and carry on to step 4. Only a result the session actually read drives
   anything. Compare **as PEP 440, not as strings**, with no special
   handling for a `.devN` segment.

   - every floor plugin installed at or above `min_version` →
     **silent**; continue the skill;
   - anything else — a plugin absent, a plugin below `min_version`, or no
     such CLI to read → *detail, step 3*.

   **Never** remove a plugin, downgrade one, pin the marketplace to a tag,
   or touch a plugin absent from the floor. Being *ahead* of the floor is
   the normal case and is not a finding.

4. **Compare this skill's fingerprint against the reconciliation stamp.**
   Skip this step entirely — silent, no reads — when any of these holds:

   - none of `.apache-magpie.lock`, `.apache-magpie-local/` or
     `.apache-magpie-overrides/` exists: nothing has ever been configured
     or adopted, so there is nothing to reconcile;
   - step 3 ended in a state step 5 below stops the run for. **An
     *unknown* step 3 result is not such a stop** — step 4 runs normally
     after one, the same way step 5 already continues past one;
   - this skill's own `surface_hash` is not visible in the context you
     were given — a check that cannot read its own input says nothing
     rather than guessing.

   This check runs the same way regardless of `method`, or whether there
   is a lock at all — it is not install-method-specific, unlike step 3.

   Otherwise: this skill's own `surface_hash` is already in context, keyed
   by its own frontmatter `name:` (e.g. `magpie-security-issue-triage`).
   When a lock exists, look that name up in its `reconciled.skills` map —
   already open from step 1, no extra read.

   - **Found, hash matches** → **silent**. Continue — nothing else in this
     step needs a read.
   - **Anything else** — found and differing, not found in the lock's map,
     or no lock at all → *detail, step 4*.

5. **Unless step 3 passed silently or came back unknown, stop.**
   Whichever branch you took — plugins installed or updated, commands
   printed because there is no CLI, or nothing run at all because `url`
   named another marketplace — this session is still below the project's
   floor. Claude Code loads plugins at session start, so anything just
   installed is not live here, and anything only printed has not run at
   all. Say what ran, or what to run, and that the session has to be
   restarted before re-running this command. An unknown result carries no
   such action — there is nothing to say and nothing to restart for, so
   continue.

6. **No lock?** Then this is the marketplace install without adoption,
   or nothing at all. That is a supported end state, not a fault — what
   matters is whether *this skill's* configuration resolves.

7. **Resolve this skill's `requires_config:` frontmatter.** Each file,
   per the lookup chain: `.apache-magpie-local/<file>` (gitignored,
   personal) first, then `.apache-magpie-overrides/<file>` (committed).
   All present → **silent**, carry on.

   Any required file missing → **run `/magpie-setup config` for this
   skill now**, say that you are doing it and why, then continue into the
   work the user actually asked for. Two things it may not do: **fabricate
   a value** — anything it cannot derive from the repository is a question
   it asks or a `TODO` it leaves — and **continue past a value it needs
   but does not have**. Why running it unasked is safe, and why it needs
   no restart → *detail, step 7*.

8. **Never run `/magpie-setup adopt` unattended.** Adoption commits a
   recommendation for every contributor and is a maintainer's decision
   taken with the other maintainers. When configuration was just
   written locally, add **one line** saying the project can also adopt
   Magpie so contributors get this on clone, and name the command.
   Then drop it. Do not ask, do not offer to run it, and do not repeat
   it on later invocations.

9. **Note what needed confirming, and propose vetting the reads.**
   Neither this step nor step 10 below is a pre-flight check — both are
   settled at the *end* of the run, and live here only because this block
   is the one thing every skill carries.

   While you work, keep note of each operation that stopped for a
   confirmation prompt: the command, and what it was for. Say nothing when
   nothing prompted, or when everything that did was a write. When the run
   ends and any of them were **read-only** → *detail, step 9*. **Propose;
   never apply** — never edit the vetted-ops catalogue, the policy, or a
   permission rule.

10. **Suggest `/magpie-setup verify` when it is overdue.** Same reasoning
    as step 9 above.

    Compare today against the **most recent** of `verified_at` and
    `verify_suggested_at` in `.apache-magpie-local/reconciled.json`
    (already read in step 4 above if that step read it; read it now
    otherwise), and — when neither is present — against the stamp's `at:`.
    Not older than `setup.verify_interval_days` (default 14, `0` disables)
    → say nothing. Older → *detail, step 10*.

Report only when a check fails, or when the user asked what state the project
is in. `/magpie-setup verify` is the full diagnostic.

<!-- END MAGPIE PREFLIGHT -->

Read-only dashboard skill over the `verdict.json` artefacts
produced by [`issue-reassess`](../reassess/SKILL.md)
campaigns. Surfaces a health rating, classification distribution,
the `still-fails-*` action tail, partial-fix surfaces, new-issue
candidates from cross-family probes, and per-component breakdowns.

The skill is the read-only counterpart to
[`issue-reassess`](../reassess/SKILL.md) — both consume the
same on-disk artefacts. Where reassess **writes** verdicts (one
per candidate) and a `report.md`, this skill **renders** an at-a-
glance dashboard for the maintainer to scan.

Modelled on [`pr-management-stats`](../../../magpie-pr-management/skills/stats/SKILL.md).

---

## Golden rules

**Golden rule 1 — read-only on tracker AND on campaign
artefacts.** This skill reads `verdict.json` files and emits HTML.
It does **not** modify any campaign artefact, does **not** post to
`<issue-tracker>`, does **not** re-invoke `issue-reproducer`.

**Golden rule 2 — HTML by default.** The dashboard is designed for
the *"what should I do today"* glance. Markdown and tables-only
fallbacks are available for terminal pipelines (`--markdown`,
`--tables-only`).

**Golden rule 3 — surface action candidates first.** The dashboard
opens with the still-failing-bug count and the new-issue
candidates from probes — these are where work happens. The bulk
fixed-on-master / cannot-run-* counts come second.

**Golden rule 4 — fresh read on every invocation.** The dashboard
re-reads `verdict.json` files on every run; no in-memory caching.
This makes the dashboard a coherent snapshot of the campaign
state at the moment of invocation.

**Golden rule 5 — multi-campaign reads are explicit.** When the
user points the skill at a directory that contains multiple
campaign subdirectories, it asks which one — never silently
aggregates across campaigns.

---

## Adopter overrides

Before running the default behaviour documented below, this skill
consults
[`.apache-magpie-local/issue-reassess-stats.md`](../../../../docs/setup/agentic-overrides.md) (personal, gitignored) and [`.apache-magpie-overrides/issue-reassess-stats.md`](../../../../docs/setup/agentic-overrides.md) (committed, project-wide)
in the adopter repo if it exists, and applies any agent-readable
overrides it finds. See
[`docs/setup/agentic-overrides.md`](../../../../docs/setup/agentic-overrides.md)
for the contract.

**Hard rule**: agents NEVER modify the snapshot under
`<adopter-repo>/.apache-magpie/`. Local modifications go in the
override file.

---

## Snapshot drift

Also at the top of every run, this skill compares the gitignored
`.apache-magpie.local.lock` (per-machine fetch) against the
committed `.apache-magpie.lock` (the project pin). On mismatch
the skill surfaces the gap and proposes
[`setup upgrade`](../../../magpie-setup/skills/setup/upgrade.md).

---

## Prerequisites

- A campaign directory exists at the path the user supplies (or
  the project's default per
  [`<project-config>/reproducer-conventions.md`](../../../../projects/_template/reproducer-conventions.md)).
- That directory contains `<KEY>/verdict.json` files for the
  campaign's candidates (at least one).

No tracker access required — the skill operates entirely on
on-disk artefacts.

---

## Inputs

| Selector | Resolves to |
|---|---|
| `stats <campaign-dir>` (default) | path to a campaign directory |
| `--markdown` | emit markdown instead of HTML |
| `--tables-only` | emit terminal-rendered tables only (no hero cards, no recommendations) |
| `--output <file>` | write to a file instead of stdout |
| `--component <name>` | filter the dashboard to one component |

The default output is HTML to stdout; the user pipes it to a file
or opens it directly.

---

## Step 0 — Pre-flight

1. **Campaign directory exists** at the supplied path.
2. **At least one `verdict.json`** present under the directory.
3. **Override consultation** — see *Adopter overrides* above.
4. **Drift check** — see *Snapshot drift* above.

If the directory has multiple campaign subdirs (e.g., the user
pointed at `<scratch>/`), prompt which to use.

---

## Step 1 — Fetch the verdicts

Read every `verdict.json` under the campaign directory. Parse and
schema-validate each per
[`issue-reproducer/verdict-composition.md`](../reproducer/verdict-composition.md).
Skip and report any file that fails to parse; do not aggregate
partial data.

Full details: [`fetch.md`](fetch.md).

---

## Step 2 — Classify

Bucket each verdict by `classification` (10 labels) and orthogonally
by `nature` (5 labels). Detect multi-case partial fixes from the
`cases` array. Cross-tabulate classification × nature.

Full details: [`classify.md`](classify.md).

---

## Step 3 — Aggregate

Compute the dashboard's payload:

- Total candidates, breakdown by classification and nature.
- Health rating (Healthy / Needs attention / Action needed) per
  the project's thresholds.
- Action candidates (still-failing tail).
- Closure candidates (fixed-on-master with strong evidence).
- New-issue candidates (probe findings).
- Per-component breakdown.

Full details: [`aggregate.md`](aggregate.md).

---

## Step 4 — Render

Emit the dashboard. Default is HTML with inline CSS (single self-
contained file); markdown and tables-only fallbacks honour the
`--markdown` and `--tables-only` flags.

Full details: [`render.md`](render.md).

---

## Step 5 — Output

Write to stdout (default), to a file if `--output` was passed, or
present in the agent's response if the user invoked the skill
interactively.

The HTML output is self-contained — no external CSS, no JS, no
images. A maintainer opens it in any browser without setup.

---

## Step 6 — Hand-back

Surface to the user:

- The path to the rendered output (if file mode).
- Headline numbers (count of still-failing, count of new-issue
  candidates).
- Recommended next actions:
  - For each still-failing candidate: `issue-fix-workflow <KEY>`.
  - For each closure candidate: a manual close via the tracker.
  - For each new-issue candidate: a manual file via the tracker.

The skill never executes any of these next actions — it only
recommends.

---

## Hard rules

- **Never modify campaign artefacts.** Read-only on the campaign
  directory; no re-running `issue-reproducer`, no rewriting
  `verdict.json`.
- **Never post to `<issue-tracker>`** — the dashboard is a local
  view; tracker writes go through other skills.
- **Never aggregate across campaigns** without an explicit user
  prompt. Each campaign's verdicts are scoped to one
  `<campaign-id>`.
- **Never invent counts.** If a `verdict.json` failed to parse,
  it's surfaced as a parse error, not counted in the totals.

---

## Failure modes

| Symptom | Likely cause | Remediation |
|---|---|---|
| Campaign directory contains no `verdict.json` files | Campaign hasn't run yet, or paths are wrong | Invoke `issue-reassess` to populate, or correct the path |
| `verdict.json` parse error on N files | Schema drift, manual edits, or interrupted campaign run | Surface the failing paths; do not aggregate partial data |
| All verdicts classified `cannot-run-*` | Pool was shape-D / shape-H heavy, or runtime is broken | Surface in the dashboard's *"limitations"* section |
| Health rating threshold seems wrong for this project | Project's defaults don't match its scale | Override via `.apache-magpie-overrides/issue-reassess-stats.md` |
| Age bands don't match the project's pace | "Recent" is project-relative; defaults assume a moderately active project | Override the band edges via `.apache-magpie-overrides/issue-reassess-stats.md` |

---

## References

- [`fetch.md`](fetch.md) — reading verdict files.
- [`classify.md`](classify.md) — classification + nature bucketing.
- [`aggregate.md`](aggregate.md) — health rating, action
  candidates, recommendation rules.
- [`render.md`](render.md) — HTML layout, markdown fallback,
  recommendation panel.
- [`issue-reassess`](../reassess/SKILL.md) — producer of
  the verdicts this skill consumes.
- [`issue-reproducer/verdict-composition.md`](../reproducer/verdict-composition.md) —
  the schema being read.
- [`pr-management-stats`](../../../magpie-pr-management/skills/stats/SKILL.md) — the
  structural template this skill mirrors.
- [`tools/dashboard-generator/`](../../../../tools/dashboard-generator/) —
  reference implementation that produces the same output
  deterministically (for adopters who want CI-rendered dashboards
  without invoking the agent).
- [`docs/issue-management/README.md`](../../../../docs/issue-management/README.md) —
  family overview.
