<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [agent-guard](#agent-guard)
  - [Prerequisites](#prerequisites)
  - [Guards](#guards)
  - [Per-command overrides](#per-command-overrides)
  - [Wiring](#wiring)
    - [OpenCode](#opencode)
    - [Kiro CLI](#kiro-cli)
    - [Harness-neutral path (any runtime)](#harness-neutral-path-any-runtime)
  - [Contributing guards](#contributing-guards)
  - [Tests](#tests)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# agent-guard

**Capability:** substrate:action-guard

**Harness:** Claude Code, OpenCode, Kiro

A deterministic pre-execution guard dispatcher. It inspects every shell command
**before it runs** and **denies** the ones that would break a hard framework
rule — protections that must not depend on the model remembering a `SKILL.md`
instruction.

The guard *decisions* live in one harness-agnostic core (`dispatch()`); a thin
adapter per harness translates that harness's pre-tool hook to/from the core,
so every wired harness enforces an identical rule set from one source of truth:

- **Claude Code** — a [`PreToolUse`](https://code.claude.com/docs/en/hooks)
  hook on the `Bash` matcher (the default, no-argument invocation).
- **OpenCode** — a [plugin](https://opencode.ai/docs/plugins/) on the
  `tool.execute.before` hook for the `bash` tool, which blocks a call by
  throwing (`agent-guard.py --opencode`). See [Wiring](#wiring).
- **Kiro CLI** — a [`preToolUse`](https://kiro.dev/docs/cli/hooks) hook on the
  `execute_bash` matcher, which blocks a call when the hook exits `2`
  (`agent-guard.py --kiro`, reason on stderr). See [Wiring](#wiring).
- **Any other runtime** — the `--check` and `--exec` CLI modes let any
  harness or shell wrapper enforce guard rules without a harness-specific hook
  adapter. See [Harness-neutral path (any runtime)](#harness-neutral-path-any-runtime).

It is **stdlib-only** and is invoked directly as
`python3 <path>/agent_guard/__init__.py` (never via `uv run`) so it returns in a
few milliseconds for any command that is not a guarded `gh` / `git commit` /
`git push`.

## Prerequisites

- **Runtime:** Python stdlib only — the hook runs as `python3 .../agent_guard/__init__.py` (3.11+), never via `uv`, so it needs no built/installed environment. The test suite runs under `uv run --project tools/agent-guard pytest`.
- **CLIs:** `git` and `gh` — the guards shell out (via `ctx.run`) to inspect commits, branch state, and GitHub Actions runs. None otherwise.
- **Credentials / auth:** None. The guards read local `git` / `gh` state; `gh` must be on `PATH` for the `mark-ready` guard's Actions lookup.
- **Network:** None in the hot path; the `mark-ready` guard reaches `api.github.com` (via `gh`) when it checks for awaiting-approval Actions runs.

## Guards

**Bundled** (shipped with the engine — universal `git` hygiene, on for every
project):

| Guard | Blocks | Rule it enforces |
|---|---|---|
| `commit-trailer` | `git commit` whose message contains `Co-Authored-By:` | AGENTS.md: agents use a `Generated-by:` trailer, never co-author |
| `empty-rebase` | `git push --force[-with-lease]` of a branch with 0 commits over its base | an empty push to a PR head auto-closes it + revokes write |

**Skill-owned** (each lives in its skill's `guards/` dir, discovered the same
way — see [Contributing guards](#contributing-guards)):

| Guard | Owner skill | Blocks | Rule it enforces |
|---|---|---|---|
| `mention` | `pr-management-triage` | `gh pr comment` / `gh issue comment` that `@`-mentions anyone other than the PR/issue author; **any** `@`-mention in `gh pr edit --body[-file]` | denoise: author-directed feedback never pings maintainers; body edits stay silent. Exempt: the operator commenting on their **own** PR/issue (author == authenticated `gh` user), and the `MAGPIE_ALLOW_MENTIONS=1` override |
| `mark-ready` | `pr-management-triage` | adding `ready for maintainer review` while the PR head SHA has GitHub Actions runs awaiting approval | Golden rule 1b |
| `security-language` | `security-issue-fix` | a CVE id / security-fix language in a **public** `gh pr create`/`gh pr edit` title/body (not comments) | public-PR scrubbing |

A denied command is **not** posted/run; the model is shown the reason and the
deterministic fix (e.g. "use a backtick `` `login` `` instead of `@login`").

## Per-command overrides

Each guard is overridable by a **visible inline env assignment** so a maintainer
can consciously proceed:

```bash
MAGPIE_ALLOW_MENTIONS=1     gh pr comment 123 --body "@reviewer please take another look"
MAGPIE_ALLOW_COAUTHOR=1     git commit -m "…"            # not for AI co-authorship
MAGPIE_ALLOW_MARK_READY=1   gh pr edit 123 --add-label "ready for maintainer review"
MAGPIE_ALLOW_SECURITY_LANG=1 gh pr create --title "…"    # disclosure already public
MAGPIE_ALLOW_EMPTY_PUSH=1   git push --force …
MAGPIE_GUARD_OFF=1          <any command>                # disable all guards once
```

`MAGPIE_READY_LABEL` overrides the label string the `mark-ready` guard watches
for (default `ready for maintainer review`).

## Wiring

The guard is registered as a `PreToolUse` hook on the `Bash` matcher in
`.claude/settings.json`:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          { "type": "command", "command": "python3 -c \"import os,sys,subprocess; p=os.path.join(os.environ.get('CLAUDE_PROJECT_DIR',''),'.claude','hooks','agent-guard.py'); sys.exit(subprocess.call([sys.executable,p]) if os.path.isfile(p) else 0)\"", "timeout": 30 }
        ]
      }
    ]
  }
}
```

`/magpie-setup` ships `agent_guard/__init__.py` as a single self-contained file
into the adopter tree (`.claude/hooks/agent-guard.py`) and into the user-scope
secure setup (`~/.claude/scripts/agent-guard.py`); `/magpie-setup upgrade`,
`verify`, and the `setup-isolated-setup-install` / `…-update` skills keep it and
the settings.json entry in sync. See those skills for the exact steps.

### OpenCode

The same engine backs OpenCode via the plugin in
[`opencode/plugin.js`](opencode/plugin.js). OpenCode aborts a tool call whose
[`tool.execute.before`](https://opencode.ai/docs/plugins/) handler throws, so
the plugin forwards each `bash` command to `agent-guard.py --opencode` and
throws with the deny reason when the shared core denies it — the OpenCode
equivalent of a Claude `PreToolUse` deny.

Drop the plugin into OpenCode's plugin directory (`.opencode/plugin/` in the
project, or `~/.config/opencode/plugin/` globally):

```bash
mkdir -p .opencode/plugin
ln -s "<framework>/tools/agent-guard/opencode/plugin.js" .opencode/plugin/agent-guard.js
```

The plugin locates the engine at `.claude/hooks/agent-guard.py` under the
worktree by default — so a repo already wired for Claude Code needs no second
copy of the script — and honours `MAGPIE_AGENT_GUARD=/abs/path/agent-guard.py`
to point elsewhere. Because both harnesses call `dispatch()`, the bundled and
skill-contributed guards, the `MAGPIE_*` overrides, and the deny reasons are
byte-for-byte identical across the two; nothing about a guard is harness-aware.

### Kiro CLI

The same engine backs [Kiro CLI](https://kiro.dev/docs/cli/hooks) via its
`preToolUse` hook. Kiro pipes the hook event
(`{"tool_name": "execute_bash", "tool_input": {"command": …}, "cwd": …}`) to
the hook command on stdin and **blocks** the tool call when that command exits
`2`, returning its stderr to the model — so `agent-guard.py --kiro` matches the
shell tool, runs the shared core, and on a deny writes the reason to stderr and
exits `2`, the Kiro equivalent of a Claude `PreToolUse` deny.

Register it in the agent configuration's `hooks` field
([reference](https://kiro.dev/docs/cli/custom-agents/configuration-reference#hooks-field)):

```json
{
  "hooks": {
    "preToolUse": [
      {
        "matcher": "execute_bash",
        "command": "python3 \"${MAGPIE_AGENT_GUARD:-.claude/hooks/agent-guard.py}\" --kiro"
      }
    ]
  }
}
```

The engine is one shared, harness-agnostic file (`--kiro` only selects the I/O
adapter). On a repo already wired for Claude Code it lives at
`.claude/hooks/agent-guard.py`, so the hook reuses it; a **Kiro-only** adopter
(no `.claude/`) points `MAGPIE_AGENT_GUARD` at wherever the engine is installed.
Note: `/magpie-setup` currently installs the engine only on the Claude path — a
general installer that drops it for non-Claude-only adopters is a pending
follow-up (see [`docs/adapters/add-a-harness.md`](../../docs/adapters/add-a-harness.md)).

Because every harness calls `dispatch()`, the bundled and skill-contributed
guards, the `MAGPIE_*` overrides, and the deny reasons are identical to the
Claude Code and OpenCode paths — verified end-to-end: with this hook wired,
Kiro refuses a `Co-Authored-By` commit (quoting the `commit-trailer` reason and
leaving the commit uncreated) while a clean commit proceeds.

### Harness-neutral path (any runtime)

For runtimes that do not expose a pre-tool hook API (Codex CLI, Gemini CLI,
Cursor, Kiro, or any other harness not yet wired above), the engine ships two
CLI modes that allow enforcement without a harness-specific adapter:

**`--check <command…>`** — inspects the command and reports allow/deny without
executing it. Exits `0` on allow (silent), `2` on deny (reason on stdout), or
`64` (usage) when no command is supplied — `64` is deliberately distinct from
the deny code so a caller testing `$? -eq 2` never mistakes a misinvocation for
a policy block. Shell scripts and wrappers can inspect the exit code before
proceeding:

```bash
reason=$(python3 /path/to/agent-guard.py --check git push origin main)
if [ $? -eq 2 ]; then
  echo "blocked: $reason" >&2
  exit 1
fi
git push origin main
```

**`--exec <command…>`** — inspects the command then exec-replaces this process
with it on allow. On deny it prints the reason to stderr and exits `2`. The
exec'd command's own exit code and output are indistinguishable from a direct
invocation, making `--exec` suitable as a transparent wrapper:

```bash
# Shell alias in project .envrc / .bashrc. Safe: aliases are invisible to the
# execvp that --exec uses, so the bare name resolves to the real binary.
alias git='python3 /path/to/agent-guard.py --exec git'
alias gh='python3 /path/to/agent-guard.py --exec gh'

# Wrapper script named 'git' earlier on $PATH than the real one. It MUST exec
# the real git by ABSOLUTE path — passing the bare name 'git' would make --exec
# re-resolve it through $PATH, find this wrapper again, and loop. Adjust the
# path to your real git (`command -v git` with this wrapper off $PATH).
#!/usr/bin/env bash
exec python3 "${MAGPIE_AGENT_GUARD:-/path/to/agent-guard.py}" --exec /usr/bin/git "$@"
```

Both modes use the same `dispatch()` core as the Claude Code and OpenCode
adapters, so the guard decisions are identical regardless of which path you use.
Both are **fail-open**: a guard glitch never hard-blocks the user (and `--exec`
bounds any accidental wrapper recursion instead of looping forever).

Locate the engine at `agent_guard/__init__.py` inside the framework snapshot
(`.apache-magpie/tools/agent-guard/src/agent_guard/__init__.py` in an adopter
tree) or at the path `/magpie-setup` ships it to (`.claude/hooks/agent-guard.py`
for Claude Code setups — the file is the same and works for all three modes).

## Contributing guards

The hook is **wired once**. Beyond the two bundled guards, additional guards are
discovered at runtime from every `*.py` in a `guards.d` directory — the
`guards.d` sibling of the running script, plus any directory listed in
`$MAGPIE_GUARD_DIRS` (colon-separated). **No `settings.json` change is needed to
add a guard.**

A skill owns its guards by shipping them under `skills/<skill>/guards/*.py`;
`/magpie-setup` collects every `skills/*/guards/*.py` (plus the engine's bundled
`guards.d`) into the adopter's `.claude/hooks/guards.d/` (and the user-scope
`~/.claude/scripts/guards.d/`). A guard file is **import-free** — it defines:

- `TRIGGERS` — optional list of command families to pre-filter on (`"gh"`,
  `"git:commit"`, `"git:push"`, …); omit to run on every guarded command.
- `guard(ctx)` — returns a deny-reason string to block, or `None` to allow.
  `ctx` is the `GuardContext`: `ctx.argv`, `ctx.raw`, `ctx.override(*names)`,
  `ctx.gh_subcommand()`, `ctx.opt(short, long)`, `ctx.gh_body(...)`,
  `ctx.mentions(text)`, `ctx.positional_after(token)`, `ctx.repo_flag()`,
  `ctx.run(args)`, `ctx.ready_label`.

A guard file that fails to import is skipped (a broken contribution never breaks
the shell). See `guards.d/no_verify_commit.py` for the template, and
`skills/pr-management-triage/guards/` for real examples.

## Tests

```bash
uv run --project tools/agent-guard pytest
```

Table-driven tests feed synthetic `PreToolUse` events to `dispatch()` and assert
allow vs. deny. The `gh` / `git` lookups the guards make are monkeypatched.
