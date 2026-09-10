<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Subsystem A — committed default set: Implementation Plan](#subsystem-a--committed-default-set-implementation-plan)
  - [Global Constraints](#global-constraints)
  - [File Structure](#file-structure)
    - [Task 1: The Step M5 offer and the harness gate](#task-1-the-step-m5-offer-and-the-harness-gate)
    - [Task 2: Merge rules for `.claude/settings.json`](#task-2-merge-rules-for-claudesettingsjson)
    - [Task 3: `verify` reports a stale block; absent is not a fault](#task-3-verify-reports-a-stale-block-absent-is-not-a-fault)
    - [Task 4: `uninstall` removes only what it added](#task-4-uninstall-removes-only-what-it-added)
    - [Task 5: Documentation](#task-5-documentation)
    - [Task 6: Spec-loop acceptance criteria](#task-6-spec-loop-acceptance-criteria)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

# Subsystem A — committed default set: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `setup` offers, once and opt-in, to commit a default-plugin block to
the adopter's `.claude/settings.json` and to scaffold `.apache-magpie-overrides/`,
so a teammate cloning the repo arrives Magpie-ready — while the install stays
completely usable for anyone who declines.

**Architecture:** Every change is **prose in skill markdown**, not code. A
family-plugin install ships `.claude-plugin/` and `skills/` only — no `tools/` —
so nothing in this subsystem may depend on a Python helper being present on the
adopter's machine. The agent performs the merge itself using its own file tools,
following rules written in `install.md`. Behaviour is tested with the repo's
`skill-evals` harness, which extracts a named section from a skill file, feeds it
to a model with a fixture repo-state report, and compares the model's JSON
against `expected.json`.

**Tech Stack:** Markdown skill files; `tools/skill-evals` (pure-stdlib Python
runner); `prek` for the pre-commit hook suite; `tools/spec-loop` specs for
behaviour specification.

**Spec:** [`2026-09-10-repo-committed-setup-design.md`](2026-09-10-repo-committed-setup-design.md)

## Global Constraints

- **The floor is exactly three plugins**, verbatim:
  `magpie-setup@apache-magpie`, `magpie-utilities@apache-magpie`,
  `magpie-agent-guard@apache-magpie`. Never more, never fewer, regardless of
  what the maintainer running setup has installed.
- **The offer defaults to no** and its prompt must state that the block is
  optional and that the plugins work in the repo either way.
- **Claude Code only.** Codex can only default-install all ten families and
  Gemini has no workspace-extension mechanism; on those, say so instead of
  writing a file that does nothing.
- **Merge never clobbers:** only `extraKnownMarketplaces` and `enabledPlugins`
  are touched; an existing `apache-magpie` marketplace definition is left
  alone; missing floor members are added to an existing `enabledPlugins` and
  **nothing is ever removed**; invalid JSON stops the operation.
- **Setup may `git add`; setup never commits.**
- **The shared pre-flight is not modified by this subsystem.** A missing block
  must never read as an unadopted repo.
- **No Python helper.** No step may add a tool the adopter would need
  installed.
- Every markdown file needs the SPDX header, doctoc markers, language tags on
  fenced code (MD040) and resolvable internal anchors (MD051).
- Commit messages must end with a `Generated-by:` trailer — a repo hook
  rejects commits without one.
- Signed commits fail inside the agent sandbox with
  `No private key found for public key ...`. That is the sandbox denying reads
  under `~/.ssh`, not a missing key; retry the same `git commit` with the
  sandbox disabled.
- Eval `--cli` mode needs credentials the sandbox blocks. Run print mode inside
  the sandbox; run `--cli "claude -p"` outside it.

## File Structure

| File | Responsibility |
|---|---|
| `skills/setup/install.md` (modify, Step M5) | The offer, the harness gate, and the merge rules the agent follows |
| `skills/setup/verify.md` (modify) | Staleness reporting for a block that exists |
| `skills/setup/uninstall.md` (modify) | Removing only the keys setup added |
| `tools/skill-evals/evals/setup/` (create) | The behavioural test suite for all of the above |
| `docs/quick-start.md` (modify) | Reader-facing explanation of the optional committed set |
| `docs/setup/marketplaces.md` (modify) | Reference-side pointer that setup can write the block |
| `tools/spec-loop/specs/adoption-and-setup.md` (modify) | Acceptance criteria |

---

### Task 1: The Step M5 offer and the harness gate

**Files:**
- Create: `tools/skill-evals/evals/setup/README.md`
- Create: `tools/skill-evals/evals/setup/step-m5-repo-artefacts/fixtures/step-config.json`
- Create: `tools/skill-evals/evals/setup/step-m5-repo-artefacts/fixtures/output-spec.md`
- Create: `tools/skill-evals/evals/setup/step-m5-repo-artefacts/fixtures/user-prompt-template.md`
- Create: `tools/skill-evals/evals/setup/step-m5-repo-artefacts/fixtures/case-{1..4}-*/{case-meta.json,report.md,expected.json}`
- Modify: `skills/setup/install.md` — the `### Step M5 — Recap and what comes next` section

**Interfaces:**
- Consumes: nothing.
- Produces: the heading `### Step M5 — Recap and what comes next` keeps its
  exact text (Task 2's `step-config.json` and the existing cross-links depend
  on it), and a new `#### Merge rules` subsection anchor that Task 2 targets.

- [ ] **Step 1: Write the eval step config**

`tools/skill-evals/evals/setup/step-m5-repo-artefacts/fixtures/step-config.json`:

```json
{
  "skill_md": "skills/setup/install.md",
  "step_heading": "### Step M5 — Recap and what comes next"
}
```

- [ ] **Step 2: Write the output spec**

`tools/skill-evals/evals/setup/step-m5-repo-artefacts/fixtures/output-spec.md`:

````markdown
<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "offer_made": true | false,
  "offer_default": "no" | "yes",
  "artefacts_offered": ["settings-block", "config-store"],
  "install_complete_without": true | false
}
```

`offer_made` is `true` only when the detected agent is Claude Code. Codex CLI,
Gemini CLI, VS Code / Copilot and any other client cannot express a committed
per-family default set, so `offer_made` is `false` and `artefacts_offered` is
`[]`.

`offer_default` is `"no"` whenever an offer is made: the block is optional and
is never written without the user asking for it.

`artefacts_offered` lists both repo-side artefacts when an offer is made —
`"settings-block"` and `"config-store"` — in that order.

`install_complete_without` is always `true`. A marketplace install that writes
nothing to the repo is a finished, working install; declining the offer, or
being on a harness that cannot take it, never makes the install partial.

Do not include any text outside the JSON object.
````

- [ ] **Step 3: Write the user-prompt template**

`tools/skill-evals/evals/setup/step-m5-repo-artefacts/fixtures/user-prompt-template.md`:

```markdown
<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Install state

{report}

You are at Step M5 of the marketplace install. Decide whether to offer the
repo-side artefacts, what the offer's default is, and whether the install is
complete without them. Return JSON only.
```

- [ ] **Step 4: Write the four cases**

`case-1-claude-code-fresh/report.md`:

```markdown
Agent detected: Claude Code.
Plugins just installed: magpie-setup, magpie-pr-management (marketplace apache-magpie, tracking main).
Repo root has no `.claude/settings.json`.
Repo root has no `.apache-magpie-overrides/` directory.
No `.apache-magpie.lock` present.
```

`case-1-claude-code-fresh/expected.json`:

```json
{"offer_made": true, "offer_default": "no", "artefacts_offered": ["settings-block", "config-store"], "install_complete_without": true}
```

`case-2-codex/report.md`:

```markdown
Agent detected: OpenAI Codex CLI.
Plugins just installed: magpie (all-in-one, marketplace apache-magpie).
Repo root has no `.claude/settings.json`.
No `.apache-magpie.lock` present.
```

`case-2-codex/expected.json`:

```json
{"offer_made": false, "offer_default": "no", "artefacts_offered": [], "install_complete_without": true}
```

`case-3-gemini/report.md`:

```markdown
Agent detected: Google Gemini CLI.
Extension just installed: magpie.
Repo root has no `.claude/settings.json`.
No `.apache-magpie.lock` present.
```

`case-3-gemini/expected.json`:

```json
{"offer_made": false, "offer_default": "no", "artefacts_offered": [], "install_complete_without": true}
```

`case-4-claude-code-declined/report.md`:

```markdown
Agent detected: Claude Code.
Plugins just installed: magpie-setup, magpie-security.
The user was offered the committed default set and the config store, and declined both.
Repo root has no `.claude/settings.json`.
```

`case-4-claude-code-declined/expected.json`:

```json
{"offer_made": true, "offer_default": "no", "artefacts_offered": ["settings-block", "config-store"], "install_complete_without": true}
```

Each case also needs `case-meta.json`:

```json
{"tags":["local-smoke","smoke"]}
```

- [ ] **Step 5: Run the evals to verify they fail**

Run:

```bash
PYTHONPATH=tools/skill-evals/src python3 -m skill_evals.runner --cli "claude -p" \
    tools/skill-evals/evals/setup/step-m5-repo-artefacts/fixtures/
```

Expected: FAIL on all four cases. Step M5 currently describes the artefacts as
things the install "deliberately does not set up", so a model reading it will
not report an offer with a default.

Run this outside the agent sandbox — `claude -p` needs credentials the sandbox
blocks, and a blocked run reports ERROR rather than FAIL.

- [ ] **Step 6: Rewrite Step M5's fourth bullet as the offer**

In `skills/setup/install.md`, in `### Step M5 — Recap and what comes next`,
replace the `project-wide agentic overrides` bullet with:

```markdown
5. **Offer the repo-side artefacts — optional, once, defaulting to no.**
   **Claude Code only**; skip this entirely on any other client and say why
   (Codex can only default-install all ten families; Gemini has no
   workspace-extension mechanism), rather than writing a file that does
   nothing.

   Ask one question covering both artefacts:

   - **A committed default set** — `extraKnownMarketplaces` plus an
     `enabledPlugins` floor of `magpie-setup`, `magpie-utilities` and
     `magpie-agent-guard` in the repo's `.claude/settings.json`, so a teammate
     who clones and trusts the repo arrives with those three enabled.
   - **The config store** — `.apache-magpie-overrides/`, scaffolded exactly as
     [Step 9](#step-9--scaffold-apache-magpie-overrides-fresh-only) does, same
     exclusions and same `project.md` pre-population.

   Say in the prompt that **both are optional and neither is required to use
   the plugins in this repo** — they are a convenience for teammates. Default
   to **no**.

   The floor is fixed. It does not grow to match what this maintainer
   installed: a maintainer-only family such as `magpie-security` stays a
   personal, user-scope install.

   `git add` what you write. Never commit.

   **Declining is a finished install.** Do not describe the result as
   incomplete, partial, or pending in the recap or anywhere else.
```

- [ ] **Step 7: Run the evals to verify they pass**

Run:

```bash
PYTHONPATH=tools/skill-evals/src python3 -m skill_evals.runner --cli "claude -p" \
    tools/skill-evals/evals/setup/step-m5-repo-artefacts/fixtures/
```

Expected: PASS on all four cases.

- [ ] **Step 8: Run the hooks**

Run: `prek run --files skills/setup/install.md $(git diff --name-only --cached)`

Expected: all hooks pass. `check-doc-sync` and `markdownlint` are the two most
likely to object — the first if a cross-reference count moved, the second on an
unresolvable anchor in the new bullet.

- [ ] **Step 9: Commit**

```bash
git add skills/setup/install.md tools/skill-evals/evals/setup/
git commit -m "feat(setup): offer the committed default set on the marketplace path

Claude Code only, opt-in, defaulting to no. Both repo-side artefacts —
the enabledPlugins floor and the config store — are offered in one
question, and declining leaves a finished install.

Generated-by: Claude Opus 5"
```

---

### Task 2: Merge rules for `.claude/settings.json`

**Files:**
- Create: `tools/skill-evals/evals/setup/step-m5-settings-merge/fixtures/step-config.json`
- Create: `tools/skill-evals/evals/setup/step-m5-settings-merge/fixtures/output-spec.md`
- Create: `tools/skill-evals/evals/setup/step-m5-settings-merge/fixtures/user-prompt-template.md`
- Create: `tools/skill-evals/evals/setup/step-m5-settings-merge/fixtures/case-{1..5}-*/{case-meta.json,report.md,expected.json}`
- Modify: `skills/setup/install.md` — add `#### Merge rules` under Step M5

**Interfaces:**
- Consumes: the `### Step M5 — Recap and what comes next` section and its
  offer text from Task 1.
- Produces: a `#### Merge rules` heading, targeted verbatim by this task's
  `step-config.json`.

- [ ] **Step 1: Write the eval step config**

```json
{
  "skill_md": "skills/setup/install.md",
  "step_heading": "#### Merge rules"
}
```

- [ ] **Step 2: Write the output spec**

`output-spec.md` body, after the SPDX header:

````markdown
## Output format

Return ONLY valid JSON with this structure:

```json
{
  "action": "create" | "merge" | "refuse",
  "keys_preserved": ["<key>", "..."],
  "plugins_added": ["<plugin@marketplace>", "..."],
  "plugins_removed": [],
  "marketplace_definition_changed": true | false
}
```

`action` is `"create"` when no `.claude/settings.json` exists, `"merge"` when
one exists and parses as JSON, and `"refuse"` when one exists but does not
parse — a malformed file is reported, never rewritten.

`keys_preserved` lists every top-level key already in the file that is not
`extraKnownMarketplaces` or `enabledPlugins`, in the order they appear. On
`"create"` it is `[]`.

`plugins_added` lists only the floor members not already enabled, in floor
order: `magpie-setup@apache-magpie`, `magpie-utilities@apache-magpie`,
`magpie-agent-guard@apache-magpie`.

`plugins_removed` is always `[]`. Nothing is ever removed from an existing
`enabledPlugins`, including non-Magpie plugins and Magpie plugins outside the
floor.

`marketplace_definition_changed` is `false` when `extraKnownMarketplaces`
already defines `apache-magpie` — an adopter pinning a tag has made a
deliberate choice — and `true` only when the definition is being added for the
first time.

Do not include any text outside the JSON object.
````

- [ ] **Step 3: Write the user-prompt template**

```markdown
<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Current `.claude/settings.json`

{report}

The user accepted the offer to commit the default set. Decide how to write it.
Return JSON only.
```

- [ ] **Step 4: Write the five cases**

`case-1-no-file/report.md`:

```markdown
No `.claude/settings.json` exists in the repo root.
```

`case-1-no-file/expected.json`:

```json
{"action": "create", "keys_preserved": [], "plugins_added": ["magpie-setup@apache-magpie", "magpie-utilities@apache-magpie", "magpie-agent-guard@apache-magpie"], "plugins_removed": [], "marketplace_definition_changed": true}
```

`case-2-other-keys/report.md`:

```markdown
`.claude/settings.json` exists and parses as JSON. Its top-level keys, in order:
`$schema`, `sandbox`, `permissions`. It has no `extraKnownMarketplaces` and no
`enabledPlugins`.
```

`case-2-other-keys/expected.json`:

```json
{"action": "merge", "keys_preserved": ["$schema", "sandbox", "permissions"], "plugins_added": ["magpie-setup@apache-magpie", "magpie-utilities@apache-magpie", "magpie-agent-guard@apache-magpie"], "plugins_removed": [], "marketplace_definition_changed": true}
```

`case-3-existing-plugins/report.md`:

```markdown
`.claude/settings.json` exists and parses as JSON. Top-level keys, in order:
`permissions`, `enabledPlugins`. `enabledPlugins` currently contains
`magpie-setup@apache-magpie: true`, `magpie-security@apache-magpie: true` and
`some-other-plugin@vendor-marketplace: true`. There is no
`extraKnownMarketplaces`.
```

`case-3-existing-plugins/expected.json`:

```json
{"action": "merge", "keys_preserved": ["permissions"], "plugins_added": ["magpie-utilities@apache-magpie", "magpie-agent-guard@apache-magpie"], "plugins_removed": [], "marketplace_definition_changed": true}
```

`case-4-pinned-marketplace/report.md`:

```markdown
`.claude/settings.json` exists and parses as JSON. Top-level keys, in order:
`extraKnownMarketplaces`, `enabledPlugins`. `extraKnownMarketplaces` defines
`apache-magpie` with `{"source": {"source": "github", "repo": "apache/magpie@0.2.0"}}`.
`enabledPlugins` contains `magpie-setup@apache-magpie: true`.
```

`case-4-pinned-marketplace/expected.json`:

```json
{"action": "merge", "keys_preserved": [], "plugins_added": ["magpie-utilities@apache-magpie", "magpie-agent-guard@apache-magpie"], "plugins_removed": [], "marketplace_definition_changed": false}
```

`case-5-malformed/report.md`:

```markdown
`.claude/settings.json` exists but does not parse: it ends mid-object after a
trailing comma on the `permissions` key.
```

`case-5-malformed/expected.json`:

```json
{"action": "refuse", "keys_preserved": [], "plugins_added": [], "plugins_removed": [], "marketplace_definition_changed": false}
```

Each case needs `case-meta.json` with `{"tags":["local-smoke","smoke"]}`.

- [ ] **Step 5: Run the evals to verify they fail**

Run:

```bash
PYTHONPATH=tools/skill-evals/src python3 -m skill_evals.runner --cli "claude -p" \
    tools/skill-evals/evals/setup/step-m5-settings-merge/fixtures/
```

Expected: ERROR with `Heading '#### Merge rules' not found in
skills/setup/install.md` — the section does not exist yet.

- [ ] **Step 6: Write the merge rules**

Append to `### Step M5 — Recap and what comes next` in `skills/setup/install.md`:

```markdown
#### Merge rules

`.claude/settings.json` is not Magpie's file. This repository's own carries
`sandbox` and `permissions` blocks; an adopter's will carry whatever they put
there. When the user accepts the offer:

- **Touch only two keys** — `extraKnownMarketplaces` and `enabledPlugins`.
  Every other top-level key is preserved exactly as it was.
- **Leave an existing `apache-magpie` marketplace definition alone.** An
  adopter pinning `apache/magpie@0.2.0` has made a deliberate choice; do not
  rewrite it to track `main`.
- **Add missing floor members to an existing `enabledPlugins`, and remove
  nothing** — not other Magpie plugins, not other vendors' plugins.
- **If the file does not exist**, create it with those two keys and nothing
  else.
- **If the file exists but does not parse as JSON, stop and say so.** Do not
  rewrite a file you cannot read; a malformed settings file is the user's to
  fix.

Then `git add .claude/settings.json`. Never commit it.
```

- [ ] **Step 7: Run the evals to verify they pass**

Run:

```bash
PYTHONPATH=tools/skill-evals/src python3 -m skill_evals.runner --cli "claude -p" \
    tools/skill-evals/evals/setup/step-m5-settings-merge/fixtures/
```

Expected: PASS on all five cases. Case 5 is the one most likely to fail first —
if the model reports `"merge"` for malformed JSON, the refuse rule needs to be
stated earlier in the section, not last.

- [ ] **Step 8: Commit**

```bash
git add skills/setup/install.md tools/skill-evals/evals/setup/
git commit -m "feat(setup): merge-never-clobber rules for the committed default set

Only extraKnownMarketplaces and enabledPlugins are touched; an existing
apache-magpie definition is left alone; floor members are added and
nothing is removed; a malformed file is reported, never rewritten.

Generated-by: Claude Opus 5"
```

---

### Task 3: `verify` reports a stale block; absent is not a fault

**Files:**
- Create: `tools/skill-evals/evals/setup/verify-default-set/fixtures/{step-config.json,output-spec.md,user-prompt-template.md}`
- Create: `tools/skill-evals/evals/setup/verify-default-set/fixtures/case-{1..3}-*/{case-meta.json,report.md,expected.json}`
- Modify: `skills/setup/verify.md`

**Interfaces:**
- Consumes: the floor definition from Task 1.
- Produces: a `## Committed default set` heading in `verify.md`, targeted by
  this task's `step-config.json`.

- [ ] **Step 1: Write the eval step config**

```json
{
  "skill_md": "skills/setup/verify.md",
  "step_heading": "## Committed default set"
}
```

- [ ] **Step 2: Write the output spec**

`output-spec.md` body, after the SPDX header:

````markdown
## Output format

Return ONLY valid JSON with this structure:

```json
{
  "status": "absent" | "current" | "stale",
  "is_fault": true | false,
  "missing": ["<plugin@marketplace>", "..."]
}
```

`status` is `"absent"` when the repo commits no `enabledPlugins` block,
`"current"` when it commits all three floor members, and `"stale"` when it
commits some but not all of them.

`is_fault` is `true` **only** for `"stale"`. An absent block is a supported,
deliberate end state — the committed default set is optional and is not
required to use the plugins — so `"absent"` is reported informationally and
never counted as a failed check.

`missing` lists the floor members not present, in floor order. It is `[]` for
`"current"`, and `[]` for `"absent"` — there is no block to be missing members
from.

Do not include any text outside the JSON object.
````

- [ ] **Step 3: Write the user-prompt template**

```markdown
<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Repo state

{report}

You are running the committed-default-set check of `setup verify`. Report its
status. Return JSON only.
```

- [ ] **Step 4: Write the three cases**

`case-1-absent/report.md`:

```markdown
`.claude/settings.json` exists with `sandbox` and `permissions` keys. It has no
`enabledPlugins` key. The user has magpie-setup and magpie-pr-management
installed at user scope.
```

`case-1-absent/expected.json`:

```json
{"status": "absent", "is_fault": false, "missing": []}
```

`case-2-current/report.md`:

```markdown
`.claude/settings.json` commits `enabledPlugins` with
`magpie-setup@apache-magpie`, `magpie-utilities@apache-magpie` and
`magpie-agent-guard@apache-magpie`, all `true`.
```

`case-2-current/expected.json`:

```json
{"status": "current", "is_fault": false, "missing": []}
```

`case-3-stale/report.md`:

```markdown
`.claude/settings.json` commits `enabledPlugins` with
`magpie-setup@apache-magpie: true` and `magpie-utilities@apache-magpie: true`.
There is no `magpie-agent-guard@apache-magpie` entry.
```

`case-3-stale/expected.json`:

```json
{"status": "stale", "is_fault": true, "missing": ["magpie-agent-guard@apache-magpie"]}
```

Each case needs `case-meta.json` with `{"tags":["local-smoke","smoke"]}`.

- [ ] **Step 5: Run the evals to verify they fail**

Run:

```bash
PYTHONPATH=tools/skill-evals/src python3 -m skill_evals.runner --cli "claude -p" \
    tools/skill-evals/evals/setup/verify-default-set/fixtures/
```

Expected: ERROR with `Heading '## Committed default set' not found in
skills/setup/verify.md`.

- [ ] **Step 6: Write the verify check**

Add to `skills/setup/verify.md`:

```markdown
## Committed default set

Read `.claude/settings.json` at the repo root and compare its `enabledPlugins`
against the floor: `magpie-setup@apache-magpie`,
`magpie-utilities@apache-magpie`, `magpie-agent-guard@apache-magpie`.

- **No `enabledPlugins` key** — report it in one line as available but not in
  use, and move on. **This is not a fault.** The committed default set is
  optional and is not required to use the plugins in this repo; a project that
  never took the offer, or took it and later removed it, is correctly
  configured. Do not count it as a failed check, and do not re-offer it here —
  `setup` is where the offer lives.
- **All three present** — report current.
- **Some but not all present** — report drift, name the missing members, and
  offer to add them under the merge rules in
  [`install.md`](install.md#merge-rules). This is the case a framework release
  that changes the floor produces.
- **A member naming a plugin the marketplace no longer ships** — report it the
  same way and offer to drop that entry.
```

- [ ] **Step 7: Run the evals to verify they pass**

Run:

```bash
PYTHONPATH=tools/skill-evals/src python3 -m skill_evals.runner --cli "claude -p" \
    tools/skill-evals/evals/setup/verify-default-set/fixtures/
```

Expected: PASS on all three cases. Case 1 is the one that matters — a model
reporting `is_fault: true` for an absent block means the optionality is not
stated strongly enough.

- [ ] **Step 8: Commit**

```bash
git add skills/setup/verify.md tools/skill-evals/evals/setup/
git commit -m "feat(setup): verify reports a stale committed default set

An absent block is reported informationally and is never a fault — the
committed set is optional. A block missing floor members is drift, with
a repair offer.

Generated-by: Claude Opus 5"
```

---

### Task 4: `uninstall` removes only what it added

**Files:**
- Create: `tools/skill-evals/evals/setup/uninstall-default-set/fixtures/{step-config.json,output-spec.md,user-prompt-template.md}`
- Create: `tools/skill-evals/evals/setup/uninstall-default-set/fixtures/case-{1,2}-*/{case-meta.json,report.md,expected.json}`
- Modify: `skills/setup/uninstall.md`

**Interfaces:**
- Consumes: the floor definition from Task 1 and the merge rules from Task 2.
- Produces: a `## Committed default set` heading in `uninstall.md`.

- [ ] **Step 1: Write the eval step config**

```json
{
  "skill_md": "skills/setup/uninstall.md",
  "step_heading": "## Committed default set"
}
```

- [ ] **Step 2: Write the output spec**

`output-spec.md` body, after the SPDX header:

````markdown
## Output format

Return ONLY valid JSON with this structure:

```json
{
  "plugins_removed": ["<plugin@marketplace>", "..."],
  "plugins_kept": ["<plugin@marketplace>", "..."],
  "keys_preserved": ["<key>", "..."],
  "file_deleted": false
}
```

`plugins_removed` lists only the floor members setup added, in floor order.

`plugins_kept` lists every other entry in `enabledPlugins` — Magpie plugins
outside the floor and other vendors' plugins alike. Uninstall removes what it
added and nothing else.

`keys_preserved` lists every top-level key other than `enabledPlugins` and
`extraKnownMarketplaces`.

`file_deleted` is always `false`. `.claude/settings.json` belongs to the
project, not to Magpie; uninstall empties its own keys and leaves the file.

Do not include any text outside the JSON object.
````

- [ ] **Step 3: Write the user-prompt template**

```markdown
<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Current `.claude/settings.json`

{report}

You are uninstalling Magpie from this repo. Decide what to remove from the
settings file. Return JSON only.
```

- [ ] **Step 4: Write the two cases**

`case-1-floor-only/report.md`:

```markdown
Top-level keys, in order: `$schema`, `sandbox`, `extraKnownMarketplaces`,
`enabledPlugins`. `enabledPlugins` contains exactly the three floor members,
all `true`.
```

`case-1-floor-only/expected.json`:

```json
{"plugins_removed": ["magpie-setup@apache-magpie", "magpie-utilities@apache-magpie", "magpie-agent-guard@apache-magpie"], "plugins_kept": [], "keys_preserved": ["$schema", "sandbox"], "file_deleted": false}
```

`case-2-mixed/report.md`:

```markdown
Top-level keys, in order: `permissions`, `enabledPlugins`. `enabledPlugins`
contains the three floor members plus `magpie-security@apache-magpie: true` and
`some-other-plugin@vendor-marketplace: true`.
```

`case-2-mixed/expected.json`:

```json
{"plugins_removed": ["magpie-setup@apache-magpie", "magpie-utilities@apache-magpie", "magpie-agent-guard@apache-magpie"], "plugins_kept": ["magpie-security@apache-magpie", "some-other-plugin@vendor-marketplace"], "keys_preserved": ["permissions"], "file_deleted": false}
```

Each case needs `case-meta.json` with `{"tags":["local-smoke","smoke"]}`.

- [ ] **Step 5: Run the evals to verify they fail**

Run:

```bash
PYTHONPATH=tools/skill-evals/src python3 -m skill_evals.runner --cli "claude -p" \
    tools/skill-evals/evals/setup/uninstall-default-set/fixtures/
```

Expected: ERROR with `Heading '## Committed default set' not found in
skills/setup/uninstall.md`.

- [ ] **Step 6: Write the uninstall step**

Add to `skills/setup/uninstall.md`:

```markdown
## Committed default set

If `.claude/settings.json` commits the block, remove **only** what setup added:

- Delete the three floor entries from `enabledPlugins` —
  `magpie-setup@apache-magpie`, `magpie-utilities@apache-magpie`,
  `magpie-agent-guard@apache-magpie`. Keep every other entry, including Magpie
  plugins outside the floor and other vendors' plugins.
- Delete the `apache-magpie` entry from `extraKnownMarketplaces`, keeping any
  other marketplace.
- If either key is left empty, remove the empty key.
- **Never delete the file** and never touch any other top-level key. The
  settings file belongs to the project.

This mirrors the existing rule that `.apache-magpie-overrides/` is preserved by
default: uninstall reverses Magpie's own additions, not the project's
configuration.
```

- [ ] **Step 7: Run the evals to verify they pass**

Run:

```bash
PYTHONPATH=tools/skill-evals/src python3 -m skill_evals.runner --cli "claude -p" \
    tools/skill-evals/evals/setup/uninstall-default-set/fixtures/
```

Expected: PASS on both cases.

- [ ] **Step 8: Commit**

```bash
git add skills/setup/uninstall.md tools/skill-evals/evals/setup/
git commit -m "feat(setup): uninstall removes only the floor it added

Other plugins in enabledPlugins survive, other marketplaces survive, the
settings file is never deleted.

Generated-by: Claude Opus 5"
```

---

### Task 5: Documentation

**Files:**
- Modify: `docs/quick-start.md` — new subsection under `### Claude Code`
- Modify: `docs/setup/marketplaces.md` — the `### Claude Code: the default set` section

**Interfaces:**
- Consumes: the behaviour from Tasks 1–4.
- Produces: no anchors other tasks depend on.

- [ ] **Step 1: Add the quick-start subsection**

After the Claude Code install block in `docs/quick-start.md`, add:

```markdown
#### Optional: commit a default set for your teammates

Everything above installs Magpie for **you, on this machine** — nothing is
written to the repository, and your teammates are unaffected.

A project can go one step further and commit a small block to its
`.claude/settings.json` naming the marketplace and three plugins, so anyone who
clones the repo and trusts it arrives with `magpie-setup`, `magpie-utilities`
and `magpie-agent-guard` already enabled. `/magpie-setup` offers to write it —
see [the default set](setup/marketplaces.md#claude-code-the-default-set).

**This is entirely optional.** The plugins work in the repo whether or not the
block is committed, and a project that never commits it is not missing
anything: the install you just did is complete. It is a convenience for
teams — nobody has to run the install by hand — not a requirement.
```

- [ ] **Step 2: Add the marketplaces.md pointer**

In `docs/setup/marketplaces.md`, immediately after the JSON block in
`### Claude Code: the default set`, add:

```markdown
> [!TIP]
> `/magpie-setup` offers to write this block for you at the end of a
> marketplace install, and `/magpie-setup verify` reports it if it falls
> behind a later release's floor. Both are opt-in: the block is a convenience
> for teammates, never a prerequisite, and declining leaves a complete,
> working install.
```

- [ ] **Step 3: Run the hooks**

Run:

```bash
prek run --files docs/quick-start.md docs/setup/marketplaces.md
```

Expected: all pass. `doctoc` will rewrite both TOCs to include the new
headings — stage the result. `markdownlint` MD051 will fail if the
`setup/marketplaces.md#claude-code-the-default-set` anchor is wrong; confirm it
against the heading text.

- [ ] **Step 4: Commit**

```bash
git add docs/quick-start.md docs/setup/marketplaces.md
git commit -m "docs: explain the optional committed default set

Says plainly in both places that committing the block is optional and
that the plugins work in the repo either way.

Generated-by: Claude Opus 5"
```

---

### Task 6: Spec-loop acceptance criteria

**Files:**
- Modify: `tools/spec-loop/specs/adoption-and-setup.md` — the `acceptance:` list

**Interfaces:**
- Consumes: the behaviour from Tasks 1–4.
- Produces: nothing.

- [ ] **Step 1: Add the acceptance criteria**

Append to the `acceptance:` list in the frontmatter of
`tools/spec-loop/specs/adoption-and-setup.md`:

```yaml
  - A marketplace install on Claude Code offers once, opt-in and defaulting to
    no, to commit the default-set block and scaffold the config store; the
    offer states that both are optional and that the plugins work in the repo
    either way.
  - Declining the offer, or running on a harness that cannot express it,
    leaves a complete install; neither the recap nor verify describes the
    result as incomplete or partial.
  - Writing the block preserves every other key in an existing
    .claude/settings.json, leaves an existing apache-magpie marketplace
    definition alone, adds only missing floor members to an existing
    enabledPlugins, removes nothing, and refuses to rewrite a settings file
    that does not parse.
  - verify reports a committed block that is missing floor members as drift
    with a repair offer, and reports an absent block informationally without
    counting it as a fault.
  - uninstall removes only the floor entries and the apache-magpie marketplace
    entry, keeps every other plugin and marketplace, and never deletes
    .claude/settings.json.
```

- [ ] **Step 2: Validate the spec**

Run:

```bash
prek run spec-validate --files tools/spec-loop/specs/adoption-and-setup.md
```

Expected: PASS. The hook checks frontmatter shape and required sections; a YAML
indentation slip in the appended list is the likely failure.

- [ ] **Step 3: Commit**

```bash
git add tools/spec-loop/specs/adoption-and-setup.md
git commit -m "spec(adoption): acceptance criteria for the committed default set

Generated-by: Claude Opus 5"
```
