---
# SPDX-License-Identifier: Apache-2.0
# https://www.apache.org/licenses/LICENSE-2.0
name: status
family: setup
mode: Meta
description: >-
  Show how Magpie is adopted in this repo — install method and pin,
  drift, wired agent targets, installed skill families, symlink health —
  and change that wiring from the same view. The change itself runs
  through the setup skill.
when_to_use: >-
  When the user asks how Magpie is set up here, which targets are
  wired, which families are installed, or whether the snapshot is in
  sync. Also when they want to add a target or family and want to see
  the current state first.
capability:
  - capability:stats
  - capability:platform
surface_hash: sha256:85dfb8b48739fc11
license: Apache-2.0
measured_tokens: 2767
---

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- Placeholder convention (see ../../AGENTS.md#placeholder-convention-used-in-skill-files):
     <project-config>  → adopter's `.apache-magpie-overrides/` directory
     <snapshot-dir>    → `.apache-magpie/` (gitignored snapshot of the framework)
     <committed-lock>  → `.apache-magpie.lock` (committed — the project's pin)
     <local-lock>      → `.apache-magpie.local.lock` (gitignored — per-machine record)
     <upstream>        → adopter's public source repo (the repo this skill runs in) -->

# setup-status

<!-- BEGIN MAGPIE BLOCK: sandbox-golden-rule — generated from tools/dev/blocks/sandbox-golden-rule.md -->

**Golden rule — a step the sandbox blocks becomes a vetted operation, never
a bypass.** This holds for the whole run. When anything you need to do fails
on a sandbox restriction (a blocked host or transport, a read-only path, a
denied credential or socket):

1. Never leave the sandbox for it: no sandbox-disabling flag, and no wider
   exclusion or allow rule proposed as the fix.
2. Look for a route that stays safe: a spelling the sandbox allows (fetch in
   the main checkout, rewrite history in a scratch clone), or a vetted
   operation that already covers it (`vetted-op-read`, `vetted-op`,
   `vetted-op-tracker`, `vetted-op-git`), launched with the literal `~` path.
   Publishing a change is covered end to end by `vetted-op-git`:
   `git-worktree-add`, `git-fetch`, `git-stage`, `git-commit`,
   `git-push-branch`, `git-pr-create`. Run the checks in the sandbox first,
   and never hand those steps to the user as commands to paste.
3. If none exists, do the rest of the work, give the user the one command to
   run this time, and propose `/magpie-setup:upstream-fix` for it: a
   closed-shape vetted operation (fixed argv, validated parameters, destination
   from the approved policy, no repository code or configuration steering it,
   behind a confirmation) or a documented in-sandbox route. Opening that PR
   needs the user's go-ahead, like any other publication.

<!-- END MAGPIE BLOCK: sandbox-golden-rule -->

Render a one-glance picture of **how apache-magpie is adopted in
this repo**, then let the user reconfigure it without leaving the
view. The dashboard answers the questions an operator actually
asks: *which install method and version are pinned, has the
snapshot drifted, which agent targets are wired, which skill
families are installed, and are the symlinks healthy.*

This skill is the **configuration** view of adoption. It is read-
only on its own; every change it offers is carried out by
delegating to [`setup`](../setup/SKILL.md) — the one skill
that owns adoption mutation. For a **deep integrity / health
check** (lock parsing, per-check ✓/✗ matrix, permission-hygiene
audit, ASF comdev MCP prerequisites, stale-worktree sweep), use
[`setup verify`](../setup/verify.md); this skill links to
it rather than duplicating its checks.

---

## Adopter overrides

<!-- BEGIN MAGPIE BLOCK: adopter-overrides — generated from tools/dev/blocks/adopter-overrides.md -->

Before running its default behaviour, this skill consults
`setup-status.md` in the personal layer
(`.apache-magpie-local/` when the project adopted Magpie, falling back to the main checkout's in a linked worktree,
or `<git-common-dir>/apache-magpie/` when Magpie is only installed; applied first, wins on conflict) and
[`.apache-magpie-overrides/setup-status.md`](../../../../docs/setup/agentic-overrides.md) (committed, project-wide)
in the adopter repo, if present, and applies any agent-readable overrides it finds.
See [`docs/setup/agentic-overrides.md`](../../../../docs/setup/agentic-overrides.md) for the contract.

**Hard rule**: agents NEVER modify the snapshot under `<adopter-repo>/.apache-magpie/`.
Local modifications go in the override file; framework changes go via PR to `apache/magpie`.

<!-- END MAGPIE BLOCK: adopter-overrides -->

---

## Snapshot drift

Also at the top of every run, this skill compares the gitignored
`.apache-magpie.local.lock` (per-machine fetch) against the
committed `.apache-magpie.lock` (the project pin). On mismatch the
skill surfaces the gap and proposes
[`setup update`](../setup/update.md). The proposal is
non-blocking; surfacing the drift is itself part of this skill's
dashboard, so the comparison feeds [Step 1](#step-1--render-the-dashboard)
rather than gating the run.

---

## Inputs

**Skill directives** (how the user invokes the skill):

| Input | Effect |
|---|---|
| (none) | Render the dashboard, then offer adjustments interactively. |
| `--no-adjust` | Render only; skip the reconfigure offer. |
| `adjust` | Skip straight to the reconfigure flow after a brief state recap. |

**Collector flags** (passed through to
[`scripts/collect_status.py`](scripts/collect_status.py)):

| Flag | Effect |
|---|---|
| `--repo <path>` | Inspect a repo other than the current git top-level. |
| `--format md` | The Markdown dashboard (default). |
| `--format json` | The raw machine-readable fields ([`collect.md`](collect.md)); add `--pretty` to indent. |

The default output is the Markdown dashboard, rendered
deterministically by the collector.

---

## Prerequisites

- A git checkout (`git rev-parse --show-toplevel` succeeds), or an
  explicit `--repo <path>`.
- `python3` on `PATH` for the deterministic collector
  ([`scripts/collect_status.py`](scripts/collect_status.py)). No
  third-party packages, no network access.

This skill reads only framework-internal, on-disk state (lock
files, symlinks, `.gitignore`, the post-checkout hook). It reads
**no external or private content**, so the prompt-injection and
Privacy-LLM gate-checks do not apply.

---

## Step 0 — Pre-flight check

1. Resolve the repo root (`--repo` if given, else
   `git rev-parse --show-toplevel`).
2. Apply adopter overrides and the drift preamble above.
3. **Adopted?** If `<committed-lock>` (`.apache-magpie.lock`) is
   absent, the repo is **not adopted**. Say so, point at
   [`setup`](../setup/SKILL.md) to adopt, and stop — there
   is no state to render.

---

## Step 1 — Render the dashboard

The collector **renders the dashboard itself**. Run it (it never
writes and never fetches):

```bash
python3 <skill-dir>/scripts/collect_status.py
```

(`<skill-dir>` is the directory holding this skill's `SKILL.md`;
`<framework>/skills/` does not exist on a marketplace install. The default output
is the Markdown dashboard; pass `--format json` only when tooling
needs the raw fields — see [`collect.md`](collect.md).)

> **OUTPUT CONTRACT — non-negotiable.** Present the script's
> Markdown output **verbatim** (it is already GitHub-flavoured
> Markdown — let the harness render the pipe table). Do **not**:
> re-draw it as a box-drawing/ASCII table; drop the `serves` bullet
> legend (it carries the agents each directory serves, including
> the whole `universal` cluster); add a Reads column back into the
> table (that is what made it wrap and break); recompute the
> verdict; or "prettify" the layout. The script, not the agent,
> owns the rendering, precisely because an LLM formatting pass
> reliably mangles it (drops the agents-served legend, renames
> columns, re-introduces the wide column). If you find yourself
> rebuilding the table, stop and paste the script output instead.

The renderer owns the headline, the agent-target table plus its
`serves` legend (so the `universal` cluster and every registry
vendor always appear), the family roster, and the drift /
integrity summary.

Full layout reference, the health-verdict rules, and mode-aware
interpretation: [`render.md`](render.md).

---

## Step 2 — Interpret (lightly)

After printing the verbatim dashboard, optionally add a one-line
**mode-aware** note where it helps — without re-tabulating or
contradicting the script output. Example: a `method:local`
framework checkout commits its symlinks and has no snapshot or
local lock, so the absent snapshot is healthy there but a fault
for a normal adopter ([`render.md`](render.md#mode-aware-interpretation)).

---

## Step 3 — Offer adjustments

Unless `--no-adjust` was passed, end the dashboard with the
reconfigure offer. Detect the obvious deltas (a registry target
present on disk but not wired; an opt-in family not installed;
dangling symlinks; drift) and present each as a concrete,
confirmable change. On confirmation, **delegate to
[`setup`](../setup/SKILL.md)** with the right flags
(`agents:<list>`, `skill-families:<list>`, or `update`) — this
skill never edits symlinks, locks, or `.gitignore` itself.

Full gap-detection and delegation rules: [`adjust.md`](adjust.md).

---

## Hard rules

- **Read-only on its own; mutation only via setup.** This skill
  never writes a symlink, a lock file, or `.gitignore`. Every
  change is delegated to [`setup`](../setup/SKILL.md),
  preserving the framework's single source of truth for adoption
  mutation.
- **Propose before applying.** Each adjustment is a proposal the
  user explicitly confirms before the delegated `setup`
  run starts. No silent reconfiguration.
- **Do not duplicate `verify`.** For deep integrity, permission
  hygiene, comdev-MCP prerequisites, and the stale-worktree sweep,
  point the user at [`setup verify`](../setup/verify.md)
  rather than re-implementing those checks here.
- **Never invent state.** Report only what the collector observed.
  If a field is unknown (e.g. upstream-tip drift needs network),
  say it was not checked and name the skill that does check it.

---

## References

- [`collect.md`](collect.md) — the collector's JSON field
  reference.
- [`render.md`](render.md) — dashboard layout, health-verdict
  rules, mode-aware interpretation.
- [`adjust.md`](adjust.md) — gap detection and the delegation
  contract to `setup`.
- [`scripts/collect_status.py`](scripts/collect_status.py) — the
  deterministic, read-only state collector.
- [`setup`](../setup/SKILL.md) — adoption mutation:
  [`install.md`](../setup/install.md), [`update.md`](../setup/update.md),
  the [`agents.md`](../setup/agents.md) target registry, and the
  [Golden rules](../setup/SKILL.md#golden-rules).
- [`setup verify`](../setup/verify.md) — the deep
  integrity / health check this dashboard complements.
- [`AGENTS.md`](../../../../AGENTS.md) — framework conventions and the
  placeholder convention.
- [`docs/setup/agentic-overrides.md`](../../../../docs/setup/agentic-overrides.md)
  — the override contract every skill consults.
