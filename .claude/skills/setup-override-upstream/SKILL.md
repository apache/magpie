---
name: setup-override-upstream
description: |
  Walk an adopter through promoting a local
  `.apache-steward-overrides/<skill>.md` file into a PR
  against `apache/airflow-steward`. After the PR merges and
  the adopter runs `/setup-steward upgrade`, the override file
  is no longer needed and the skill prompts for its removal.
when_to_use: |
  Invoke when the user says "upstream my override", "promote
  this override to the framework", "convert my local
  modification into a steward feature", "make this override
  a framework feature", "open a PR to apache-steward for
  this override", or similar — typically after running the
  override locally for a while and deciding the change is
  worth contributing back.
argument-hint: "[skill-name]"
license: Apache-2.0
---

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/legal/release-policy.html -->

<!-- Placeholder convention (see ../../AGENTS.md#placeholder-convention-used-in-skill-files):
     <adopter-repo>           → repo this skill is being run in (an adopter)
     <override-file>          → .apache-steward-overrides/<skill>.md being upstreamed
     <framework-skill>        → framework skill the override modifies
     <framework-clone>        → user's local clone of apache/airflow-steward
                                (separate from .apache-steward/, which is a gitignored snapshot)
     <framework-fork>         → user's GitHub fork of apache/airflow-steward
                                (where the PR branch gets pushed) -->

# setup-override-upstream

This skill is the path from *local override* to *framework
feature*. It takes a single
`.apache-steward-overrides/<skill>.md` file in an adopter
repo, walks the user through deciding whether the change is
worth upstreaming, designs the framework-level abstraction,
implements it in `apache/airflow-steward`, and opens a PR.

The override mechanism (per
[`docs/setup/agentic-overrides.md`](../../../docs/setup/agentic-overrides.md))
is deliberately *agentic* and *adopter-local*: there's no
schema, no anchors, no patch tool. That makes overrides
quick to write but hard to share — every adopter who wants
the same behaviour writes their own. **Upstreaming** is the
escape hatch: when an override stops being project-specific
and starts looking like a missing feature, the right move
is a PR that bakes the change into the framework's default,
making every adopter benefit on their next
`/setup-steward upgrade`.

## Adopter overrides

Before running the default behaviour documented below, this
skill consults
[`.apache-steward-overrides/setup-override-upstream.md`](../../../docs/setup/agentic-overrides.md)
in the adopter repo if it exists, and applies any
agent-readable overrides it finds. See
[`docs/setup/agentic-overrides.md`](../../../docs/setup/agentic-overrides.md)
for the contract — what overrides may contain, hard rules,
the reconciliation flow on framework upgrade, upstreaming
guidance.

**Hard rule**: agents NEVER modify the snapshot under
`<adopter-repo>/.apache-steward/`. Local modifications go in
the override file. Framework changes go via PR to
`apache/airflow-steward`.

---

## Snapshot drift

Also at the top of every run, this skill compares the
gitignored `.apache-steward.local.lock` (per-machine
fetch) against the committed `.apache-steward.lock` (the
project pin). On mismatch the skill surfaces the gap and
proposes
[`/setup-steward upgrade`](../setup-steward/upgrade.md).
The proposal is non-blocking — the user may defer if
they want to run with the local snapshot for now. See
[`docs/setup/install-recipes.md` § Subsequent runs and drift detection](../../../docs/setup/install-recipes.md#subsequent-runs-and-drift-detection)
for the full flow.

Drift severity:

- **method or URL differ** → ✗ full re-install needed.
- **ref differs** (project bumped tag, or `git-branch`
  local is behind upstream tip) → ⚠ sync needed.
- **`svn-zip` SHA-512 mismatches the committed
  anchor** → ✗ security-flagged; investigate before
  upgrading.

> **Doubly important here**: the skill is about to design
> a framework-level abstraction by reading the snapshot's
> framework skill. If the snapshot is stale, the
> abstraction may be designed against a version that has
> already changed upstream. Address drift before
> proceeding.

---

## Golden rules

**Golden rule 1 — not every override should be upstreamed.**
Many overrides encode genuinely *project-specific* choices:
the wording of a canned response, the project's scope-label
taxonomy, milestone-format regex, a tone-of-voice
preference. These should stay in the adopter repo. The
skill explicitly walks through this decision and stops
early if the change is not generalisable.

**Golden rule 2 — write to `<framework-clone>`, never to
the snapshot.** The framework PR is implemented in the
user's local apache-steward clone (a separate working
directory from the adopter's `.apache-steward/` snapshot,
which is gitignored and read-only). If the user does not
have a clone yet, the skill helps them set one up.

**Golden rule 3 — assistant proposes, user fires.** Per the
framework convention (see
[`AGENTS.md`](../../../AGENTS.md)), every state-changing
action — clone, branch, commit, push, `gh pr create` — is
proposed by the skill and only happens on explicit user
confirmation. Public PR content is shown to the user before
it is posted.

**Golden rule 4 — decouple PR from override deletion.**
Opening the framework PR is one step; deleting the now-
redundant override file in the adopter repo is a separate
step that happens AFTER the PR has merged AND the adopter
has run `/setup-steward upgrade` to pick up the framework
change. The skill ends with a clear pointer at the
post-merge cleanup; it does not delete the override
preemptively.

## Walk-through

### Step 0 — Pre-flight

1. We are in an adopter repo (has
   `<adopter-repo>/.apache-steward.lock` and
   `<adopter-repo>/.apache-steward-overrides/`). If not,
   stop — the skill is for adopters with at least one
   override file.
2. The snapshot is current (no drift per the section
   above). If drift exists, propose
   `/setup-steward upgrade` first.
3. Identify `<framework-clone>` — the user's local clone
   of `apache/airflow-steward`. Common locations:
   `~/code/airflow-steward/`, `~/work/airflow-steward/`.
   If not found, surface and ask the user where it is, or
   help them clone it (`git clone
   git@github.com:apache/airflow-steward.git`). The clone
   is **separate** from `<adopter-repo>/.apache-steward/`
   (the snapshot).

### Step 1 — Pick the override

List `<adopter-repo>/.apache-steward-overrides/*.md`
(excluding the directory's own `README.md`). For each,
print the file name + first headline.

- **Zero overrides** → stop. There is nothing to upstream.
- **One override** → auto-pick.
- **Multiple** → ask the user which one to upstream this
  run. The skill handles one override per invocation
  (clean PR, clean review).

### Step 2 — Read the override + framework skill

Read the chosen override file. Surface to the user:

- Title + the override headlines (`### Override N — ...`)
- The "why" paragraph if the file has one

Then read the framework skill it modifies, from the
snapshot at
`<adopter-repo>/.apache-steward/.claude/skills/<framework-skill>/`.
Surface:

- The skill's purpose (frontmatter description)
- The specific section(s) the override modifies (steps,
  decision-table rows, golden rules)
- Any cross-skill references the override depends on

Goal: both the user and the agent should now have a clear
mental model of *what* the change is and *where* it
applies.

### Step 3 — Decide if upstreamable

Walk through with the user. Common categories:

- **Project-specific** (canned-response wording, scope
  labels, milestone formats, tooling assumptions
  particular to this project) → **stop here**. Suggest the
  override stay local. Generalising would require the
  framework to either include the adopter's specifics
  (defeats project-agnosticism) or expose a config knob
  that no other adopter would set the same way (bloats the
  contract).
- **Missing feature** (the override does something useful
  that any adopter might want) → **continue**. The
  framework should learn this behaviour by default, or
  expose it as an opt-in.
- **Better default** (the override changes a default the
  framework currently picks; if a majority of adopters
  would prefer the override's default, the framework
  should adopt it) → **continue**. The PR may also keep
  the old behaviour reachable via a flag.
- **Refactor a step** (the framework's step is
  awkward / redundant / has an edge case) → **continue**.
  The PR fixes the step itself.

If the user is unsure, lean toward **stop** — keep the
override local until a second adopter wants the same thing.

### Step 4 — Design the framework-level abstraction

Once the user confirms the change is upstreamable, design
the framework-side change. Pick one of:

| Shape | When |
|---|---|
| **Add a config knob** in `<project-config>/` | The change is opt-in per-adopter; default behaviour is unchanged. |
| **Change a default** | The new behaviour is better for the majority; the framework's existing default becomes a `<project-config>/` opt-out. |
| **Add an optional step** | The change is an *additional* step (not a substitute for an existing one). |
| **Refactor existing step** | The change rewrites how an existing step works. No new config; the new behaviour is universal. |

Surface the proposal to the user. Iterate. The output of
this step is a concrete plan: which framework files to
modify, what to add / remove / change, what tests or
verification the framework already has that may need
updating.

### Step 5 — Implement in the framework clone

In `<framework-clone>`:

1. `git fetch origin && git checkout -b
   feat/<short-description> origin/main`
2. Apply the changes the design step decided on. Read the
   surrounding framework code first (the framework's
   `AGENTS.md`, the relevant supporting files of the
   modified skill) to match conventions.
3. Run framework pre-commit:
   `prek run --all-files`. Fix anything that fires.
4. Show the user the diff (`git diff`). Get explicit
   confirmation before committing.
5. Commit with a message matching the framework's
   conventions (Conventional-Commits prefix:
   `feat(skills): ...` for new framework behaviour,
   `refactor(skills): ...` for restructure, etc.). Use
   `Generated-by: Claude Code (Claude Opus 4.7)` trailer
   per the framework's no-coauthored-by hook.

### Step 6 — Open the PR

1. `git push -u <fork-remote> feat/<branch>`. If no fork
   remote is configured, surface and help the user add one
   (`git remote add fork <user>/airflow-steward.git`).
2. Draft the PR title + body. Include:
   - **Summary** — what the change is, in 1–3 bullets.
   - **Motivation** — link to the originating override
     file in the adopter repo (the user's project), with
     enough context that the framework reviewer
     understands the use case without reading the full
     override.
   - **Migration path for existing adopters** — if the
     change introduces a new config knob, explain the
     default; if it changes a default, explain how
     adopters opt out.
   - **Test plan** — what the user verified locally.
3. **Confirm with the user before posting**. Show the
   exact title + body. Wait for "OK to post" / "yes" /
   "send" / similar before running `gh pr create`.
4. Write the PR body to a temp file, then post:

   ```bash
   gh pr create --repo apache/airflow-steward --base main \
     --head <user>:<branch> --title "..." \
     --body-file /tmp/pr-body.md
   ```

### Step 7 — Post-PR cleanup pointer

After the PR is open, surface to the user:

```text
Framework PR opened: <PR URL>

Next steps once it merges:

  1. /setup-steward upgrade   (in <adopter-repo>)
     - Bumps the snapshot to the new framework version.
     - .apache-steward.lock will reflect the new pin.
  2. Delete .apache-steward-overrides/<skill>.md in <adopter-repo>
     - The override is now redundant; the framework does
       what the override used to do.
  3. Commit the deletion + the bumped lock together.
```

The skill **does not** delete the override file itself —
that happens after the PR merges, and the skill cannot
predict when (or if) the framework reviewers accept the
PR. Deletion is the user's manual cleanup once the PR
lands.

## Output to the user (skill end)

```text
✓ Override picked:        .apache-steward-overrides/<skill>.md
✓ Framework skill:        <framework-skill>
✓ Decision:               upstreamable as <shape from Step 4>
✓ Framework clone:        <framework-clone>
✓ Branch:                 feat/<short-description>
✓ Commits:                <count>
✓ PR opened:              <PR URL>

Next: wait for the PR to merge, then in <adopter-repo>:
  /setup-steward upgrade
  rm .apache-steward-overrides/<skill>.md
  git add -A && git commit -m "Remove override <skill>: upstreamed in apache/airflow-steward#<N>"
```

## Failure modes

| Symptom | Likely cause | Remediation |
|---|---|---|
| `<adopter-repo>` has no `.apache-steward-overrides/` | not adopted, or adopted without the overrides scaffold | run `/setup-steward adopt` (idempotent) |
| Step 1 finds zero overrides | nothing to upstream — adopter has no local modifications recorded | stop |
| `<framework-clone>` not found | user has not cloned `apache/airflow-steward` yet | help them clone, then resume |
| Framework pre-commit fails after the implementation | the change does not match framework conventions | iterate with the user, re-run pre-commit, do not bypass with `--no-verify` |
| User decides mid-flow that the override is project-specific after all | wrong call in Step 3 | stop without opening a PR; the override file in the adopter repo is unchanged, no harm done |

## What this skill is NOT for

- Not for *applying* an override at run-time — that is the
  per-skill pre-flight protocol documented in
  [`docs/setup/agentic-overrides.md`](../../../docs/setup/agentic-overrides.md).
- Not for *creating* a new override — that is
  [`/setup-steward override <skill>`](../setup-steward/overrides.md).
- Not for *upgrading* the snapshot — that is
  [`/setup-steward upgrade`](../setup-steward/upgrade.md).
  Run that BEFORE this skill if drift exists.
- Not for arbitrary framework PRs unrelated to overrides.
  This skill is specifically the override → PR flow. Other
  framework contributions (new skill, new tool, refactor)
  go through the framework's normal PR workflow.

## Cross-references

- [`docs/setup/agentic-overrides.md`](../../../docs/setup/agentic-overrides.md) — the override contract.
- [`setup-steward/overrides.md`](../setup-steward/overrides.md) — how to *create* / *open* an override.
- [`setup-steward/upgrade.md`](../setup-steward/upgrade.md) — how to upgrade the snapshot post-merge.
