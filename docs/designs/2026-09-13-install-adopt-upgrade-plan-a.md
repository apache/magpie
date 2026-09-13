<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Subsystem A — the adoption floor: Implementation Plan](#subsystem-a--the-adoption-floor-implementation-plan)
  - [Global Constraints](#global-constraints)
  - [File Structure](#file-structure)
    - [Task 1: The `method: marketplace` record in `locks.md`](#task-1-the-method-marketplace-record-in-locksmd)
    - [Task 2: `adopt` writes the floor](#task-2-adopt-writes-the-floor)
    - [Task 3: `setup` arrives pre-filled from the floor](#task-3-setup-arrives-pre-filled-from-the-floor)
    - [Task 4: The pre-flight brings a machine up to the floor](#task-4-the-pre-flight-brings-a-machine-up-to-the-floor)
    - [Task 5: `upgrade` splits on adoption](#task-5-upgrade-splits-on-adoption)
    - [Task 6: `verify`, `status`, `unadopt` and `uninstall`](#task-6-verify-status-unadopt-and-uninstall)
    - [Task 7: Specification, docs and suite bookkeeping](#task-7-specification-docs-and-suite-bookkeeping)
  - [Self-review](#self-review)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Subsystem A — the adoption floor: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the marketplace install a committed adoption record —
`method: marketplace` in `.apache-magpie.lock`, carrying a `min_version` and a
plugin list that are both **floors** — so `adopt` writes it, `setup` pre-fills
from it, `upgrade` raises it, and every skill's pre-flight brings a machine up
to it.

**Architecture:** Every behavioural change is **prose in skill markdown**, not
code. A family-plugin install ships `.claude-plugin/` and `skills/` only — no
`tools/` — so nothing here may depend on a Python helper existing on the
adopter's machine. The agent reads the rules and performs the file edits and
CLI calls itself. Behaviour is tested with the repo's `skill-evals` harness,
which extracts a named heading's section from a skill file, feeds it to a model
along with a fixture repo-state report, and compares the model's JSON against
`expected.json`. The only Python touched is `tools/dev/preflight-block.md`'s
generator, which already exists and already runs `--fix` from the pre-commit
hook.

**Tech Stack:** Markdown skill files; `tools/skill-evals` (pure-stdlib Python
runner); `tools/dev/check-skill-preflight.py --fix` for block propagation;
`prek` for the pre-commit hook suite; `tools/spec-loop` specs for behaviour
specification.

**Spec:** [`2026-09-13-install-adopt-upgrade-design.md`](2026-09-13-install-adopt-upgrade-design.md)

## Global Constraints

- **`min_version` and `plugins` are floors, never pins.** Installed plugins may
  be newer. Nothing is ever downgraded, removed, or pinned, and the
  `extraKnownMarketplaces` entry is written **untagged** (`apache/magpie`, no
  `@version` suffix).
- **The seed floor is exactly three plugins**, verbatim: `magpie-setup`,
  `magpie-utilities`, `magpie-agent-guard`. A maintainer may add to it; nothing
  adds to it automatically, and installing another family never changes it.
- **`min_version` only ever rises.** No operation in this plan lowers it.
- **Version comparison is PEP 440**, not string ordering. `0.10.0` satisfies a
  `0.9.0` floor; `0.2.0` satisfies a `0.2.0.dev202609110041` floor.
- **One framework version, not per-plugin.** Every Magpie plugin's version
  tracks `pyproject.toml`, so `min_version` is a single framework version.
- **Auto-install only for `url: apache/magpie`.** Any other value is reported
  and explicitly confirmed before anything runs. This is a security boundary,
  not a nicety — see the design's Risks section.
- **The pre-flight never** removes a plugin, downgrades one, pins a
  marketplace, or touches a plugin absent from the committed floor.
- **`.claude/settings.json` is derived from the lock**, and the existing merge
  rules stand unchanged: only `extraKnownMarketplaces` and `enabledPlugins` are
  touched, an existing `apache-magpie` definition is left alone, missing floor
  members are added and **nothing is ever removed**, invalid JSON stops the
  operation without rewriting.
- **Setup may `git add`; setup never commits.**
- **Do not rename `### Merge rules` in `adopt.md`.** The existing
  `step-adopt-settings-merge` eval suite keys on that exact heading.
- **No Python helper on the adopter's machine.** No step may add a tool an
  adopter would need installed.
- **The three snapshot methods are untouched.** `svn-zip`, `git-tag` and
  `git-branch` keep `ref` and keep pinning. This plan *adds* a fourth method.
- Every markdown file needs the SPDX header, doctoc markers, language tags on
  fenced code (MD040) and resolvable internal anchors (MD051).
- Commit messages must end with a `Generated-by:` trailer — a repo hook rejects
  commits without one.
- Signed commits fail inside the agent sandbox with `Couldn't load public key
  ...`. That is the sandbox denying reads under `~/.ssh`, not a missing key;
  retry the same `git commit` with the sandbox disabled.
- Eval `--cli` mode needs credentials the sandbox blocks. Run print mode inside
  the sandbox; run `--cli "claude -p"` outside it.

## File Structure

| File | Responsibility |
|---|---|
| `skills/setup/locks.md` (modify) | The `method: marketplace` record: its fields, floor-not-pin semantics, and PEP 440 comparison |
| `skills/setup/adopt.md` (modify) | Writing the floor lock, and deriving the wiring from it |
| `skills/setup/SKILL.md` (modify) | Routing: the fourth method in the paths table; the pre-fill behaviour |
| `skills/setup/install.md` (modify) | Step M5's offer becomes a pointer to `adopt`; pre-fill on an adopted repo |
| `skills/setup/upgrade.md` (modify) | The adoption split: nothing repo-side when unadopted, raise the floor when adopted |
| `skills/setup/verify.md` (modify) | Floor reporting; ahead-of-floor is not drift |
| `skills/setup/uninstall.md` (modify) | `unadopt` removes the lock; `uninstall` leaves it |
| `skills/setup-status/render.md` (modify) | Print the floor beside the installed set |
| `tools/dev/preflight-block.md` (modify) | The floor check, propagated into 65 `SKILL.md` copies by `--fix` |
| `tools/skill-evals/evals/setup/lock-marketplace-parse/` (create) | Task 1's behavioural test |
| `tools/skill-evals/evals/setup/adopt-write-floor/` (create) | Task 2's |
| `tools/skill-evals/evals/setup/setup-prefill-from-floor/` (create) | Task 3's |
| `tools/skill-evals/evals/setup/preflight-floor/` (create) | Task 4's |
| `tools/skill-evals/evals/setup/upgrade-adoption-split/` (create) | Task 5's |
| `tools/skill-evals/evals/setup/verify-floor/` (create) | Task 6's |
| `tools/skill-evals/evals/setup/README.md` (modify) | Suite table and case counts |
| `tools/spec-loop/specs/adoption-and-setup.md` (modify) | Acceptance criteria |
| `docs/setup/team-adoption.md`, `docs/setup/individual-use.md` (modify) | Reader-facing description of the floor |

**Not in this plan.** `docs/quick-start.md`, the per-harness prerequisite page,
and the family READMEs belong to Subsystem B. The screenshots and callouts
belong to Subsystem C.

---

### Task 1: The `method: marketplace` record in `locks.md`

`locks.md` is the reference every other step in this plan reads. It currently
opens by saying lock files exist *only* on the pinned snapshot install — the
single sentence this whole subsystem changes.

**Files:**
- Modify: `skills/setup/locks.md:4-8` (the "only on the pinned snapshot
  install" opening) and after `skills/setup/locks.md:44` (a new section before
  `## <local-lock>`)
- Create: `tools/skill-evals/evals/setup/lock-marketplace-parse/fixtures/step-config.json`
- Create: `tools/skill-evals/evals/setup/lock-marketplace-parse/fixtures/output-spec.md`
- Create: `tools/skill-evals/evals/setup/lock-marketplace-parse/fixtures/user-prompt-template.md`
- Create: `tools/skill-evals/evals/setup/lock-marketplace-parse/fixtures/case-{1..5}-*/`

**Interfaces:**
- Consumes: nothing — this is the first task.
- Produces: the heading `## `method: marketplace` — the adoption floor`, which
  Tasks 2–6 cross-reference as `[locks.md](locks.md#method-marketplace--the-adoption-floor)`;
  the field names `method`, `url`, `min_version`, `plugins`; and the three
  verdict strings `satisfied` / `below-floor` / `plugin-missing` that Tasks 4
  and 6 reuse verbatim.

- [ ] **Step 1: Write the failing eval fixtures**

Create `tools/skill-evals/evals/setup/lock-marketplace-parse/fixtures/step-config.json`:

```json
{
  "skill_md": "skills/setup/locks.md",
  "step_heading": "## `method: marketplace` — the adoption floor"
}
```

Create `fixtures/output-spec.md`:

````markdown
<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "verdict": "satisfied" | "below-floor" | "plugin-missing" | "not-marketplace" | "malformed",
  "is_pin": true | false,
  "needs": [...]
}
```

`verdict` reports how the machine's installed state stands against the lock,
per the rules in the section above. `not-marketplace` is for a lock using one
of the three snapshot methods; `malformed` is for a lock this section's rules
cannot read.

`is_pin` reports whether this lock pins an exact version — that is, whether a
machine running a *newer* version than the lock names is out of compliance.

`needs` is a list of plugin names that must be installed or updated to reach
the floor, in floor order. Empty when nothing is needed.

Do not include any text outside the JSON object.
````

Create `fixtures/user-prompt-template.md`:

```markdown
<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Repo and machine state

{report}

You are reading the project's committed lock to decide how this machine stands
against it. Return JSON only.
```

- [ ] **Step 2: Write the five cases**

Each case is a directory under `fixtures/`. Every `case-meta.json` is
`{"tags":["local-smoke","smoke"]}`.

`case-1-ahead-of-floor/report.md`:

````markdown
<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

`.apache-magpie.lock` at the repo root contains:

    method:       marketplace
    url:          apache/magpie
    min_version:  0.2.0

    plugins:
      - magpie-setup
      - magpie-utilities
      - magpie-agent-guard

`claude plugin list --json` reports magpie-setup 0.4.0, magpie-utilities 0.4.0,
magpie-agent-guard 0.4.0, and magpie-security 0.4.0, all from the
`apache-magpie` marketplace.
```

`case-1-ahead-of-floor/expected.json`:

```json
{"verdict": "satisfied", "is_pin": false, "needs": []}
```

`case-2-dev-floor-met-by-release/report.md` — the PEP 440 case:

```markdown
<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

`.apache-magpie.lock` at the repo root contains:

    method:       marketplace
    url:          apache/magpie
    min_version:  0.2.0.dev202609110041

    plugins:
      - magpie-setup
      - magpie-utilities
      - magpie-agent-guard

`claude plugin list --json` reports all three plugins at version 0.2.0 from the
`apache-magpie` marketplace.
```

`case-2-dev-floor-met-by-release/expected.json`:

```json
{"verdict": "satisfied", "is_pin": false, "needs": []}
```

`case-3-below-floor/report.md`:

```markdown
<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

`.apache-magpie.lock` at the repo root contains:

    method:       marketplace
    url:          apache/magpie
    min_version:  0.10.0

    plugins:
      - magpie-setup
      - magpie-utilities
      - magpie-agent-guard

`claude plugin list --json` reports all three plugins at version 0.9.0 from the
`apache-magpie` marketplace.
```

`case-3-below-floor/expected.json` — this case is the string-ordering trap; a
naive comparison reads `0.9.0` as newer than `0.10.0`:

```json
{"verdict": "below-floor", "is_pin": false,
 "needs": ["magpie-setup", "magpie-utilities", "magpie-agent-guard"]}
```

`case-4-plugin-missing/report.md`:

```markdown
<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

`.apache-magpie.lock` at the repo root contains:

    method:       marketplace
    url:          apache/magpie
    min_version:  0.2.0

    plugins:
      - magpie-setup
      - magpie-utilities
      - magpie-agent-guard

`claude plugin list --json` reports magpie-setup 0.3.0 and magpie-utilities
0.3.0 from the `apache-magpie` marketplace. No other plugins are installed.
```

`case-4-plugin-missing/expected.json`:

```json
{"verdict": "plugin-missing", "is_pin": false, "needs": ["magpie-agent-guard"]}
```

`case-5-git-tag-still-pins/report.md` — guards the constraint that the three
snapshot methods keep pinning:

```markdown
<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

`.apache-magpie.lock` at the repo root contains:

    method: git-tag
    url:    https://github.com/apache/magpie.git
    ref:    v0.2.0
    commit: 4f1c9ab2d3e5f60718293a4b5c6d7e8f90a1b2c3

`.apache-magpie.local.lock` records `source_ref: v0.4.0` and
`fetched_commit: aa11bb22cc33dd44ee55ff6677889900aabbccdd`.
```

`case-5-git-tag-still-pins/expected.json` — a newer fetched version *is* drift
here, which is exactly the difference from case 1:

```json
{"verdict": "not-marketplace", "is_pin": true, "needs": []}
````

- [ ] **Step 3: Run the evals to verify they fail**

Run, from the repo root and **outside the sandbox** (the CLI needs credentials
the sandbox blocks):

```bash
uv run --directory tools/skill-evals skill-eval --cli "claude -p" \
    evals/setup/lock-marketplace-parse/
```

Expected: the runner fails to extract the section, reporting that the heading
`## \`method: marketplace\` — the adoption floor` is not present in
`skills/setup/locks.md`.

- [ ] **Step 4: Rewrite the opening of `locks.md`**

Replace lines 4–8 — currently the claim that lock files exist only on the
snapshot install — with:

```markdown
# locks — the committed record and the local fingerprint

Every **adopted** project has one committed lock, whatever install
method it uses. What the lock means depends on the method:

| Method | The committed lock is | A newer local version is |
|---|---|---|
| `marketplace` | a **floor** — the minimum the project expects | fine, and reported as nothing |
| `svn-zip` / `git-tag` / `git-branch` | a **pin** — the exact version to re-fetch | **drift**, to be reconciled |

The second lock, `<local-lock>`, exists only on the three snapshot
methods: it fingerprints what this machine fetched. A marketplace
install has no local lock, because the agent's plugin manager already
knows what is installed and `claude plugin list --json` reports it.
```

- [ ] **Step 5: Add the new section**

Insert after the `## <committed-lock>` section's per-method format block (after
line 44, before `## <local-lock>`):

````markdown
## `method: marketplace` — the adoption floor

```text
# .apache-magpie.lock — committed; the project's floor.

method:       marketplace
url:          apache/magpie
min_version:  0.2.0

plugins:
  - magpie-setup
  - magpie-utilities
  - magpie-agent-guard
```

Read it as: *this project expects at least Magpie `min_version`, and
expects at least these plugins to be available.*

**Neither line is a ceiling.** A contributor running 0.4.0 with seven
families installed satisfies this lock completely and is told nothing.
Nothing downgrades a plugin, removes one, or pins the marketplace to
`min_version` — the `extraKnownMarketplaces` entry derived from this
lock is written **untagged**, so contributors track the tip and meet
the floor by default.

`min_version` rather than `ref` is deliberate. On `git-tag` and
`svn-zip`, `ref` **is** a pin and re-fetching that exact version is the
point; reusing the key here would put two opposite meanings under one
name in one file.

### Deciding how a machine stands

1. **`method` is not `marketplace`** → `not-marketplace`. The three
   snapshot methods pin; their rules are above, not here.
2. **`method`, `url`, `min_version` or `plugins` is missing or
   unparsable** → `malformed`. Do not guess at a lock you cannot read.
3. **A plugin in `plugins` is not installed** → `plugin-missing`, and
   it goes in `needs`.
4. **An installed plugin's version is below `min_version`** →
   `below-floor`, and it goes in `needs`.
5. **Otherwise** → `satisfied`, `needs` empty.

`plugin-missing` wins over `below-floor` when both are true: a plugin
that is absent has no version to be behind.

**Compare versions as PEP 440, never as strings.** `0.10.0` is *newer*
than `0.9.0`, and `0.2.0` is newer than `0.2.0.dev202609110041` — a
maintainer who adopted mid-cycle against a `.dev` build is correctly
satisfied by the release that follows it. String ordering gets both of
these backwards.

**One version, not per-plugin.** Every Magpie plugin's version tracks
the framework's `pyproject.toml`, so `min_version` is a single
framework version rather than a per-plugin constraint.

### `url` is a security boundary

`url` names the marketplace the floor's plugins come from. Any
automated action taken on this lock's behalf — see the pre-flight in
every skill — runs **without asking only when `url` is
`apache/magpie`**. Any other value is reported and explicitly
confirmed first.

A lock is a committed file in whatever repository the user happened to
open. Treating it as authority to install from an arbitrary marketplace
would make opening a repository enough to install an attacker's code.
````

- [ ] **Step 6: Run the evals to verify they pass**

```bash
uv run --directory tools/skill-evals skill-eval --cli "claude -p" \
    evals/setup/lock-marketplace-parse/
```

Expected: 5/5 cases pass. Case 3 (`0.9.0` against a `0.10.0` floor) and case 5
(`git-tag` newer local is drift) are the two that catch a misread of the rules.

- [ ] **Step 7: Commit**

```bash
git add skills/setup/locks.md tools/skill-evals/evals/setup/lock-marketplace-parse/
git commit -m "feat(setup): give the lock a marketplace method carrying a floor

Lock files existed only on the pinned-snapshot install, so the marketplace
path -- the default one -- recorded nothing about the version a project
adopted against.

method: marketplace joins the three snapshot methods, carrying min_version
and a plugin list that are both floors rather than pins: a contributor ahead
of them is told nothing, and nothing is ever downgraded, removed, or pinned.
Comparison is PEP 440, so 0.10.0 reads as newer than 0.9.0 and a .dev floor
is satisfied by the release that follows it.

url is a security boundary: automated action on a lock's behalf runs without
asking only for apache/magpie, because a lock is a committed file in whatever
repository the user happened to open.

Generated-by: Claude Opus 5"
```

---

### Task 2: `adopt` writes the floor

**Files:**
- Modify: `skills/setup/adopt.md` — insert a new `## Step 2 — Write the floor
  lock`; renumber the existing Steps 2/3/4 to 3/4/5, **keeping `### Merge
  rules` spelled exactly as it is**
- Create: `tools/skill-evals/evals/setup/adopt-write-floor/fixtures/`

**Interfaces:**
- Consumes: from Task 1 — the field names `method` / `url` / `min_version` /
  `plugins`, and the untagged-marketplace rule.
- Produces: the heading `## Step 2 — Write the floor lock`; the rule that
  `min_version` is the version installed on this machine at adopt time; the
  JSON keys `min_version`, `plugins`, `wrote_lock`, `marketplace_tagged` that
  Task 6's `verify-floor` suite reuses.

- [ ] **Step 1: Write the failing eval fixtures**

`fixtures/step-config.json`:

```json
{
  "skill_md": "skills/setup/adopt.md",
  "step_heading": "## Step 2 — Write the floor lock"
}
```

`fixtures/output-spec.md`:

````markdown
<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "wrote_lock": true | false,
  "min_version": "<version string, or null>",
  "plugins": [...],
  "marketplace_tagged": true | false
}
```

`wrote_lock` reports whether this step writes `.apache-magpie.lock` at all.

`min_version` is the value written into it, or `null` if no lock is written.

`plugins` is the floor written into it, in floor order.

`marketplace_tagged` reports whether the derived `extraKnownMarketplaces`
entry carries an `@version` suffix.

Do not include any text outside the JSON object.
````

`fixtures/user-prompt-template.md`:

```markdown
<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Repo and machine state

{report}

You are running the floor-lock step of `setup adopt`. Report what it writes.
Return JSON only.
```

- [ ] **Step 2: Write the four cases**

Every `case-meta.json` is `{"tags":["local-smoke","smoke"]}`.

`case-1-fresh-claude-code/report.md`:

````markdown
<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

The repo is a main checkout with no `.apache-magpie.lock` and no
`.apache-magpie-overrides/`. The running agent is Claude Code.

`claude plugin list --json` reports magpie-setup 0.3.0, magpie-utilities 0.3.0,
magpie-agent-guard 0.3.0 and magpie-security 0.3.0, all from the
`apache-magpie` marketplace.

The maintainer confirmed they are acting for the project and accepted the
seeded floor without changing it.
```

`case-1-fresh-claude-code/expected.json` — `magpie-security` is installed but
does **not** enter the floor:

```json
{"wrote_lock": true, "min_version": "0.3.0",
 "plugins": ["magpie-setup", "magpie-utilities", "magpie-agent-guard"],
 "marketplace_tagged": false}
```

`case-2-maintainer-adds-a-family/report.md`:

```markdown
<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

The repo is a main checkout with no `.apache-magpie.lock`. The running agent is
Claude Code.

`claude plugin list --json` reports magpie-setup 0.3.0, magpie-utilities 0.3.0,
magpie-agent-guard 0.3.0 and magpie-pr-management 0.3.0, all from the
`apache-magpie` marketplace.

The maintainer was shown the seeded floor and its always-on context cost, asked
to add `magpie-pr-management` to it because every contributor reviews PRs, and
confirmed.
```

`case-2-maintainer-adds-a-family/expected.json`:

```json
{"wrote_lock": true, "min_version": "0.3.0",
 "plugins": ["magpie-setup", "magpie-utilities", "magpie-agent-guard",
             "magpie-pr-management"],
 "marketplace_tagged": false}
```

`case-3-dev-version-installed/report.md`:

```markdown
<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

The repo is a main checkout with no `.apache-magpie.lock`. The running agent is
Claude Code.

`claude plugin list --json` reports magpie-setup, magpie-utilities and
magpie-agent-guard all at version 0.4.0.dev202609130112, from the
`apache-magpie` marketplace.

The maintainer confirmed they are acting for the project and accepted the
seeded floor without changing it.
```

`case-3-dev-version-installed/expected.json` — the dev version is recorded as
it stands, not rounded to a release:

```json
{"wrote_lock": true, "min_version": "0.4.0.dev202609130112",
 "plugins": ["magpie-setup", "magpie-utilities", "magpie-agent-guard"],
 "marketplace_tagged": false}
```

`case-4-gemini/report.md` — the harness-reach case:

```markdown
<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

The repo is a main checkout with no `.apache-magpie.lock`. The running agent is
Google Gemini CLI, which has no workspace-extension mechanism and no
`.claude/settings.json` equivalent.

The Magpie extension installed in it reports version 0.3.0.

The maintainer confirmed they are acting for the project and accepted the
seeded floor without changing it.
```

`case-4-gemini/expected.json` — the lock is harness-neutral and is still
written; only the derived wiring is skipped:

```json
{"wrote_lock": true, "min_version": "0.3.0",
 "plugins": ["magpie-setup", "magpie-utilities", "magpie-agent-guard"],
 "marketplace_tagged": false}
````

- [ ] **Step 3: Run the evals to verify they fail**

```bash
uv run --directory tools/skill-evals skill-eval --cli "claude -p" \
    evals/setup/adopt-write-floor/
```

Expected: extraction fails — `## Step 2 — Write the floor lock` is not in
`skills/setup/adopt.md`.

- [ ] **Step 4: Insert the new step**

In `skills/setup/adopt.md`, insert immediately after `## Step 1 — Decide the
default set` and before the existing `## Step 2 — Write the default set`:

````markdown
## Step 2 — Write the floor lock

The floor from Step 1 is recorded in `.apache-magpie.lock`, committed
at the repo root. This is the project's adoption record, and it is
harness-neutral: write it on **every** client, including the ones that
cannot express the derived wiring in Step 3.

```text
# .apache-magpie.lock — committed; the project's floor.

method:       marketplace
url:          apache/magpie
min_version:  0.3.0

plugins:
  - magpie-setup
  - magpie-utilities
  - magpie-agent-guard
```

- **`min_version` is the Magpie version installed on this machine right
  now** — the version the maintainer is actually validating against.
  Read it from `claude plugin list --json`, or from the running agent's
  equivalent. Record it **verbatim**: a `.devNNNN` build adopted
  mid-cycle is written as it stands, not rounded up or down to a
  release. [`locks.md`](locks.md#method-marketplace--the-adoption-floor)
  explains why PEP 440 makes that correct.
- **`plugins` is the floor from Step 1**, in floor order, and nothing
  else. A family the maintainer happens to have installed does not
  enter the floor because it is installed — only because they asked for
  it in Step 1.
- **`url` is `apache/magpie`.** See
  [`locks.md`](locks.md#url-is-a-security-boundary) — a floor naming
  any other marketplace loses the pre-flight's automatic behaviour, so
  do not write one unless the user has a reason and knows the cost.

**If a lock already exists**, this is a re-adoption. Show the diff
between the existing floor and the one Step 1 produced, and let the
maintainer confirm. Never lower `min_version`: if the existing floor is
*higher* than the installed version, keep the existing value and say
so — a floor going backwards would silently withdraw a requirement the
project already made.

`git add` the lock. **Never commit** — the floor lands through the
project's normal review process, like any other committed file.
````

Then renumber the three following headings: `## Step 2 — Write the default set`
→ `## Step 3 — Write the derived wiring`, `## Step 3 — Scaffold the overrides
store` → `## Step 4 — …`, `## Step 4 — Recap` → `## Step 5 — Recap`. **Leave
`### Merge rules` exactly as spelled** — `step-adopt-settings-merge` keys on it.

- [ ] **Step 5: Point the derived-wiring step at the lock**

At the top of the renumbered `## Step 3 — Write the derived wiring`, before the
existing prose, insert:

```markdown
`.claude/settings.json` is **derived from the lock in Step 2**, not
authored here: `extraKnownMarketplaces` names `url`, and
`enabledPlugins` contains `plugins`, each as `<plugin>@apache-magpie`.
The lock is the source of truth; this file is how Claude Code acts on
it.

**Write the marketplace entry untagged** — `"repo": "apache/magpie"`,
with no `@version`. The floor is a minimum, and tagging the marketplace
would convert it into a ceiling that stops contributors receiving any
later release.

On a client that cannot express this — Codex can only default-install
all ten families, Gemini has no workspace-extension mechanism — skip
this step and say so. The lock from Step 2 still stands and is still
the project's record; what is missing is only the automatic wiring.
```

- [ ] **Step 6: Extend the recap**

In the renumbered `## Step 5 — Recap`, change item 1 from two paths to three,
and add a new item after it:

```markdown
1. **What is staged** — the three paths (the lock, the derived wiring,
   the overrides store), and that nothing is committed.
2. **What the floor means** — a minimum, not a pin. Contributors on a
   newer Magpie are fine and will be told nothing; contributors behind
   it are brought up to it by the pre-flight in any skill they run.
   Nothing is ever downgraded or removed.
```

Renumber the remaining recap items accordingly.

- [ ] **Step 7: Run the evals to verify they pass**

```bash
uv run --directory tools/skill-evals skill-eval --cli "claude -p" \
    evals/setup/adopt-write-floor/
```

Expected: 4/4 pass. Case 1 (`magpie-security` installed, absent from the floor)
and case 4 (Gemini still gets a lock) are the two that matter.

- [ ] **Step 8: Re-run the existing adopt suite for regressions**

```bash
uv run --directory tools/skill-evals skill-eval --cli "claude -p" \
    evals/setup/step-adopt-settings-merge/
```

Expected: 5/5 still pass — the renumbering must not have moved `### Merge
rules`.

- [ ] **Step 9: Commit**

```bash
git add skills/setup/adopt.md tools/skill-evals/evals/setup/adopt-write-floor/
git commit -m "feat(setup): adopt writes the floor lock

Adoption recorded no version. It wrote an untagged marketplace entry and
three plugin names into .claude/settings.json and nothing else, so nothing
could tell that a contributor was three releases behind what the project
validated against.

A new Step 2 writes .apache-magpie.lock with min_version set to the version
installed at adopt time, verbatim including a .dev suffix, and the floor from
Step 1. It is written on every client, Gemini and Codex included: the lock is
harness-neutral and .claude/settings.json is merely how Claude Code acts on
it. Re-adoption never lowers min_version -- a floor going backwards would
silently withdraw a requirement the project already made.

The marketplace entry stays untagged. Tagging it would turn the floor into a
ceiling and stop contributors receiving any later release.

Generated-by: Claude Opus 5"
```

---

### Task 3: `setup` arrives pre-filled from the floor

**Files:**
- Modify: `skills/setup/install.md` — a new `## Step M0b — Pre-fill from the
  committed floor` before the marketplace walk-through, and Step M5's offer
  becomes a pointer
- Modify: `skills/setup/SKILL.md:64-70` (the install-paths table) — add the
  fourth method row
- Create: `tools/skill-evals/evals/setup/setup-prefill-from-floor/fixtures/`

**Interfaces:**
- Consumes: from Task 1 — the verdict strings and field names. From Task 2 —
  that a lock exists to read.
- Produces: the heading `## Step M0b — Pre-fill from the committed floor`; the
  JSON keys `source`, `proposed_plugins`, `writes_to_repo`, `asks_first`.

- [ ] **Step 1: Write the failing eval fixtures**

`fixtures/step-config.json`:

```json
{
  "skill_md": "skills/setup/install.md",
  "step_heading": "## Step M0b — Pre-fill from the committed floor"
}
```

`fixtures/output-spec.md`:

````markdown
<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "source": "committed-floor" | "framework-defaults",
  "proposed_plugins": [...],
  "writes_to_repo": true | false,
  "asks_first": true | false
}
```

`source` reports where the proposed configuration came from.

`proposed_plugins` is what this run proposes to install, in the order the
source gives them.

`writes_to_repo` reports whether this step writes any committed file.

`asks_first` reports whether this step requires explicit user confirmation
before running any install command.

Do not include any text outside the JSON object.
````

`fixtures/user-prompt-template.md`:

```markdown
<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Repo and machine state

{report}

You are running the pre-fill step of `setup`. Report what it proposes. Return
JSON only.
```

- [ ] **Step 2: Write the four cases**

Every `case-meta.json` is `{"tags":["local-smoke","smoke"]}`.

`case-1-adopted-repo/report.md`:

````markdown
<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

`.apache-magpie.lock` at the repo root contains:

    method:       marketplace
    url:          apache/magpie
    min_version:  0.3.0

    plugins:
      - magpie-setup
      - magpie-utilities
      - magpie-agent-guard
      - magpie-pr-management

The running agent is Claude Code. `claude plugin list --json` reports
magpie-setup 0.3.0 only. The user ran `/magpie-setup` with no arguments.
```

`case-1-adopted-repo/expected.json`:

```json
{"source": "committed-floor",
 "proposed_plugins": ["magpie-setup", "magpie-utilities", "magpie-agent-guard",
                      "magpie-pr-management"],
 "writes_to_repo": false, "asks_first": true}
```

`case-2-unadopted-repo/report.md`:

```markdown
<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

There is no `.apache-magpie.lock` and no `.apache-magpie-overrides/` at the
repo root. The running agent is Claude Code with no Magpie plugins installed.
The user ran `/magpie-setup` with no arguments.
```

`case-2-unadopted-repo/expected.json`:

```json
{"source": "framework-defaults",
 "proposed_plugins": ["magpie-setup", "magpie-utilities", "magpie-agent-guard"],
 "writes_to_repo": false, "asks_first": true}
```

`case-3-foreign-marketplace/report.md` — the security case:

```markdown
<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

`.apache-magpie.lock` at the repo root contains:

    method:       marketplace
    url:          contoso-internal/magpie-fork
    min_version:  0.3.0

    plugins:
      - magpie-setup
      - magpie-utilities

The running agent is Claude Code with no Magpie plugins installed. The user ran
`/magpie-setup` with no arguments.
```

`case-3-foreign-marketplace/expected.json`:

```json
{"source": "committed-floor",
 "proposed_plugins": ["magpie-setup", "magpie-utilities"],
 "writes_to_repo": false, "asks_first": true}
```

`case-4-snapshot-lock/report.md` — routing must not misfire on the pinned path:

```markdown
<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

`.apache-magpie.lock` at the repo root contains:

    method: git-tag
    url:    https://github.com/apache/magpie.git
    ref:    v0.3.0
    commit: 4f1c9ab2d3e5f60718293a4b5c6d7e8f90a1b2c3

`.apache-magpie/` is absent and `.apache-magpie.local.lock` does not exist. The
running agent is Claude Code. The user ran `/magpie-setup` with no arguments.
```

`case-4-snapshot-lock/expected.json` — this is the snapshot install's own
flow, so the marketplace pre-fill proposes nothing:

```json
{"source": "framework-defaults", "proposed_plugins": [],
 "writes_to_repo": false, "asks_first": true}
````

- [ ] **Step 3: Run the evals to verify they fail**

```bash
uv run --directory tools/skill-evals skill-eval --cli "claude -p" \
    evals/setup/setup-prefill-from-floor/
```

Expected: extraction fails — the heading is not in `skills/setup/install.md`.

- [ ] **Step 4: Add the pre-fill step**

Insert into `skills/setup/install.md` immediately before the marketplace
walk-through section (`## Marketplace install — the default path`):

````markdown
## Step M0b — Pre-fill from the committed floor

Before proposing anything, read `.apache-magpie.lock` at the repo root.

**No lock, or a lock whose `method` is one of the three snapshot
methods** → this step proposes nothing. Framework defaults apply and
the snapshot flow owns the rest; propose no marketplace plugins here.

**`method: marketplace`** → the project has adopted Magpie and this
lock is its floor. Propose **exactly the floor's `plugins`, in the
order the lock gives them**, rather than the framework's three
defaults. Say where the proposal came from:

```text
This project has adopted Magpie (.apache-magpie.lock).
Its floor: magpie-setup, magpie-utilities, magpie-agent-guard,
           magpie-pr-management — Magpie 0.3.0 or newer.

Proposing to install those four. You can change this — the floor is
what the project recommends, not a restriction on what you may run.
```

Two rules hold regardless of what the lock says:

- **This step writes nothing to the repository.** Reading the floor is
  not adopting, re-adopting, or amending it. Changing the committed
  floor is [`adopt`](adopt.md), and only `adopt`.
- **Ask before running any install command.** The floor is a
  recommendation from the project; acting on it is still the user's
  decision, and they may add to or subtract from the proposal.

**If `url` is not `apache/magpie`**, say so prominently before the
proposal and name the marketplace the floor points at. See
[`locks.md`](locks.md#url-is-a-security-boundary): a lock is a
committed file in whatever repository the user happened to open, and
this is the moment they get to notice it.
````

- [ ] **Step 5: Turn Step M5's offer into a pointer**

In `skills/setup/install.md`, replace the Step M5 offer to write the
default-set block and scaffold the store with:

```markdown
**Adopting is a separate, deliberate act.** If this repo has no
`.apache-magpie.lock`, say once that the project can commit a floor —
a minimum version and plugin set every contributor picks up on clone —
and name [`/magpie-setup adopt`](adopt.md) as the way to do it. Do not
write it here.

One writer of the floor keeps the lock, the derived wiring, and the
overrides store from drifting apart, and keeps a maintainer's decision
to commit files for every contributor out of an install flow someone
may have reached just to try Magpie out.
```

- [ ] **Step 6: Add the fourth row to the paths table**

In `skills/setup/SKILL.md:64-70`, add to the install-paths table, after the
`marketplace` row:

```markdown
| **`marketplace` + an adopted floor** | The same per-machine install, plus a committed `.apache-magpie.lock` recording the project's minimum version and plugin set. Contributors are brought up to it by any skill's pre-flight. | The project wants a floor every contributor meets, without pinning anyone to one version. Written by [`adopt`](adopt.md). |
```

- [ ] **Step 7: Run the evals to verify they pass**

```bash
uv run --directory tools/skill-evals skill-eval --cli "claude -p" \
    evals/setup/setup-prefill-from-floor/
```

Expected: 4/4 pass.

- [ ] **Step 8: Re-run the Step M5 suite for regressions**

```bash
uv run --directory tools/skill-evals skill-eval --cli "claude -p" \
    evals/setup/step-m5-no-repo-offer/
```

Expected: 4/4 still pass — all four cases assert that an install writes nothing
repo-side, which the pointer rewrite preserves and strengthens.

- [ ] **Step 9: Commit**

```bash
git add skills/setup/install.md skills/setup/SKILL.md \
        tools/skill-evals/evals/setup/setup-prefill-from-floor/
git commit -m "feat(setup): setup arrives pre-filled from the committed floor

A contributor running /magpie-setup in an adopted repo got the framework's
three defaults, the same as in a repo that had never heard of Magpie. The
project's floor was sitting in a committed file nothing read.

Step M0b reads it and proposes the floor's plugins instead, in the order the
lock gives them, saying where the proposal came from and that it is a
recommendation rather than a restriction. Reading the floor is not adopting
it: this step still writes nothing to the repo, and still asks before running
any install.

Step M5's offer to write the default set becomes a pointer to adopt. One
writer of the floor keeps the lock, the derived wiring and the overrides store
from drifting apart, and keeps a decision that commits files for every
contributor out of a flow someone may have reached just to try Magpie out.

A floor naming a marketplace other than apache/magpie is called out before the
proposal -- the moment the user gets to notice it.

Generated-by: Claude Opus 5"
```

---

### Task 4: The pre-flight brings a machine up to the floor

This is the task that touches 65 files. It edits one source and lets the
existing generator propagate it.

**Files:**
- Modify: `tools/dev/preflight-block.md` — replace check 2, add checks 3 and 4
- Modify (generated, by `--fix`): 65 × `skills/*/SKILL.md`
- Create: `tools/skill-evals/evals/setup/preflight-floor/fixtures/`

**Interfaces:**
- Consumes: from Task 1 — `satisfied` / `below-floor` / `plugin-missing`, the
  PEP 440 rule, and the `url` boundary.
- Produces: the JSON keys `action`, `commands`, `blocks`, `reason` used by no
  later task — this is a leaf.

- [ ] **Step 1: Write the failing eval fixtures**

`fixtures/step-config.json` — the block lives in the source file, and every
`SKILL.md` copy is generated from it, so the eval reads the source:

```json
{
  "skill_md": "tools/dev/preflight-block.md",
  "step_heading": "## Pre-flight — is this project set up?"
}
```

`fixtures/output-spec.md`:

````markdown
<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "action": "silent" | "install" | "update" | "print-command" | "ask-first" | "propose-setup",
  "commands": [...],
  "blocks": true | false,
  "reason": "<one sentence>"
}
```

`action` reports what the pre-flight does about the state described.
`silent` means it prints nothing and the skill proceeds.

`commands` is the list of shell commands the pre-flight runs, or — for
`print-command` and `ask-first` — the commands it shows the user. Empty for
`silent` and `propose-setup`.

`blocks` reports whether the skill stops rather than continuing this turn.

`reason` is one sentence saying why.

Do not include any text outside the JSON object.
````

`fixtures/user-prompt-template.md`:

```markdown
<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Repo and machine state

{report}

You are running the shared pre-flight at the top of a Magpie skill. Report what
it does. Return JSON only.
```

`fixtures/assertions.json` — `reason` is free text, so grade it with a
deterministic predicate rather than a string match. The shape is the one
`step-override-bypass` already uses: each predicate is a **top-level key**,
and a case opts in by carrying that key as a boolean in its `expected.json`.

```json
{
  "mentions_restart": {
    "type": "regex",
    "field": "reason",
    "pattern": "restart|new session|reload",
    "flags": "is"
  }
}
```

- [ ] **Step 2: Write the six cases**

Every `case-meta.json` is `{"tags":["local-smoke","smoke"]}` unless noted.

`case-1-at-floor/report.md`:

````markdown
<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

`.apache-magpie.lock` contains `method: marketplace`, `url: apache/magpie`,
`min_version: 0.2.0`, and a `plugins` list of magpie-setup, magpie-utilities
and magpie-agent-guard.

`.apache-magpie-overrides/` exists and contains `project.md`.

The running agent is Claude Code. `claude plugin list --json` reports all three
plugins at 0.4.0 from the `apache-magpie` marketplace.
```

`case-1-at-floor/expected.json`:

```json
{"action": "silent", "commands": [], "blocks": false}
```

`case-2-below-floor/report.md`:

```markdown
<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

`.apache-magpie.lock` contains `method: marketplace`, `url: apache/magpie`,
`min_version: 0.3.0`, and a `plugins` list of magpie-setup and
magpie-pr-management.

`.apache-magpie-overrides/` exists and contains `project.md`.

The running agent is Claude Code. `claude plugin list --json` reports
magpie-setup 0.3.0 and magpie-pr-management 0.2.0, both from the
`apache-magpie` marketplace.
```

`case-2-below-floor/expected.json`, opting in to the `mentions_restart`
predicate:

```json
{"action": "update",
 "commands": ["claude plugin update magpie-pr-management@apache-magpie"],
 "blocks": true,
 "mentions_restart": true}
```

`case-3-plugin-missing/report.md`:

```markdown
<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

`.apache-magpie.lock` contains `method: marketplace`, `url: apache/magpie`,
`min_version: 0.3.0`, and a `plugins` list of magpie-setup and
magpie-agent-guard.

`.apache-magpie-overrides/` exists and contains `project.md`.

The running agent is Claude Code. `claude plugin list --json` reports
magpie-setup 0.3.0 only.
```

`case-3-plugin-missing/expected.json`:

```json
{"action": "install",
 "commands": ["claude plugin install magpie-agent-guard@apache-magpie"],
 "blocks": true,
 "mentions_restart": true}
```

`case-4-foreign-marketplace/report.md` — the security case:

```markdown
<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

`.apache-magpie.lock` contains `method: marketplace`, `url:
contoso-internal/magpie-fork`, `min_version: 0.3.0`, and a `plugins` list of
magpie-setup and magpie-exfil-helper.

`.apache-magpie-overrides/` exists and contains `project.md`.

The running agent is Claude Code. `claude plugin list --json` reports
magpie-setup 0.3.0 from the `apache-magpie` marketplace and nothing else.
```

`case-4-foreign-marketplace/expected.json` — nothing runs without a decision:

```json
{"action": "ask-first", "blocks": true}
```

`case-5-no-claude-cli/report.md`:

```markdown
<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

`.apache-magpie.lock` contains `method: marketplace`, `url: apache/magpie`,
`min_version: 0.3.0`, and a `plugins` list of magpie-setup and
magpie-agent-guard.

`.apache-magpie-overrides/` exists and contains `project.md`.

The running agent is Google Gemini CLI. There is no `claude` executable on
PATH. The installed Magpie extension reports version 0.2.0.
```

`case-5-no-claude-cli/expected.json`:

```json
{"action": "print-command", "blocks": true}
```

`case-6-unadopted/report.md` — the pre-existing behaviour, which must survive:

```markdown
<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

There is no `.apache-magpie.lock` and no `.apache-magpie-overrides/` at the
repo root. The running agent is Claude Code with magpie-setup 0.4.0 and
magpie-issue 0.4.0 installed.
```

`case-6-unadopted/expected.json`:

```json
{"action": "propose-setup", "commands": [], "blocks": true}
````

- [ ] **Step 3: Run the evals to verify they fail**

```bash
uv run --directory tools/skill-evals skill-eval --cli "claude -p" \
    evals/setup/preflight-floor/
```

Expected: cases 1 and 6 may pass by luck on the current block; cases 2–5 fail,
because the block has no floor check and cannot produce `install`, `update`,
`ask-first` or `print-command` at all.

- [ ] **Step 4: Replace check 2 and add the floor checks**

In `tools/dev/preflight-block.md`, replace the numbered list (currently checks
1–3) with:

````markdown
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

   **First, check `url`.** If it is anything other than
   `apache/magpie`, run **nothing**. Name the marketplace the lock
   points at, show the commands it would take, and let the user decide.
   A lock is a committed file in whatever repository happened to be
   opened, and acting on it automatically would make opening a
   repository enough to install someone else's code.

   Otherwise read the installed state — `claude plugin list --json`, or
   the running agent's equivalent — and compare **as PEP 440, not as
   strings**: `0.10.0` is newer than `0.9.0`, and `0.2.0` is newer than
   `0.2.0.dev202609110041`.

   - every floor plugin installed at or above `min_version` →
     **silent**; continue the skill;
   - a floor plugin absent → `claude plugin install
     <plugin>@apache-magpie`;
   - a floor plugin below `min_version` → `claude plugin update
     <plugin>@apache-magpie`.

   **Never** remove a plugin, downgrade one, pin the marketplace to a
   tag, or touch a plugin absent from the floor. Being *ahead* of the
   floor is the normal case and is not a finding.

   Where there is no such CLI, run nothing and print the commands
   instead. The comparison and the message are the same; only the
   action differs.

4. **Anything was installed or updated → say what ran, and stop.**
   Claude Code loads plugins at session start, so what you just
   installed is not live in this session. The skill cannot continue
   this turn either way; what this saves the user is working out the
   command.

   ```text
   ⚠ magpie-pr-management 0.2.0 installed; this project's floor is 0.3.0.

     ✓ ran: claude plugin update magpie-pr-management@apache-magpie

     Restart the session to load it, then re-run this command.
   ```

5. **No lock?** Then this is the marketplace install without adoption,
   or nothing at all. Look for a `<project-config>/` directory. If there
   is none, the project has not been adopted and every `<placeholder>`
   in this skill is unresolved → **stop and propose `/magpie-setup`**.
   Do **not** run setup unattended and do **not** continue on a guess: a
   skill that proceeds against an unadopted repo writes to the wrong
   tracker.
````

- [ ] **Step 5: Propagate the block into all 65 skills**

```bash
python3 tools/dev/check-skill-preflight.py --fix
python3 tools/dev/check-skill-preflight.py
```

Expected: the first rewrites 65 `SKILL.md` files; the second exits 0 with no
drift.

- [ ] **Step 6: Run the evals to verify they pass**

```bash
uv run --directory tools/skill-evals skill-eval --cli "claude -p" \
    evals/setup/preflight-floor/
```

Expected: 6/6 pass. Case 4 (`ask-first`, nothing runs) is the one that must
never regress.

- [ ] **Step 7: Commit**

```bash
git add tools/dev/preflight-block.md skills/ \
        tools/skill-evals/evals/setup/preflight-floor/
git commit -m "feat(setup): the pre-flight brings a machine up to the floor

The pre-flight could tell that a repo was unadopted. It could not tell that a
machine was behind what an adopted repo asked for, because until the lock grew
a marketplace method there was nothing to be behind.

Check 3 compares the installed plugins against the floor as PEP 440, installs
what is absent, updates what is below min_version, and is silent when the
machine is at or ahead of it -- which is the normal case. It never removes a
plugin, downgrades one, pins the marketplace, or touches a plugin absent from
the floor.

It stops afterwards regardless. Claude Code loads plugins at session start, so
what it just installed is not live this turn; the message says so rather than
implying the retry will work. What this saves is working out the command, not
the restart.

url is checked before anything runs: a floor naming any marketplace other than
apache/magpie gets the commands printed and a decision asked for. A lock is a
committed file in whatever repository happened to be opened.

Generated-by: Claude Opus 5"
```

---

### Task 5: `upgrade` splits on adoption

**Files:**
- Modify: `skills/setup/upgrade.md` — a new `## Step 0b — Marketplace method:
  the floor split` after the existing `## Step 0 — Pre-flight` (line 43–82)
- Create: `tools/skill-evals/evals/setup/upgrade-adoption-split/fixtures/`

**Interfaces:**
- Consumes: from Task 1 — the field names and the never-lower rule. From
  Task 2 — the derived-wiring relationship.
- Produces: the JSON keys `updates_plugins`, `new_min_version`,
  `stages_files`, `commits`.

- [ ] **Step 1: Write the failing eval fixtures**

`fixtures/step-config.json`:

```json
{
  "skill_md": "skills/setup/upgrade.md",
  "step_heading": "## Step 0b — Marketplace method: the floor split"
}
```

`fixtures/output-spec.md`:

````markdown
<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "updates_plugins": true | false,
  "new_min_version": "<version string, or null>",
  "stages_files": [...],
  "commits": true | false
}
```

`updates_plugins` reports whether this step updates the machine's installed
plugins.

`new_min_version` is the value `min_version` holds after this step, or `null`
if no lock is written.

`stages_files` is the list of repo-relative paths this step `git add`s, empty
if none.

`commits` reports whether this step creates a git commit.

Do not include any text outside the JSON object.
````

`fixtures/user-prompt-template.md`:

```markdown
<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Repo and machine state

{report}

You are running the marketplace branch of `setup upgrade`. Report what it does.
Return JSON only.
```

- [ ] **Step 2: Write the four cases**

Every `case-meta.json` is `{"tags":["local-smoke","smoke"]}`.

`case-1-not-adopted/report.md`:

````markdown
<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

There is no `.apache-magpie.lock` at the repo root. The running agent is Claude
Code. `claude plugin list --json` reports magpie-setup 0.2.0 and
magpie-issue 0.2.0 from the `apache-magpie` marketplace; 0.4.0 is available.

The user ran `/magpie-setup upgrade`.
```

`case-1-not-adopted/expected.json`:

```json
{"updates_plugins": true, "new_min_version": null, "stages_files": [],
 "commits": false}
```

`case-2-adopted/report.md`:

```markdown
<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

`.apache-magpie.lock` contains `method: marketplace`, `url: apache/magpie`,
`min_version: 0.2.0`, and a `plugins` list of magpie-setup, magpie-utilities
and magpie-agent-guard.

The running agent is Claude Code. `claude plugin list --json` reports all three
at 0.2.0; 0.4.0 is available. The user ran `/magpie-setup upgrade`.
```

`case-2-adopted/expected.json`:

```json
{"updates_plugins": true, "new_min_version": "0.4.0",
 "stages_files": [".apache-magpie.lock", ".claude/settings.json"],
 "commits": false}
```

`case-3-already-ahead/report.md` — the never-lower rule:

```markdown
<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

`.apache-magpie.lock` contains `method: marketplace`, `url: apache/magpie`,
`min_version: 0.9.0`, and a `plugins` list of magpie-setup and
magpie-utilities.

The running agent is Claude Code. `claude plugin list --json` reports both
plugins at 0.9.0, and 0.9.0 is the latest available — there is nothing to
update.

The user ran `/magpie-setup upgrade`.
```

`case-3-already-ahead/expected.json` — nothing moved, so nothing is staged:

```json
{"updates_plugins": false, "new_min_version": "0.9.0", "stages_files": [],
 "commits": false}
```

`case-4-snapshot-method/report.md` — routing must fall through:

```markdown
<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

`.apache-magpie.lock` contains `method: git-tag`, `url:
https://github.com/apache/magpie.git`, `ref: v0.3.0` and `commit:
4f1c9ab2d3e5f60718293a4b5c6d7e8f90a1b2c3`. `.apache-magpie.local.lock` records
`source_ref: v0.2.0`.

The user ran `/magpie-setup upgrade`.
```

`case-4-snapshot-method/expected.json` — this step does not handle the snapshot
path and hands it to the steps that follow:

```json
{"updates_plugins": false, "new_min_version": null, "stages_files": [],
 "commits": false}
````

- [ ] **Step 3: Run the evals to verify they fail**

```bash
uv run --directory tools/skill-evals skill-eval --cli "claude -p" \
    evals/setup/upgrade-adoption-split/
```

Expected: extraction fails — the heading is not in `skills/setup/upgrade.md`.

- [ ] **Step 4: Add the split**

Insert into `skills/setup/upgrade.md` immediately after `## Step 0 —
Pre-flight` and before `## Step 1 — Compute drift`:

````markdown
## Step 0b — Marketplace method: the floor split

Read `.apache-magpie.lock`. **If `method` is one of the three snapshot
methods, or there is no lock at all, skip this step entirely** and
continue at Step 1 — the snapshot flow below owns those, unchanged.

For `method: marketplace`, this step *is* the upgrade, and Steps 1–9
below do not apply: there is no snapshot to delete, no symlink to
refresh and no local lock to rewrite.

**Update the machine either way.** Run the agent's plugin update for
every installed Magpie plugin and report the versions before and after.
Where there is no such CLI, print the commands instead.

Then split on whether the project has adopted Magpie:

| | No lock | `method: marketplace` |
|---|---|---|
| Updates the plugins | yes | yes |
| Writes to the repo | **nothing** | raises `min_version`, regenerates the derived wiring |
| Commits | — | **never**; `git add` only |

**Not adopted** → report the new versions and stop. Do not offer to
write a lock here: adopting is
[`adopt`](adopt.md), a deliberate act with a different blast radius,
and an upgrade is not the moment to slip it in.

**Adopted** → after the update, set `min_version` to the version now
installed and regenerate `.claude/settings.json` from the lock, under
the merge rules in [`adopt.md`](adopt.md#merge-rules). Show the diff,
`git add` both, and say plainly that the bump lands through the
project's normal review like any other committed file.

**`min_version` only ever rises.** If the installed version is somehow
*below* the committed floor — an update that could not reach the latest,
a machine pinned by other means — leave the floor where it is and say
so. A floor going backwards would silently withdraw a requirement the
project already made.

**If nothing moved, stage nothing.** An upgrade that finds everything
already current is a no-op with a one-line report, not an empty diff to
review.
````

- [ ] **Step 5: Run the evals to verify they pass**

```bash
uv run --directory tools/skill-evals skill-eval --cli "claude -p" \
    evals/setup/upgrade-adoption-split/
```

Expected: 4/4 pass. Case 3 (`0.9.0` floor stays `0.9.0`) is the never-lower
guard; case 4 must fall through without claiming to have done anything.

- [ ] **Step 6: Commit**

```bash
git add skills/setup/upgrade.md \
        tools/skill-evals/evals/setup/upgrade-adoption-split/
git commit -m "feat(setup): upgrade splits on whether the project adopted

upgrade was written for the snapshot install -- delete the snapshot, re-fetch
per the committed pin, refresh symlinks, rewrite the local lock. None of that
applies to a marketplace install, which has no snapshot, no symlinks and no
local lock.

Step 0b handles that path and returns. It updates the machine either way, and
then splits: an unadopted repo gets a version report and nothing written, an
adopted one gets min_version raised to what is now installed and the derived
wiring regenerated, staged for the project's normal review.

min_version only ever rises. A machine that could not reach the latest leaves
the floor where it is, because a floor going backwards would silently withdraw
a requirement the project already made. An upgrade that finds everything
current stages nothing rather than offering an empty diff.

It does not offer to write a lock when there is none. Adopting is a deliberate
act with a different blast radius, and an upgrade is not the moment to slip it
in.

Generated-by: Claude Opus 5"
```

---

### Task 6: `verify`, `status`, `unadopt` and `uninstall`

**Files:**
- Modify: `skills/setup/verify.md` — a new `## Adoption floor` section after
  `## Committed default set` (line 823–853)
- Modify: `skills/setup/uninstall.md` — the `unadopt` / `uninstall` split
- Modify: `skills/setup-status/render.md` — print the floor
- Create: `tools/skill-evals/evals/setup/verify-floor/fixtures/`

**Interfaces:**
- Consumes: from Task 1 — the verdicts and the ahead-is-not-drift rule. From
  Task 2 — the three staged paths.
- Produces: nothing consumed by a later task — this is a leaf.

- [ ] **Step 1: Write the failing eval fixtures**

`fixtures/step-config.json`:

```json
{
  "skill_md": "skills/setup/verify.md",
  "step_heading": "## Adoption floor"
}
```

`fixtures/output-spec.md`:

````markdown
<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "status": "not-adopted" | "met" | "below" | "unshippable-plugin",
  "is_fault": true | false,
  "shortfall": [...]
}
```

`status` reports how the machine stands against the committed floor.
`unshippable-plugin` is for a floor naming a plugin the marketplace no longer
ships.

`is_fault` reports whether that state is a fault to be fixed.

`shortfall` lists the plugin names that do not meet the floor, in floor order.

Do not include any text outside the JSON object.
````

`fixtures/user-prompt-template.md`:

```markdown
<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Repo and machine state

{report}

You are running the adoption-floor check of `setup verify`. Report its status.
Return JSON only.
```

- [ ] **Step 2: Write the four cases**

Every `case-meta.json` is `{"tags":["local-smoke","smoke"]}`.

`case-1-no-lock/report.md`:

````markdown
<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

There is no `.apache-magpie.lock` at the repo root. `.apache-magpie-overrides/`
exists and contains `project.md`. The running agent is Claude Code with
magpie-setup 0.4.0 and magpie-utilities 0.4.0 installed.
```

`case-1-no-lock/expected.json` — not adopting is a supported end state:

```json
{"status": "not-adopted", "is_fault": false, "shortfall": []}
```

`case-2-ahead-of-floor/report.md`:

```markdown
<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

`.apache-magpie.lock` contains `method: marketplace`, `url: apache/magpie`,
`min_version: 0.2.0`, and a `plugins` list of magpie-setup and
magpie-utilities.

The running agent is Claude Code. `claude plugin list --json` reports
magpie-setup 0.7.0, magpie-utilities 0.7.0 and magpie-security 0.7.0.
```

`case-2-ahead-of-floor/expected.json` — being ahead, and having extra plugins,
are both normal:

```json
{"status": "met", "is_fault": false, "shortfall": []}
```

`case-3-below-floor/report.md`:

```markdown
<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

`.apache-magpie.lock` contains `method: marketplace`, `url: apache/magpie`,
`min_version: 0.5.0`, and a `plugins` list of magpie-setup, magpie-utilities
and magpie-agent-guard.

The running agent is Claude Code. `claude plugin list --json` reports
magpie-setup 0.5.0, magpie-utilities 0.4.0, and no magpie-agent-guard.
```

`case-3-below-floor/expected.json`:

```json
{"status": "below", "is_fault": true,
 "shortfall": ["magpie-utilities", "magpie-agent-guard"]}
```

`case-4-plugin-no-longer-shipped/report.md`:

```markdown
<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

`.apache-magpie.lock` contains `method: marketplace`, `url: apache/magpie`,
`min_version: 0.2.0`, and a `plugins` list of magpie-setup and
magpie-legacy-reports.

The running agent is Claude Code. `claude plugin list --json --available`
reports that the `apache-magpie` marketplace offers magpie-setup 0.7.0 and nine
other family plugins, none of them named magpie-legacy-reports. magpie-setup
0.7.0 is installed.
```

`case-4-plugin-no-longer-shipped/expected.json` — a fault for a maintainer to
fix in a PR, not something the pre-flight installs around:

```json
{"status": "unshippable-plugin", "is_fault": true,
 "shortfall": ["magpie-legacy-reports"]}
````

- [ ] **Step 3: Run the evals to verify they fail**

```bash
uv run --directory tools/skill-evals skill-eval --cli "claude -p" \
    evals/setup/verify-floor/
```

Expected: extraction fails — `## Adoption floor` is not in
`skills/setup/verify.md`.

- [ ] **Step 4: Add the `verify` check**

Insert into `skills/setup/verify.md` after the `## Committed default set`
section, before `## After the report`:

````markdown
## Adoption floor

Read `.apache-magpie.lock`. This check applies only to
`method: marketplace`; the three snapshot methods are covered by the
drift check above.

- **No lock** → `not-adopted`. **This is not a fault.** A project that
  has not adopted Magpie is a supported end state, and every install in
  it works exactly as it does anywhere else. Report it in one line and
  move on.
- **Every floor plugin installed at or above `min_version`** → `met`,
  not a fault. Being *ahead* of the floor is the normal case, and extra
  plugins beyond the floor are the contributor's business — neither is
  reported as a finding.
- **A floor plugin absent, or below `min_version`** → `below`, a fault.
  List the shortfall in floor order and offer the repair: the same
  install/update the pre-flight would run.
- **A floor plugin the marketplace no longer ships** →
  `unshippable-plugin`, a fault. Do **not** offer to install around it.
  The project's floor names something that no longer exists, which is a
  fact for a maintainer to fix in a PR against this repo — say so, and
  name `setup adopt` as where the floor is edited.

Compare versions as PEP 440
([`locks.md`](locks.md#method-marketplace--the-adoption-floor)), never
as strings.
````

- [ ] **Step 5: Split `unadopt` from `uninstall`**

In `skills/setup/uninstall.md`, add to the section describing what each action
removes:

```markdown
**The lock belongs to `unadopt`, not `uninstall`.**

- **`unadopt`** removes `.apache-magpie.lock` along with the
  `extraKnownMarketplaces` and `enabledPlugins` entries derived from
  it. The project is withdrawing its floor; that is a committed
  recommendation and it goes.
- **`uninstall`** leaves `.apache-magpie.lock` exactly where it is. The
  project's floor is not this machine's install, and removing Magpie
  from your agent says nothing about what the project recommends to
  everyone else.

Say which one you did, and say what it did *not* touch.
```

- [ ] **Step 6: Print the floor in `status`**

In `skills/setup-status/render.md`, add to the adoption section of the rendered
dashboard:

```markdown
When `.apache-magpie.lock` carries `method: marketplace`, render the
floor beside the installed set, and mark each floor plugin met or
short:

| Floor (`min_version` 0.3.0) | Installed | |
|---|---|---|
| magpie-setup | 0.7.0 | ✓ |
| magpie-utilities | 0.7.0 | ✓ |
| magpie-agent-guard | — | short |

Plugins installed beyond the floor are listed separately and never
marked as a problem.
```

- [ ] **Step 7: Run the evals to verify they pass**

```bash
uv run --directory tools/skill-evals skill-eval --cli "claude -p" \
    evals/setup/verify-floor/
```

Expected: 4/4 pass. Cases 1 and 2 are the ones that must come back
`is_fault: false` — a check that calls a healthy repo faulty converts an
optional recommendation into a de-facto requirement.

- [ ] **Step 8: Re-run the whole setup suite**

```bash
uv run --directory tools/skill-evals skill-eval --cli "claude -p" \
    evals/setup/
```

Expected: every pre-existing suite still passes alongside the five new ones.

- [ ] **Step 9: Commit**

```bash
git add skills/setup/verify.md skills/setup/uninstall.md \
        skills/setup-status/render.md \
        tools/skill-evals/evals/setup/verify-floor/
git commit -m "feat(setup): verify, status and unadopt know about the floor

verify reports how the machine stands against the committed floor, and is
careful about what counts as a fault: a repo that never adopted is fine, and a
contributor ahead of the floor with extra families installed is fine. Only a
shortfall is a finding. A check that called either of those faulty would
convert an optional recommendation into a de-facto requirement.

A floor naming a plugin the marketplace no longer ships is a fault that is
not installed around -- the floor names something that does not exist, which
is a maintainer's fix in a PR.

unadopt removes the lock; uninstall leaves it. The project's floor is not this
machine's install, and removing Magpie from your agent says nothing about what
the project recommends to everyone else.

status renders the floor beside the installed set, marking each member met or
short, and lists plugins beyond the floor separately rather than as a problem.

Generated-by: Claude Opus 5"
```

---

### Task 7: Specification, docs and suite bookkeeping

**Files:**
- Modify: `tools/spec-loop/specs/adoption-and-setup.md` — behaviour contract
  and acceptance criteria
- Modify: `tools/skill-evals/evals/setup/README.md` — suite table and counts
- Modify: `tools/skill-evals/README.md:20` — the setup suite's case count
- Modify: `docs/setup/team-adoption.md`, `docs/setup/individual-use.md`

**Interfaces:**
- Consumes: every heading and rule from Tasks 1–6.
- Produces: nothing — this is the closing task.

- [ ] **Step 1: Add the behaviour contract**

In `tools/spec-loop/specs/adoption-and-setup.md`, add to `## Behaviour &
contract`:

```markdown
- **Adoption records a floor, not a pin.** On the marketplace path,
  `adopt` writes `.apache-magpie.lock` with `method: marketplace`, a
  `min_version` equal to the version installed at adopt time, and a
  plugin list seeded with the framework's three. Both are minimums:
  contributors may run newer versions and more plugins, and nothing is
  ever downgraded, removed, or pinned. The derived
  `extraKnownMarketplaces` entry is written untagged.
- **The lock is harness-neutral; the wiring is not.** The lock is
  written on every client. `.claude/settings.json` is derived from it
  and written only where the harness can express it.
- **Every skill's pre-flight brings the machine up to the floor** and
  then stops for a restart, and does so without asking only when the
  lock's `url` is `apache/magpie`.
- **`upgrade` splits on adoption:** nothing repo-side when the project
  has not adopted; `min_version` raised — never lowered — and staged
  when it has.
```

- [ ] **Step 2: Add the acceptance criteria**

Append to `## Acceptance criteria` in the same file, continuing its numbering:

```markdown
8. `adopt` on a marketplace install writes a `method: marketplace` lock
   carrying the installed version and the seeded floor, stages it, and
   commits nothing; the derived marketplace entry carries no version tag.
9. A pre-flight on a machine at or ahead of the floor prints nothing; one
   below it installs or updates only floor plugins, reports what ran, and
   stops for a restart without removing, downgrading or pinning anything.
10. A pre-flight whose lock names a `url` other than `apache/magpie` runs
    nothing and asks first.
11. Version comparison is PEP 440: `0.10.0` satisfies a `0.9.0` floor, and
    `0.2.0` satisfies a `0.2.0.dev202609110041` floor.
12. `upgrade` writes nothing to the repo when the project has not adopted,
    and raises — never lowers — `min_version` when it has.
13. `verify` reports a missing lock and an ahead-of-floor machine as not
    faults, and a shortfall as one.
14. `unadopt` removes the lock; `uninstall` leaves it; each says which.
```

- [ ] **Step 3: Update the eval suite README**

In `tools/skill-evals/evals/setup/README.md`, change the heading `## Suites (26
cases total)` to `## Suites (53 cases total)` and add five rows:

````markdown
| lock-marketplace-parse | locks.md § `method: marketplace` | 5 | ahead of floor, a .dev floor met by the release after it, 0.9.0 against a 0.10.0 floor (the string-ordering trap), a missing floor plugin, and a git-tag lock that still pins |
| adopt-write-floor | adopt.md § Step 2 | 4 | a fresh adopt with an extra family installed that stays out of the floor, a maintainer adding one deliberately, a .dev version recorded verbatim, and Gemini still getting a lock with no derived wiring |
| setup-prefill-from-floor | install.md § Step M0b | 4 | adopted (propose the floor), unadopted (framework defaults), a foreign marketplace called out, and a snapshot lock falling through |
| preflight-floor | preflight-block.md § Pre-flight | 6 | at floor (silent), below floor (update), plugin missing (install), foreign marketplace (ask first, run nothing), no `claude` CLI (print), unadopted (propose setup) |
| upgrade-adoption-split | upgrade.md § Step 0b | 4 | not adopted (nothing staged), adopted (floor raised and staged), already ahead (floor unchanged), snapshot method (falls through) |
| verify-floor | verify.md § Adoption floor | 4 | no lock (not a fault), ahead of floor with extra plugins (not a fault), a shortfall (a fault), a floor plugin the marketplace no longer ships (a fault, not installed around) |
```

Add to `## Notes`:

```markdown
- `preflight-floor` case 4 is the security case and the one that must
  never regress: a lock naming a marketplace other than `apache/magpie`
  must produce `ask-first` with nothing run.
- `preflight-floor` cases 2 and 3 grade their free-text `reason` with
  the `mention_restart` regex predicate in `assertions.json` rather than
  by string match. The `mention_` prefix is load-bearing:
  `runner.py`'s `is_structural_expected` recognises only keys prefixed
  `has_` or `mention_`, so a plural `mentions_restart` would fall
  through to key-intersection comparison and the predicate would
  silently never fire.
- `verify-floor` cases 1 and 2 are the pair that keeps the floor a
  recommendation: a repo that never adopted, and a contributor ahead of
  the floor with extra families installed, must both come back
  `is_fault: false`.
````

- [ ] **Step 4: Update the harness README count**

In `tools/skill-evals/README.md:20`, change the setup line to:

```markdown
- **setup** — 53 cases across 13 steps (step-verify-drift, step-overrides-surface, step-override-bypass, step-m5-no-repo-offer, step-adopt-settings-merge, verify-default-set, uninstall-default-set, lock-marketplace-parse, adopt-write-floor, setup-prefill-from-floor, preflight-floor, upgrade-adoption-split, verify-floor)
```

- [ ] **Step 5: Update the two reader-facing setup pages**

In `docs/setup/team-adoption.md`, add a section describing what adoption now
commits — the lock, what a floor means, and that it never limits what a
contributor may install. In `docs/setup/individual-use.md`, add a paragraph
saying that working in an adopted repo brings your machine up to the floor and
nothing more: your extra plugins and newer versions are untouched.

Both must state the floor-not-ceiling rule in the first sentence that mentions
it. Do not describe the quick-start flow here — that is Subsystem B's.

- [ ] **Step 6: Run the full check suite**

```bash
python3 tools/dev/check-doc-sync.py
python3 tools/dev/check-skill-preflight.py
uv run --project tools/skill-and-tool-validator --group dev skill-and-tool-validate
uv run --project tools/spec-validator spec-validate
```

Expected: all four exit 0.

- [ ] **Step 7: Commit**

```bash
git add tools/spec-loop/specs/adoption-and-setup.md \
        tools/skill-evals/README.md \
        tools/skill-evals/evals/setup/README.md \
        docs/setup/team-adoption.md docs/setup/individual-use.md
git commit -m "docs(setup): specify the adoption floor and record the new suites

The spec-loop spec is where setup behaviour is specified and validated in this
repository, so the floor's contract belongs there rather than only in the
design: what adopt records, that both dimensions are minimums, that the lock
is harness-neutral while the wiring is not, and that automatic action is
restricted to apache/magpie.

Seven acceptance criteria follow, including the two that are easy to get
backwards -- PEP 440 ordering, and min_version rising but never falling.

team-adoption and individual-use get the reader-facing half: what a floor
means for a maintainer committing one, and what it means for a contributor
working in a repo that has. The quick start is Subsystem B and is untouched
here.

Generated-by: Claude Opus 5"
```

---

## Self-review

**Spec coverage.** Every Subsystem A element in the design maps to a task: the
record → Task 1; `adopt` writes it → Task 2; `setup` arrives pre-filled and
Step M5 becomes a pointer → Task 3; the pre-flight → Task 4; the `upgrade`
split → Task 5; verify/status/uninstall → Task 6; spec surface → Task 7. Every
one of the design's eight Subsystem A acceptance criteria has a matching eval
case. Subsystems B and C are out of scope here by the design's own sequencing
and get their own plans.

**Type consistency.** The verdict vocabulary introduced in Task 1 (`satisfied`,
`below-floor`, `plugin-missing`, `not-marketplace`, `malformed`) is reused
unchanged where it appears again. Task 4 and Task 6 deliberately use *different*
enums — `action` for what the pre-flight does, `status` for what `verify`
reports — because they answer different questions; neither claims to be the
other. Field names `method` / `url` / `min_version` / `plugins` are identical in
every fixture and every prose block.

**Known non-determinism.** `reason` in Task 4 is free text and is graded by
regex predicates, following the `step-override-bypass` precedent. Every other
graded field across all 27 new cases is an enumerated string, a boolean, or a
plain list, so the suites are fully auto-comparable.
