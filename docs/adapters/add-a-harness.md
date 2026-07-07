<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Adding a new agent harness](#adding-a-new-agent-harness)
  - [Step 1 — add a row to the agent-target registry](#step-1--add-a-row-to-the-agent-target-registry)
  - [Step 2 — wire the action guard](#step-2--wire-the-action-guard)
  - [Step 3 — add a spec-loop runner profile](#step-3--add-a-spec-loop-runner-profile)
  - [Step 4 — update tool harness declarations](#step-4--update-tool-harness-declarations)
  - [Step 5 — validate the full wiring](#step-5--validate-the-full-wiring)
  - [Scope of a first-class harness integration](#scope-of-a-first-class-harness-integration)
  - [See also](#see-also)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Adding a new agent harness

This recipe names every step to wire a new agentic runtime into
Magpie so it loads skills, enforces the action guard, and runs
the spec-loop. It is the counterpart to the
[tool-adapter authoring guide](authoring.md) — that guide adds a
new *backend* (forge, VCS, mail system); this guide adds a new
*agent runtime*.

The framework's skills are plain
[`AGENTS.md`](https://agents.md/)-standard Markdown. No runtime
gets its own copy or variant of a skill — the content is
byte-identical. What differs per runtime is:

1. **Where on disk it looks for skills** (the symlink relay).
2. **Whether it enforces the action guard** (the pre-tool hook).
3. **How the spec-loop invokes it headlessly** (the `--cli` profile).
4. **Which substrate tools list it** (the `**Harness:**` declarations).

Steps 1 and 3 are always required. Step 2 is required for runtimes
that support a pre-tool hook API (and a matter of OS-level fallback for
those that do not). Step 4 is a metadata update, not executable code.

---

## Step 1 — add a row to the agent-target registry

The single source of truth for *where each runtime reads skills from* is
[`skills/setup/agents.md`](../../skills/setup/agents.md). Add one row:

```markdown
| `<id>` | `.<runtime>/skills/` | native (relay) | <Runtime name> |
```

- `<id>` — a short, lowercase, hyphen-safe identifier (e.g. `kiro`,
  `aider`, `openhands`).
- `<runtime>/skills/` — the path the runtime reads for project-scope
  skills. Check the runtime's docs; if it reads `.agents/skills/`
  directly (like Codex, Cursor, Gemini CLI) no new row is needed —
  the `universal` row already covers it.
- `native (relay)` — used for runtimes with their own per-agent
  directory. Leave the *kind* column as `native (relay)` if the
  directory is distinct from `.agents/skills/`; use `universal` only
  for runtimes that read `.agents/` natively.

Once the row is present, `/magpie-setup adopt` and `upgrade` wire the
relay symlinks automatically. The rules are:

- The *canonical* entry lives at `.agents/skills/magpie-<skill>` and
  points at the skill source.
- Every relay entry at `.<runtime>/skills/magpie-<skill>` points at
  `../../.agents/skills/magpie-<skill>` — **through the canonical, not
  straight at source**.

`symlink-lint` enforces both rules and is wired into `prek`; run it to
verify after any manual link creation:

```bash
uv run --project tools/symlink-lint python3 -m symlink_lint
```

## Step 2 — wire the action guard

The action guard (`tools/agent-guard`) intercepts shell commands *before*
they run and denies ones that break hard framework rules (unauthorized
`git push`, wrong commit-trailer format, premature `--ready-for-review`,
…). The guard *decisions* live in one harness-agnostic `dispatch()` core;
each harness gets a thin adapter translating its hook format.

**For runtimes with a pre-tool hook API:** add an adapter following the
existing Claude Code and OpenCode examples.

```text
tools/agent-guard/
  agent_guard/__init__.py        ← dispatch() core (harness-agnostic)
  agent_guard/adapters/
    claude.py                    ← reads stdin JSON, writes stdout JSON
    opencode.py                  ← reads stdin JSON, throws on block
    <your-runtime>.py            ← same shape; translate your hook format
```

The adapter must:
1. Parse the harness's pre-tool hook payload (stdin JSON, env vars, or
   CLI args — check the runtime docs).
2. Call `dispatch(command_string)` from the core.
3. Return the harness's expected "allow" or "block" response (format
   varies per harness).

Run the guard's test suite to verify the adapter:

```bash
uv run --project tools/agent-guard --group dev pytest
```

**For runtimes without a hook API:** document the limitation explicitly
in the row's notes in `skills/setup/agents.md`. An OS-level wrapper
(e.g. `bubblewrap` on Linux, `sandbox-exec` on macOS, or a custom
`PATH`-shadowing script that intercepts `git push` and `gh pr create`)
can enforce the rules at the process level without a harness hook. See
`tools/agent-isolation/agent-iso.sh` for the credential-stripping
pattern; extend it or write a sibling wrapper for the new runtime.

Whatever the enforcement mechanism, update the affected substrate tool
READMEs (step 4) to declare the new harness in their `**Harness:**` line
once support lands.

## Step 3 — add a spec-loop runner profile

The spec-loop (`tools/spec-loop/loop.sh`) runs the build/plan/update/
consolidate beats headlessly. Each runtime has a different flag for
"accept all permissions and run non-interactively." Add your runtime's
convention in two places.

**`tools/spec-loop/loop.sh` — harness detection:**

```bash
case "${SPEC_LOOP_HARNESS:-$(basename "$AGENT")}" in
    *codex*)      HARNESS=codex ;;
    *cursor*)     HARNESS=cursor ;;
    *gemini*)     HARNESS=gemini ;;
    *opencode*)   HARNESS=opencode ;;
    *<runtime>*)  HARNESS=<runtime> ;;    # add your case here
    *)            HARNESS=claude ;;
esac
```

**`tools/spec-loop/lib.sh` — headless invocation:**

Add a branch inside `spec_loop_launch_agent()` following the existing
patterns. Each branch runs the agent in the background (`&`) with:
- the auto-approve / skip-permissions flag for that runtime;
- `--model "$model"` forwarded when non-empty;
- the prompt fed via stdin, a file argument, or a flag — whatever the
  runtime accepts.

Example template:

```bash
elif [ "$harness" = "<runtime>" ]; then
    "$agent" <headless-flag> \
        ${model_args[@]+"${model_args[@]}"} \
        "$(cat "$prompt_file")" &
```

Validate the loop syntax after editing:

```bash
bash -n tools/spec-loop/loop.sh && bash -n tools/spec-loop/lib.sh
```

If the runtime supports a structured-output or JSON-stream mode
equivalent to Claude's `--output-format stream-json`, wire it via an
`$output_format` check (see the Cursor branch for an example).

## Step 4 — update tool harness declarations

Substrate tools that are harness-coupled declare `**Harness:**` in their
README. When your new runtime uses one of these tools, update its line:

| Tool | Current harness declaration |
|---|---|
| `tools/agent-guard` | `**Harness:** Claude Code, OpenCode` |
| `tools/agent-isolation` | `**Harness:** Claude Code, OpenCode` |
| `tools/permission-audit` | `**Harness:** Claude Code, OpenCode` |
| `tools/sandbox-lint` | `**Harness:** Claude Code, OpenCode` |
| `tools/spec-loop` | `**Harness:** Claude Code, Codex, Cursor, Gemini CLI, OpenCode` |

Add your runtime to every tool it integrates with. Tools that declare
`**Harness:** agnostic` need no change — they work under any runtime
unchanged. After updating, refresh the vendor-neutrality score:

```bash
uv run --project tools/vendor-neutrality-score vendor-neutrality-score --markdown
```

Copy the generated block into `docs/vendor-neutrality.md` as instructed
in its comment header.

## Step 5 — validate the full wiring

```bash
# 1. Symlink topology (no cycles, correct relay direction)
uv run --project tools/symlink-lint python3 -m symlink_lint

# 2. Skill + tool metadata (capability, prerequisites, organization lines)
uv run --project tools/skill-and-tool-validator --group dev skill-and-tool-validate

# 3. Guard tests (if you added a guard adapter in step 2)
uv run --project tools/agent-guard --group dev pytest

# 4. Loop syntax
bash -n tools/spec-loop/loop.sh && bash -n tools/spec-loop/lib.sh
```

All four must pass before opening a PR.

## Scope of a first-class harness integration

A minimal integration lands steps 1 + 3: skills load, the loop runs.
Steps 2 and 4 are what turn "skills load" into "skills run safely."
The recommended order for a community contribution:

1. **Open a tracking issue** (or claim the existing one for your
   runtime — see `docs/vendor-neutrality.md` § Agentic runtime for the
   issue list).
2. **Land the registry row + relay symlinks** (step 1) — small PR,
   unblocks users immediately.
3. **Land the loop profile** (step 3) — small PR, enables spec-loop
   use.
4. **Land the guard adapter or OS-level wrapper** (step 2) — the most
   harness-specific work; can be a follow-up PR.
5. **Update harness declarations** (step 4) — include in whichever PR
   lands the first substantive integration point.

This matches how Claude Code and OpenCode integrations were built: the
skill path landed first, then guard, then loop, then full harness table.

## See also

- [`skills/setup/agents.md`](../../skills/setup/agents.md) — the
  agent-target registry (single source of truth for symlink paths).
- [`tools/symlink-lint/`](../../tools/symlink-lint/) — enforces relay
  symlink correctness.
- [`tools/agent-guard/`](../../tools/agent-guard/) — the action guard
  core and per-harness adapters.
- [`tools/agent-isolation/`](../../tools/agent-isolation/) — the
  clean-environment launcher (OS-level complement to the agent hook).
- [`tools/spec-loop/loop.sh`](../../tools/spec-loop/loop.sh) and
  `lib.sh` — the spec-loop runner with per-harness invocation profiles.
- [`docs/vendor-neutrality.md`](../vendor-neutrality.md) § Agentic
  runtime — the open tracking issues per runtime and the neutrality
  rationale.
- [`docs/adapters/authoring.md`](authoring.md) — the analogous recipe
  for adding a new tool backend (forge, VCS, mail archive, CNA).
