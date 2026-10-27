<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [agent-guard](#agent-guard)
  - [Prerequisites](#prerequisites)
  - [Why a hook, not a rule in a SKILL.md](#why-a-hook-not-a-rule-in-a-skillmd)
  - [Guards](#guards)
  - [Per-command overrides](#per-command-overrides)
  - [Wiring](#wiring)
    - [Snapshot adopters (`/magpie-setup`)](#snapshot-adopters-magpie-setup)
    - [Codex](#codex)
    - [OpenCode](#opencode)
    - [Pi](#pi)
    - [Goose](#goose)
    - [Kiro CLI](#kiro-cli)
    - [Antigravity](#antigravity)
    - [Copilot CLI](#copilot-cli)
    - [Grok](#grok)
    - [Junie CLI](#junie-cli)
    - [Harness-neutral path (any runtime)](#harness-neutral-path-any-runtime)
  - [Contributing guards](#contributing-guards)
  - [Tests](#tests)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# agent-guard

**Capability:** substrate:action-guard

**Harness:** Claude Code, Codex, OpenCode, Pi, Goose, Kiro, Antigravity, Copilot, Grok, Junie

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
- **Pi** — Magpie's user-scope Pi extension, which sends every `bash` call to
  `agent-guard.py --pi` (the OpenCode transport) and blocks it on a deny.
  See [Pi](#pi).
- **Goose** — the Magpie Goose plugin's `PreToolUse` hook, which sends every
  `shell` call to `agent-guard.py --goose` (the same transport) and blocks it
  on a deny. See [Goose](#goose).
- **Kiro CLI** — a [`preToolUse`](https://kiro.dev/docs/cli/hooks) hook on the
  `execute_bash` matcher, which blocks a call when the hook exits `2`
  (`agent-guard.py --kiro`, reason on stderr). See [Wiring](#wiring).
- **Antigravity** — a [`PreToolUse`](https://antigravity.google/docs/hooks/)
  hook on `run_command`, using `--antigravity` (a JSON `deny` decision on
  stdout). The user-scope `~/.gemini/config/hooks.json` registers it once for
  every repository. See [Antigravity](#antigravity).
- **Grok Build** — a `PreToolUse` hook on the `Bash` matcher.
  Grok Build 1.0.46 was observed emitting `run_terminal_command` with the shell
  command in `toolInput.command`.
  Source/snapshot project hooks use `--grok`; marketplace plugin hooks are
  selected automatically from Grok's incoming hook payload shape.
  See [Grok](#grok).
- **Junie CLI** — a `PreToolUse` hook (Early Access) on the `Bash` matcher,
  using `--junie` (exit `2` plus a `decision` JSON and a stderr reason).
  See [Junie CLI](#junie-cli).
- **Any other runtime** — the `--check` and `--exec` CLI modes let any
  harness or shell wrapper enforce guard rules without a harness-specific hook
  adapter. See [Harness-neutral path (any runtime)](#harness-neutral-path-any-runtime).

It is **stdlib-only** and is invoked directly as
`python3 <path>/agent_guard/__init__.py` (never via `uv run`) so it returns in a
few milliseconds for any command that is not a guarded `gh` / `git commit` /
`git push` or a `uv` / `uvx` dispatcher launch.

## Prerequisites

- **Runtime:** Python stdlib only — the hook runs as `python3 .../agent_guard/__init__.py` (3.11+), never via `uv`, so it needs no built/installed environment. When that `python3` is older — typically an activated project virtualenv — the engine re-runs itself under the newest `python3.N` (3.11+) on `PATH`, or exits 1 with an actionable message when there is none. The test suite runs under `uv run --directory tools/agent-guard --group dev pytest`.
- **CLIs:** `git` and `gh` — the guards shell out (via `ctx.run`) to inspect commits, branch state, and GitHub Actions runs. None otherwise.
- **Credentials / auth:** None. The guards read local `git` / `gh` state; `gh` must be on `PATH` for the `mark-ready` guard's Actions lookup.
- **Network:** None in the hot path; the `mark-ready` guard reaches `api.github.com` (via `gh`) when it checks for awaiting-approval Actions runs.

## Why a hook, not a rule in a SKILL.md

A rule written in a `SKILL.md` is a sentence the model reads at the start of a
session and is *asked* to keep in mind — through forty tool calls, a
compaction, and an issue body that says something the model finds persuasive.
Most of the time it does. "Most of the time" is fine for a style preference and
useless for a rule whose violation posts to a public repository under the
operator's name, because the cost is not evenly spread: one slip is a
notification to four maintainers who did not ask for it, or a CVE identifier
visible before the embargo lifts.

So these rules are not prose. They are Python, in a hook the harness calls
before the shell tool runs, and they get a veto. The guard sees the exact
command, decides, and either lets it through or refuses — a refused command is
**not run**: not posted, not retried, and not worked around by rephrasing. The
model is shown the reason and the deterministic fix (*"use a backtick
`` `login` `` instead of `@login`"*), so it corrects rather than guesses.

This is also the layer that does not care *why* a command was issued. A
prompt-injected instruction in an issue body and an honest mistake produce the
same `gh pr comment`, and the guard treats them identically — which is what you
want from something whose job is to be unpersuadable.

It is not a substitute for the sandbox and does not overlap with it. The
sandbox confines what a command can *reach*; the guard decides whether it
*runs at all*. A sandbox has nothing to say about a command that is entirely
within its rights, and a guard has nothing to say about a command reading
`~/.ssh`.

## Guards

**Bundled** (shipped with the engine — universal `git` hygiene and the
dispatcher spelling, on for every project):

| Guard | Blocks | Rule it enforces |
|---|---|---|
| `commit-trailer` | `git commit` whose message contains `Co-Authored-By:`, unless the repository's [commit-attribution convention](../../docs/setup/commit-attribution.md) is `co-authored-by` | AGENTS.md: agents use the project's attribution trailer (default `Generated-by:`), not co-authorship |
| `empty-rebase` | `git push --force[-with-lease]` of a branch with 0 commits over its base | an empty push to a PR head auto-closes it + revokes write |
| `vetted-ops-spelling` | `uv run --project` / `uvx --from` (options on either side of `run`) launching `vetted-op`, `vetted-op-read`, `vetted-op-tracker` or `adversarial-review` from anything but the literal `~/.claude/magpie/<tool>` — an expanded home path, `$HOME/…`, or a checkout path, relative (`tools/vetted-ops`) or absolute inside the working tree; a quoted or escaped `~`; the right spelling behind `env` / `command` (the exclusion matches a line by its start); and `~/.claude/scripts/magpie-run-evals.sh` launched by any other path | AGENTS.md golden rule: the sandbox exclusions and permission rules name only the `~` spelling. Under Codex, a `vetted-op-read` launched from the exact root its own [rewrite hook](../vetted-ops/hooks/codex-expand-stable-path.py) is registered with (`--stable-path` in the Codex configuration, else the account's home) is let through |

**Skill-owned** (each lives in its skill's `guards/` dir, discovered the same
way — see [Contributing guards](#contributing-guards)):

| Guard | Owner skill | Blocks | Rule it enforces |
|---|---|---|---|
| `mention` | `pr-management-triage` | `gh pr comment` / `gh issue comment` that `@`-mentions anyone other than the PR/issue author; **any** `@`-mention in `gh pr edit --body[-file]` | denoise: author-directed feedback never pings maintainers; body edits stay silent. Exempt: the operator commenting on their **own** PR/issue (author == authenticated `gh` user), and the `MAGPIE_ALLOW_MENTIONS=1` override |
| `mark-ready` | `pr-management-triage` | adding `ready for maintainer review` while the PR head SHA has GitHub Actions runs awaiting approval | Golden rule 1b |
| `security-language` | `security-issue-fix` | a CVE id / security-fix language in a **public** `gh pr create`/`gh pr edit` title/body (not comments) | public-PR scrubbing |

A denied command is **not** posted/run; the model is shown the reason and the
deterministic fix (e.g. "use a backtick `` `login` `` instead of `@login`").

Every guard sees through the prefix wrappers that run their argument as the
command: `env` (with `-i`, `-u NAME`, `-C DIR` and `NAME=value` assignments,
which count as inline overrides), `command` (`-p`), `exec` (`-c`, `-l`,
`-a NAME`), `nohup`, and `time` (the shell keyword's `-p` and the GNU / BSD
`time` options). `env git commit …` is checked as `git commit …`;
`command -v git` is a lookup and is left alone.
A wrapper the guards cannot parse is refused (`agent-guard[wrapper]`). That
includes `env -S` / `--split-string`: env splits that string with its own
escapes (`\_`, `\c`, `${VAR}`), so the guards could not be sure they see the
command env runs.

A command line is split into commands the way bash splits it: on a newline and
on every control operator (`;`, `&`, `|`, `&&`, `||`, `|&`, `;;`), whether or
not spaces surround it, so `echo hi;git push` and a `git` command on the second
line are both checked. Redirections (`2>&1`, `&>file`, `>|`) stay words,
quoted text and `#` comments are not commands, and a leading reserved word
(`if`, `then`, `do`, `{`, `!` …) is skipped. A subshell `( … )`, a command or
process substitution (`$( … )`, backticks, `<( … )`, also inside double quotes
and `$(( … ))` / `${ … }`), and a heredoc body fed to anything but a bare `cat`
/ `tee` are checked as commands of their own, as is a substitution in a heredoc
body whose delimiter is unquoted.

A shell's `-c` string (`bash -c "…"`, `sh -c '…'`, `zsh -lc "…"`), or the joined arguments of `eval` (after one `--`; also behind any chain of `builtin`, `command`, `--` and `-p`; an option anywhere else in front of the string is refused), is split
and checked like a command line of its own, and inherits the inline
assignments written before the shell. That goes one level deep: a `-c` string
inside a `-c` string that names `git` or `gh` is refused (`agent-guard[wrapper]`).

A command line whose quoting cannot be parsed (an unbalanced quote, a trailing
backslash) is refused when it names `git` or `gh` as a word
(`agent-guard[parse]`): the guards cannot see what it runs.
Quotes and backslashes are removed before that check, as bash removes them,
so `g'i't` and `"g"h` count as `git` and `gh`; such a line holding `$`, a
backtick, a glob or brace character (`*`, `?`, `[`, `{`) or a
backslash-newline is refused too, since an expansion can build the word
(`g$()it`, `$CMD`, `/usr/bin/gi?`). Simplify the
quoting, for example by passing a multi-line message with `-F <file>` /
`--body-file <file>`. Any other unparsable line is allowed, as before.
A heredoc's body is data, not shell syntax: an apostrophe in it does not make
the line unparsable. That holds for a body naming `git` or `gh` only when it is
fed to a bare `cat`, `/bin/cat`, `/usr/bin/cat` or `tee` (plain file arguments
and `>` / `>>` only) that starts a command rather than continuing the line
before, in a command that, without its heredoc bodies, holds no `$`, backtick,
parenthesis or brace, no `alias`, and no `eval`, `source`, `.`, `hash` or
`enable` as a word anywhere (after quote removal), in which every other heredoc
is such a sink too, and,
under an unquoted delimiter, holds no `$(…)` or backtick substitution (bash
runs those); never for a heredoc that is not closed, and never in a command
where any line outside a heredoc body ends in a backslash: bash joins that line
with the next, so a `#` at the start of the next line may sit mid-word rather
than open a comment.
A `<<` inside quotes, a `#` comment, arithmetic (`$((…))`, `$[…]`) or a
`${…}` expansion opens no heredoc, so the lines after it are read as commands,
as bash reads them. The delimiter is the whole word after quote removal
(`E"O"F` is `EOF`); a delimiter holding `$` or a backtick is not stripped.
The guard reads one command string, so a `cat` heredoc that writes a script
which a later command runs is beyond it: the agent could write that file with
its own file tools just as well.

## Per-command overrides

Each guard is overridable by a **visible inline env assignment** so a maintainer
can consciously proceed:

```bash
MAGPIE_ALLOW_MENTIONS=1     gh pr comment 123 --body "@reviewer please take another look"
MAGPIE_ALLOW_COAUTHOR=1     git commit -m "…"            # not for AI co-authorship
MAGPIE_ALLOW_MARK_READY=1   gh pr edit 123 --add-label "ready for maintainer review"
MAGPIE_ALLOW_SECURITY_LANG=1 gh pr create --title "…"    # disclosure already public
MAGPIE_ALLOW_EMPTY_PUSH=1   git push --force …
MAGPIE_ALLOW_VETTED_PATH=1  uv run --project tools/vetted-ops vetted-op-read …  # developing the dispatcher
```

Each `MAGPIE_ALLOW_*` override is also honoured when it is set in the hook's own
environment.

`MAGPIE_GUARD_OFF=1` disables every guard at once.
The kill switch is read from the hook's environment only — the environment the
harness starts the hook with, set by whoever launches the agent — never from the
command line: `MAGPIE_GUARD_OFF=1 git commit …` written inline is checked like
`git commit …`.

`MAGPIE_READY_LABEL` overrides the label string the `mark-ready` guard watches
for (default `ready for maintainer review`).

## Wiring

Install the `magpie-agent-guard` plugin:

```text
/plugin marketplace add apache/magpie
/plugin install magpie-agent-guard@apache-magpie
```

That is the whole installation.
The plugin's
[`hooks/hooks.json`](../../plugins/magpie-agent-guard/hooks/hooks.json)
registers the `PreToolUse` hook and resolves the engine from the plugin root
with `${GROK_PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}`, so the guard runs out of
the installed plugin. **No
file is copied into any repository, no `settings.local.json` entry is written,
and a git worktree needs no seeding** — it is an ordinary checkout, and the
guard is active in it the moment the plugin is installed.

Skill-owned guards work the same way: the engine discovers every
`skills/<skill>/guards` in the framework tree it is running from, so a skill's
guards take effect where they live and nothing collects or syncs them.
A marketplace install has no such tree — it caches each plugin on its own, as
`<marketplace>/<plugin>/<version>/` — so the engine scans the
`skills/*/guards` of the family plugins installed beside its own, at its own
version (they are released together), else at their most recently installed one.

The guard is its own plugin rather than a hook on `magpie` or on each family
plugin because Claude Code merges hooks from **every** enabled plugin — wiring it
into the families would run it once per enabled family on every `Bash` call. One
dedicated owner runs it exactly once, whatever else is installed.

### Snapshot adopters (`/magpie-setup`)

A project that vendors the framework as a snapshot rather than installing the
plugin wires the hook by hand, in the gitignored, per-machine
`.claude/settings.local.json`. Point it at the **snapshot's** engine, not at a
per-repository copy:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          { "type": "command", "command": "python3 \"$CLAUDE_PROJECT_DIR/.apache-magpie/tools/agent-guard/src/agent_guard/__init__.py\"", "timeout": 30 }
        ]
      }
    ]
  }
}
```

Every worktree already symlinks `.apache-magpie/` to the main checkout's
snapshot ([`worktree-init`](../../skills/setup/worktree-init.md)), so this path
resolves in a worktree without seeding anything else. `/magpie-setup upgrade`
refreshes the engine with the rest of the snapshot.

The user-scope secure setup installs the engine once at
`~/.claude/scripts/agent-guard.py` and wires it from `~/.claude/settings.json`;
that path is worktree- and repository-independent by construction. See
[`setup-isolated-setup-install`](../../skills/setup-isolated-setup-install/SKILL.md).

### Codex

Codex supports native synchronous `PreToolUse` hooks with the canonical `Bash` event and `tool_input.command`.
Register `python3 <engine-path>/__init__.py --codex` in `.codex/config.toml`, resolving the engine from the git root for source or snapshot installs.
The marketplace plugin’s existing Claude-compatible hook also works in Codex without a second registration.
The explicit adapter emits a native JSON deny on guard hits and no output on ordinary calls, leaving Codex approvals in charge.
See the [Codex adapter](../../docs/adapters/codex.md#deterministic-guard-rules) for wiring, trust review, and verification.

Prefer the installed plugin or user-scope engine outside writable roots for routine adopter sessions.
A project source or snapshot engine can be edited by the agent without changing the trusted hook definition; report that limitation during verification.
Use `/hooks` to trust the current definition after install or changes.
Project trust alone does not activate an untrusted hook.
Hook errors and timeouts are non-blocking in Codex, and interactive `write_stdin` input is not rechecked.

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

### Pi

Pi has no hook configuration of its own; extensions intercept tool calls.
Magpie's Pi extension, [`tools/agent-isolation/pi/magpie.ts`](../agent-isolation/pi/magpie.ts),
sends every `bash` command to `agent-guard.py --pi` before it runs and blocks
the call on exit `2`, using the reason the engine prints on stdout. `--pi`
shares the `{"command", "cwd"}` stdin transport with `--opencode`, so the
decisions and reasons are identical; a missing engine or interpreter fails
open, like every other adapter.

The extension is installed **once per user**, never per repository, by the
framework's Pi package:

```bash
pi install git:github.com/apache/magpie
```

It resolves the engine relative to its own file, so the installed package
carries everything it runs. The same extension adds the permission rules and
the OS sandbox for bash; see [the Pi harness](../../docs/adapters/pi.md).

### Goose

Goose runs hooks shipped in a plugin. The Magpie Goose plugin's
[`hooks/hooks.json`](../../hooks/hooks.json) registers a `PreToolUse` hook,
[`tools/agent-isolation/goose/hook.ts`](../agent-isolation/goose/hook.ts),
which sends every `shell` command to `agent-guard.py --goose` before it runs
and blocks the call on exit `2`, using the reason the engine prints on stdout.
`--goose` shares the `{"command", "cwd"}` stdin transport with `--opencode`
and `--pi`, so the decisions and reasons are identical; a missing engine fails
open, like every other adapter, while a crash of the hook itself fails closed
(`on_failure: block`).

The plugin is installed **once per user**, never per repository:

```bash
goose plugin install https://github.com/apache/magpie
```

The same hook applies the baseline's deny rules, and `agent-iso goose` runs the
whole Goose process in an OS sandbox; see [the Goose harness](../../docs/adapters/goose.md).

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
Note: `/magpie-setup:setup` currently installs the engine only on the Claude path — a
general installer that drops it for non-Claude-only adopters is a pending
follow-up (see [`docs/adapters/add-a-harness.md`](../../docs/adapters/add-a-harness.md)).

Because every harness calls `dispatch()`, the bundled and skill-contributed
guards, the `MAGPIE_*` overrides, and the deny reasons are identical to the
Claude Code and OpenCode paths — verified end-to-end: with this hook wired,
Kiro refuses a `Co-Authored-By` commit (quoting the `commit-trailer` reason and
leaving the commit uncreated) while a clean commit proceeds.

### Antigravity

The same engine backs [Antigravity](https://antigravity.google/docs/hooks/) (CLI, App and IDE) via its `PreToolUse` hook on the `run_command` tool.
Antigravity pipes the event on stdin — the shell command is `toolCall.args.CommandLine`, the workspace roots are `workspacePaths` — and reads a JSON decision from stdout.
`agent-guard.py --antigravity` runs the shared core and prints `{"decision": "deny", "reason": …}` on a deny, which blocks the call and returns the reason to the model; anything else prints `{"decision": "allow"}`, which defers to the user's own permission rules rather than approving the call.
The hook runs with its `hooks.json` directory as the working directory, so Git checks use the command's `Cwd`, else the first workspace root.

The guard is registered **once per user**, in `~/.gemini/config/hooks.json`, never per repository.
The shipped registration is [`tools/agent-isolation/antigravity/hooks.json`](../agent-isolation/antigravity/hooks.json); the [`setup-isolated-setup-install`](../../skills/setup-isolated-setup-install/SKILL.md) skill merges it while preserving unrelated hooks.
It points at the engine inside the installed Magpie plugin:

```json
{
  "magpie-agent-guard": {
    "PreToolUse": [
      {
        "matcher": "run_command",
        "hooks": [
          {
            "type": "command",
            "command": "python3 \"${HOME}/.gemini/config/plugins/magpie/tools/agent-guard/src/agent_guard/__init__.py\" --antigravity",
            "timeout": 30
          }
        ]
      }
    ]
  }
}
```

Antigravity runs the hook command through a shell, so `${HOME}` expands and the file carries no username.
For a framework checkout or snapshot instead of the plugin, replace the path with that tree's engine.
Verified against Antigravity CLI 1.3.6 on macOS: `agy plugin install` staged the engine at the path above, the hook received the event, a deny blocked the command with the reason shown to the model, and an allow fell through to the permission prompt.

A missing interpreter or script leaves the session running, so verify a known denial after installation.
The hook covers shell commands; native file, browser and MCP tools still need the permission rules, and shell execution still needs the terminal sandbox.
See the [harness contract](../../docs/adapters/antigravity.md).

### Copilot CLI

The repository's [`.github/hooks/magpie.json`](../../.github/hooks/magpie.json)
wires the `--copilot` adapter to Copilot CLI's `preToolUse` event (the
PascalCase `PreToolUse` payload is accepted too).
The adapter prints one JSON decision on stdout and exits `0`:

- a guard hit → `permissionDecision: "deny"` with the reason;
- one simple read-only command (`gh pr view`, `gh issue list`, `gh search`,
  `git status/diff/log`, GET-only `gh api`, `vetted-op-read`) →
  `"allow"`, so reads never prompt;
- anything else, including any compound command or write → no output, and
  Copilot's normal permission flow decides.

Manual registration, with the path replaced by the resolved framework directory:

```json
{
  "version": 1,
  "hooks": {
    "preToolUse": [
      {
        "type": "command",
        "bash": "python3 \"/absolute/path/to/magpie/tools/agent-guard/src/agent_guard/__init__.py\" --copilot",
        "timeoutSec": 10
      }
    ]
  }
}
```

See [the Copilot install lifecycle](../../docs/adapters/copilot.md#install).

### Grok

The setup project-hook template
[`plugins/magpie-setup/templates/grok-agent-guard-hook.json`](../../plugins/magpie-setup/templates/grok-agent-guard-hook.json)
uses Grok's `PreToolUse` event with the `Bash` matcher and invokes `--grok`.
The Magpie repository itself relies on the enabled marketplace plugin instead,
so it does not also commit the active project hook.
The payload contract was verified with Grok Build 1.0.46
(`2765805b9442`) using a real captured event whose concrete shell tool was
`run_terminal_command`. Marketplace/plugin loading and failure behavior were
additionally verified on Grok Build 1.0.50 (`c58f321264ba`).

Grok sends the command in `toolInput.command`.
The adapter forwards that command and an optional string `cwd` to the shared
`dispatch()` core.
A guard hit returns Grok's deny decision with the shared reason.
An allowed shell command exits 0 without emitting a decision.

Marketplace installs do not need a second repository-local hook merely to reach
the executable.
The plugin registers its Grok-compatible hook in `hooks/hooks.json`, resolves
the bundled runtime with `${GROK_PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}`, and
selects the Grok adapter from the incoming camelCase hook payload.
The runtime is materialized as real files inside the plugin because Grok's
local plugin installation does not preserve the former out-of-root symlink.

Framework checkouts and pinned snapshots may use the Magpie-owned project hook.
Project hooks remain trust-gated by Grok.
Magpie must never grant or reset that trust on the operator's behalf.

Malformed or unrelated events handled inside the adapter fail open by
returning exit 0.

Hook-process failure is different. On Grok Build 1.0.50, a bare exit 2 with no
deny JSON blocked the shell tool call, and a missing Python hook target that
exited 2 was also blocked. Installation verification should still include a
known live denial so wiring, packaging, and runtime policy are exercised
together.

See the [Grok adapter contract](../../docs/adapters/grok.md).

### Junie CLI

Junie's `PreToolUse` payload is Claude-shaped (`tool_name`, `tool_input.command`),
so the no-argument dispatcher would route it to the Claude adapter,
whose `hookSpecificOutput` deny Junie ignores and exit 0 would let the command run.
Junie hooks must therefore invoke `--junie` explicitly.
The adapter blocks with exit `2`, the one signal Junie honours regardless of output,
and also prints a `decision` JSON and the reason on stderr.
Other non-zero exits only warn in Junie, so the adapter never uses them.
See [the Junie adapter](../../docs/adapters/junie.md).

### Harness-neutral path (any runtime)

For runtimes without a wired pre-tool hook adapter, the engine ships two
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
tree) or at the path `/magpie-setup:setup` ships it to (`.claude/hooks/agent-guard.py`
for Claude Code setups — the file is the same and works for all three modes).

## Contributing guards

The hook is **wired once**. Beyond the two bundled guards, additional guards are
discovered at runtime from every `*.py` in a discovered guard directory — any
directory listed in `$MAGPIE_GUARD_DIRS` (colon-separated), then every
`plugins/*/skills/*/guards` and `skills/*/guards` in the framework tree the
engine runs from (or, from a marketplace install, in the family plugins cached
beside it), then the
`guards.d` sibling of the running script. **No `settings.json` change and no
install step is needed to add a guard.**

A skill owns its guards by shipping them under `skills/<skill>/guards/*.py`.
The engine discovers them there — it resolves the framework tree it is running
from and scans every `skills/*/guards` in it, alongside its own bundled
`guards.d`. Nothing collects or copies them, so a new guard is live as soon as
the framework is. (A single self-contained copy of the engine, with no framework
tree above it, sees only its own `guards.d` and whatever `$MAGPIE_GUARD_DIRS`
names.) A guard file is **import-free** — it defines:

- `TRIGGERS` — optional list of command families to pre-filter on (`"gh"`,
  `"git:commit"`, `"git:push"`, …); omit to run on every guarded command.
- `guard(ctx)` — returns a deny-reason string to block, or `None` to allow.
  `ctx` is the `GuardContext`: `ctx.argv`, `ctx.raw`, `ctx.override(*names)`,
  `ctx.gh_subcommand()`, `ctx.opt(short, long)` (first value),
  `ctx.opts(short, long)` (every value of a repeated flag), `ctx.gh_body(...)`,
  `ctx.mentions(text)`, `ctx.positional_after(token)`, `ctx.repo_flag()`,
  `ctx.run(args)`, `ctx.ready_label`.

A guard file that fails to import is skipped (a broken contribution never breaks
the shell). See `guards.d/no_verify_commit.py` for the template, and
`skills/pr-management-triage/guards/` for real examples.

## Tests

```bash
uv run --directory tools/agent-guard --group dev pytest
```

Table-driven tests feed synthetic `PreToolUse` events to `dispatch()` and assert
allow vs. deny. The `gh` / `git` lookups the guards make are monkeypatched.
