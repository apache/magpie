---
# SPDX-License-Identifier: Apache-2.0
# https://www.apache.org/licenses/LICENSE-2.0
name: override-upstream
family: setup
mode: Meta
description: >-
  Promote a local `.apache-magpie-overrides/<skill>.md` into a PR
  against `apache/magpie`. Once it merges and the adopter upgrades, the
  override is redundant and the skill offers to remove it.
when_to_use: >-
  When the user wants a local override contributed back to the
  framework — typically after living with it for a while and deciding
  it belongs upstream.
argument-hint: "[skill-name]"
capability: capability:platform
surface_hash: sha256:33f740e1edbcdfda
license: Apache-2.0
---

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/legal/release-policy.html -->

<!-- Placeholder convention (see ../../AGENTS.md#placeholder-convention-used-in-skill-files):
     <adopter-repo>           → repo this skill is being run in (an adopter)
     <override-file>          → .apache-magpie-overrides/<skill>.md being upstreamed
     <framework-skill>        → framework skill the override modifies
     <framework-clone>        → user's local clone of apache/magpie
                                (separate from .apache-magpie/, which is a gitignored snapshot)
     <framework-fork>         → user's GitHub fork of apache/magpie
                                (where the PR branch gets pushed) -->

# setup-override-upstream

This skill turns a *local override* into a *framework feature*.
It takes one `.apache-magpie-overrides/<skill>.md` file in an adopter repo, helps the user decide whether the change is worth upstreaming, designs the framework-level abstraction, implements it in `apache/magpie`, and opens a PR.

Overrides (per [`docs/setup/agentic-overrides.md`](../../../../docs/setup/agentic-overrides.md)) are deliberately *agentic* and *adopter-local*: no schema, no anchors, no patch tool.
That makes them quick to write but hard to share, since every adopter who wants the same behaviour writes their own.
**Upstreaming** is the escape hatch: when an override starts looking like a missing feature, a PR bakes it into the framework default, and every adopter gets it on their next `setup upgrade`.

## Adopter overrides

Before running the default behaviour below, this skill consults [`.apache-magpie-local/setup-override-upstream.md`](../../../../docs/setup/agentic-overrides.md) (personal, gitignored) and [`.apache-magpie-overrides/setup-override-upstream.md`](../../../../docs/setup/agentic-overrides.md) (committed, project-wide) in the adopter repo, if they exist, and applies any agent-readable overrides it finds.
The contract (what overrides may contain, hard rules, reconciliation on framework upgrade, upstreaming guidance) is in [`docs/setup/agentic-overrides.md`](../../../../docs/setup/agentic-overrides.md).

**Hard rule**: agents NEVER modify the snapshot under `<adopter-repo>/.apache-magpie/`.
Local modifications go in the override file.
Framework changes go via PR to `apache/magpie`.

---

## Snapshot drift

Also at the top of every run, this skill compares the gitignored `.apache-magpie.local.lock` (per-machine fetch) against the committed `.apache-magpie.lock` (the project pin).
On mismatch it surfaces the gap and proposes [`setup upgrade`](../setup/upgrade.md).
The proposal is non-blocking; the user may defer and run with the local snapshot for now.
Full flow: [`docs/quick-start/other-install-methods.md` § Subsequent runs and drift detection](../../../../docs/quick-start/other-install-methods.md#subsequent-runs-and-drift-detection).

Drift severity:

- **method or URL differ** → ✗ full re-install needed.
- **ref differs** (project bumped tag, or `git-branch` local is behind upstream tip) → ⚠ sync needed.
- **`svn-zip` SHA-512 mismatches the committed anchor** → ✗ security-flagged; investigate before upgrading.

> **Doubly important here**: the skill designs a framework-level abstraction by reading the snapshot's framework skill.
> A stale snapshot means designing against a version that may already have changed upstream.
> Address drift before proceeding.

---

## Golden rules

**Golden rule 1 — not every override should be upstreamed.**
Many overrides encode *project-specific* choices: canned-response wording, the scope-label taxonomy, a milestone-format regex, a tone-of-voice preference.
These stay in the adopter repo.
The skill walks through this decision explicitly and stops early if the change does not generalise.

**Golden rule 2 — write to `<framework-clone>`, never to
the snapshot.**
The framework PR is implemented in the user's local apache-magpie clone, a separate working directory from the adopter's gitignored, read-only `.apache-magpie/` snapshot.
If the user has no clone yet, the skill helps set one up.

**Golden rule 3 — assistant proposes, user fires.**
Per the framework convention (see [`AGENTS.md`](../../../../AGENTS.md)), every state-changing action (clone, branch, commit, push, `gh pr create`) is proposed and runs only on explicit user confirmation.
Public PR content is shown to the user before it is posted.

**Golden rule 4 — decouple PR from override deletion.**
Opening the framework PR is one step.
Deleting the now-redundant override file is a separate step, AFTER the PR has merged AND the adopter has run `setup upgrade` to pick up the change.
The skill ends with a pointer at that cleanup; it does not delete the override preemptively.

## Walk-through

### Step 0 — Pre-flight

1. We are in an adopter repo (has `<adopter-repo>/.apache-magpie.lock` and `<adopter-repo>/.apache-magpie-overrides/`).
   If not, stop — the skill is for adopters with at least one override file.
2. The snapshot is current (no drift per the section above).
   If drift exists, propose `setup upgrade` first.
3. Identify `<framework-clone>`, the user's local clone of `apache/magpie`.
   Common locations: `~/code/magpie/`, `~/work/magpie/`.
   If not found, ask the user where it is, or help them clone it (`git clone
   git@github.com:apache/magpie.git`).
   The clone is **separate** from `<adopter-repo>/.apache-magpie/` (the snapshot).

### Step 1 — Pick the override

List `<adopter-repo>/.apache-magpie-overrides/*.md` (excluding the directory's own `README.md`).
For each, print the file name + first headline.

- **Zero overrides** → stop. There is nothing to upstream.
- **One override** → auto-pick.
- **Multiple** → ask the user which one to upstream this run.
  The skill handles one override per invocation (clean PR, clean review).

### Step 2 — Read the override + framework skill

Read the chosen override file. Surface to the user:

- Title + the override headlines (`### Override N — ...`)
- The "why" paragraph if the file has one

Then read the framework skill it modifies, from the snapshot at `<adopter-repo>/.apache-magpie/skills/<framework-skill>/`.
Surface:

- The skill's purpose (frontmatter description)
- The specific section(s) the override modifies (steps, decision-table rows, golden rules)
- Any cross-skill references the override depends on

Goal: the user and the agent both know *what* the change is and *where* it applies.

### Step 3 — Decide if upstreamable

Walk through with the user.
Common categories:

- **Project-specific** (canned-response wording, scope labels, milestone formats, tooling assumptions particular to this project) → **stop here**.
  Suggest the override stay local.
  Generalising would force the framework either to include the adopter's specifics (defeats project-agnosticism) or to expose a config knob no other adopter would set the same way (bloats the contract).
- **Missing feature** (the override does something useful any adopter might want) → **continue**.
  The framework should learn this behaviour by default, or expose it as an opt-in.
- **Better default** (the override changes a default the framework currently picks; if most adopters would prefer the override's default, the framework should adopt it) → **continue**.
  The PR may also keep the old behaviour reachable via a flag.
- **Refactor a step** (the framework's step is awkward / redundant / has an edge case) → **continue**.
  The PR fixes the step itself.

If the user is unsure, lean toward **stop** — keep the override local until a second adopter wants the same thing.

### Step 4 — Design the framework-level abstraction

Once the user confirms the change is upstreamable, design the framework-side change.
Pick one of:

| Shape | When |
|---|---|
| **Add a config knob** in `<project-config>/` | The change is opt-in per-adopter; default behaviour is unchanged. |
| **Change a default** | The new behaviour is better for the majority; the framework's existing default becomes a `<project-config>/` opt-out. |
| **Add an optional step** | The change is an *additional* step (not a substitute for an existing one). |
| **Refactor existing step** | The change rewrites how an existing step works. No new config; the new behaviour is universal. |

Surface the proposal to the user and iterate.
The output is a concrete plan: which framework files to modify, what to add / remove / change, and which existing framework tests or verification may need updating.

### Step 5 — Implement in the framework clone

In `<framework-clone>`:

1. `git fetch origin && git checkout -b
   feat/<short-description> origin/main`
2. Apply the changes from the design step.
   Read the surrounding framework code first (the framework's `AGENTS.md`, the modified skill's supporting files) to match conventions.
3. Run framework pre-commit: `prek run --all-files`.
   Fix anything that fires.
4. Show the user the diff (`git diff`).
   Get explicit confirmation before committing.
5. Commit with a message matching the framework's conventions (Conventional-Commits prefix: `feat(skills): ...` for new framework behaviour, `refactor(skills): ...` for restructure, etc.).
   End the message with a `Generated-by: <agent> (<model>)` trailer, where `<agent>` and `<model>` are the actual agent and model you are running as (e.g. `Claude (Opus 4.8)`, `OpenCode (Big Pickle)`).
   Do not hardcode either, per the framework's no-coauthored-by hook.

### Step 6 — Open the PR

1. `git push -u <fork-remote> feat/<branch>`.
   If no fork remote is configured, help the user add one (`git remote add fork <user>/magpie.git`).
2. Draft the PR title + body. Include:
   - **Summary** — what the change is, in 1–3 bullets.
   - **Motivation** — link to the originating override file in the adopter repo (the user's project), with enough context that the framework reviewer understands the use case without reading the full override.
   - **Migration path for existing adopters** — if the change introduces a new config knob, explain the default; if it changes a default, explain how adopters opt out.
   - **Test plan** — what the user verified locally.
3. **Confirm with the user before posting**.
   Show the exact title + body.
   Wait for "OK to post" / "yes" / "send" / similar before running `gh pr create`.
4. **Pick the labels.** Every framework PR carries at least one `family:*` and one `capability:*` label per [`docs/labels-and-capabilities.md`](../../../../docs/labels-and-capabilities.md).
   The override is upstreaming a change to skill `<skill>`, so:
   - `family:*` — follow the skill's family (`family:pr-management` for `pr-management-*`, `family:security` for `security-*`, `family:setup` for `setup-*`, `family:issue` for `issue-*`, etc.).
   - `capability:*` — the capability the change is *implementing*, not the file paths touched.
     Look it up in the skill-to-capability map at [`docs/labels-and-capabilities.md#capability-to-skill-map`](../../../../docs/labels-and-capabilities.md#capability-to-skill-map).
   - Add `kind:*` and `mode:*` when they apply per the same doc.

   Show the chosen labels in the confirmation preview alongside the PR title and body, so the user sees them before posting.

5. Write the PR body to a tempfile first, then create the PR:
   ```bash
   # Write tool: file_path: /tmp/override-pr-body.md, content: <PR body>
   gh pr create --repo apache/magpie --base main \
     --head <user>:<branch> --title "..." --body-file /tmp/override-pr-body.md \
     --label "family:<family>" --label "capability:<capability>"
   ```

### Step 7 — Post-PR cleanup pointer

After the PR is open, surface to the user:

```text
Framework PR opened: <PR URL>

Next steps once it merges:

  1. setup upgrade   (in <adopter-repo>)
     - Bumps the snapshot to the new framework version.
     - .apache-magpie.lock will reflect the new pin.
  2. Delete .apache-magpie-overrides/<skill>.md in <adopter-repo>
     - The override is now redundant; the framework does
       what the override used to do.
  3. Commit the deletion + the bumped lock together.
```

The skill **does not** delete the override file itself.
Deletion happens after the PR merges, which the skill cannot predict (or whether reviewers accept it at all); it is the user's manual cleanup once the PR lands.

## Output to the user (skill end)

```text
✓ Override picked:        .apache-magpie-overrides/<skill>.md
✓ Framework skill:        <framework-skill>
✓ Decision:               upstreamable as <shape from Step 4>
✓ Framework clone:        <framework-clone>
✓ Branch:                 feat/<short-description>
✓ Commits:                <count>
✓ PR opened:              <PR URL>

Next: wait for the PR to merge, then in <adopter-repo>:
  setup upgrade
  rm .apache-magpie-overrides/<skill>.md
  git add -A && git commit -m "Remove override <skill>: upstreamed in apache/magpie#<N>"
```

## Failure modes

| Symptom | Likely cause | Remediation |
|---|---|---|
| `<adopter-repo>` has no `.apache-magpie-overrides/` | not adopted, or adopted without the overrides scaffold | run `setup install` (idempotent) |
| Step 1 finds zero overrides | nothing to upstream — adopter has no local modifications recorded | stop |
| `<framework-clone>` not found | user has not cloned `apache/magpie` yet | help them clone, then resume |
| Framework pre-commit fails after the implementation | the change does not match framework conventions | iterate with the user, re-run pre-commit, do not bypass with `--no-verify` |
| User decides mid-flow that the override is project-specific after all | wrong call in Step 3 | stop without opening a PR; the override file in the adopter repo is unchanged, no harm done |

## What this skill is NOT for

- Not for *applying* an override at run-time — that is the per-skill pre-flight protocol in [`docs/setup/agentic-overrides.md`](../../../../docs/setup/agentic-overrides.md).
- Not for *creating* a new override — that is [`setup override <skill>`](../setup/overrides.md).
- Not for *upgrading* the snapshot — that is [`setup upgrade`](../setup/upgrade.md).
  Run that BEFORE this skill if drift exists.
- Not for framework PRs unrelated to overrides.
  Other contributions (new skill, new tool, refactor) go through the framework's normal PR workflow.

## Cross-references

- [`docs/setup/agentic-overrides.md`](../../../../docs/setup/agentic-overrides.md) — the override contract.
- [`setup/overrides.md`](../setup/overrides.md) — how to *create* / *open* an override.
- [`setup/upgrade.md`](../setup/upgrade.md) — how to upgrade the snapshot post-merge.
