<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Adversarial review by other models, before every PR](#adversarial-review-by-other-models-before-every-pr)
  - [What is wrong](#what-is-wrong)
  - [Decisions](#decisions)
  - [The tool](#the-tool)
    - [Backends](#backends)
    - [The prompt and the findings](#the-prompt-and-the-findings)
  - [Data flow before a PR is created](#data-flow-before-a-pr-is-created)
  - [Configuration](#configuration)
  - [Per-harness commands](#per-harness-commands)
  - [Sandbox](#sandbox)
  - [Consumers](#consumers)
  - [Testing](#testing)
  - [Rollout](#rollout)
  - [Alternatives considered](#alternatives-considered)
  - [Risks](#risks)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Adversarial review by other models, before every PR

| | |
|---|---|
| **Status** | Being built: the tool and plugin (PR 1 of 4, apache/magpie#1366), then `setup` (PR 2 of 4). Plan: [`2026-09-23-adversarial-review-plan.md`](2026-09-23-adversarial-review-plan.md). |
| **Scope** | A new tool (`tools/adversarial-review`) and substrate plugin, the `setup` family (detection, configuration, per-harness commands), a shared pre-PR block included by every PR-creating skill, and an optional multi-reviewer second read in `pr-management-code-review`. |

## What is wrong

Magpie can pair a change with a second model's review, but only one way and only in one place.
`pr-management-code-review` accepts a single user-typed slash command (`with-reviewer:/…`, or a *Review preferences* heading in agent instructions), and the maintainer has to fire it by hand because the assistant cannot invoke slash commands.
The only reviewer in common use is the Claude Code Codex plugin's `/codex:adversarial-review`.

That leaves four gaps:

- **One reviewer at a time.** A maintainer who wants Codex *and* Copilot to read a change has no way to say so.
- **No reviewer outside Claude Code.** A maintainer running Magpie in Codex CLI, Gemini CLI or Copilot has no equivalent command, and in particular no way to ask Claude for the adversarial read.
- **Only in code review.** The PRs Magpie itself opens — a security fix from `security-issue-fix`, a framework fix from `setup-upstream-fix`, an override promotion from `setup-override-upstream` — get no second model's read at all, even though they are exactly the changes that land in front of the most people with the least review.
- **Nothing detects what is installed.** The maintainer has to know which reviewer plugin exists and type its exact command name.

## Decisions

1. **A standalone capability, not part of review.** Adversarial review is its own tool and plugin. `code-review` is one consumer of it; PR-creating skills are the main one.
2. **One shared tool, thin per-harness commands.** `tools/adversarial-review` owns detection, the prompt, the backend command lines, output parsing and merging. Per-harness commands only call it.
3. **Runs by default before a PR is created.** Every Magpie skill that opens a PR runs the configured reviewers against the branch about to be pushed, through one shared block. The security family always does so when any reviewer is configured; other families follow the configured `mode`.
4. **The agent runs it; the harness permission prompt gates it.** The skill invokes the tool through Bash, so no slash command has to be typed. The per-harness commands still exist for ad-hoc use.
5. **No privacy-llm gate — because the input is only what the PR will publish.** The reviewer sees the diff, the changed-file list and the PR title and body *as they will be posted*. Nothing private is ever passed: no tracker content, CVE ID, reporter detail, advisory text or security framing. The privacy-llm gate exists to stop private data reaching an unapproved model; with the input limited to public-bound content there is no private data to stop.
6. **Advisory, never blocking.** Findings are shown next to the diff before the push. The human decides what to act on. An unavailable reviewer, or none at all, never stops the PR.
7. **The running model is excluded.** A reviewer is only useful as a *different* model; the harness's own model is detected and skipped by default.

## The tool

`tools/adversarial-review/` is a stdlib-only Python package (no runtime dependencies, no workspace-only dependency groups — the package ships as a plugin and must resolve standalone), with three subcommands.

**`detect`** reports, for each backend, whether its CLI is on `PATH` and whether a cheap probe succeeds (`--version`, no model call), and which backend is the running harness.
The running harness is identified from the environment variables each harness sets for its child processes (for example `CLAUDECODE=1` for Claude Code) and marked `self`. The exact variable per harness is recorded in its backend adapter and pinned by the detection tests; when no harness is recognised, nothing is excluded and `detect` says so.

**`run --reviewers <list> --target <branch|diff|pr N> [--base <ref>]`** builds the input, runs every requested reviewer in parallel, and prints one merged JSON document of findings.

**`commands --harness <name>`** prints the per-harness command file content, for `setup` to write.

### Backends

One small adapter per CLI holds its headless, read-only command line:

| Backend | Invocation |
|---|---|
| `codex` | `codex exec -s read-only --ephemeral --output-schema <schema>` |
| `copilot` | `copilot -p <prompt>` with write and shell tools denied (`--deny-tool`) |
| `gemini` | `gemini -p <prompt> --approval-mode plan -o json` |
| `claude` | `claude -p <prompt>` with write tools disallowed (`--disallowedTools`), `--output-format json` |

Adding a model is adding one adapter. The exact flags are pinned by tests (see [Testing](#testing)).

### The prompt and the findings

One shared prompt, written once: *assume this change is wrong; find where it fails under real conditions — authentication and authorization, data loss, races, security regressions, broken assumptions, missing error handling.*
Reviewers may read the files the diff touches (read-only tools) but change nothing.

Every reviewer returns findings against one JSON schema — `severity`, `file`, `line`, `claim`, `evidence`, `reviewer`. `codex` enforces the schema natively; for the others the tool parses the output and records malformed output as a reviewer error rather than dropping it silently.
Findings from several reviewers are de-duplicated (same file, overlapping line, same claim class) while keeping every reviewer's name, then sorted by severity.

## Data flow before a PR is created

1. **Build the input from public-bound content only.** `git diff <base>...HEAD` (or the PR diff), the changed-file list, and the PR title and body exactly as the skill will post them. For security fixes that is the already-scrubbed title and body. The shared block accepts only these inputs; it has no parameter for tracker or mail content, so no skill can pass private context by accident.
2. **Run.** Every configured reviewer except `self`, in parallel, each with a timeout (default 8 minutes, under a harness's 10-minute shell-call cap).
3. **Merge and show.** The merged findings are presented next to the diff. The human chooses what to fix; the skill then continues to its normal push and PR-creation step.

Errors:

- A CLI that is missing, not logged in, or times out is reported as unavailable with its reason; the remaining reviewers continue.
- When every reviewer is unavailable, the skill says so plainly and continues the PR flow.
- Reviewer output is external content. A finding that contains instructions (injected from the reviewed diff or from the model) is shown as data and never acted on without the human.

## Configuration

`adversarial-review.md`, resolved through the usual lookup chain — `.apache-magpie-local/` (personal) first, then `.apache-magpie-overrides/` (project):

```yaml
adversarial_review:
  mode: on-pr-create        # on-pr-create | on-demand | off
  reviewers: [codex, copilot]
  timeout_minutes: 8        # below a harness's 10-minute shell-call cap
  models:                   # optional per-backend overrides
    copilot: gpt-5
```

- `setup config` runs `detect`, proposes the available non-`self` backends, and writes the user's choice to `.apache-magpie-local/adversarial-review.md`.
- `setup adopt` may commit a project default to `.apache-magpie-overrides/adversarial-review.md`; a personal file overrides it.
- `setup verify` reports configured reviewers whose CLI has since disappeared.
- The security family runs the reviewers at PR creation whenever at least one is configured, regardless of `mode`.

## Per-harness commands

`setup` writes a thin command for each harness it finds, each one invoking `adversarial-review run --target <argument>`:

| Harness | Command |
|---|---|
| Claude Code | `/magpie-adversarial-review:adversarial-review`, shipped in the plugin (Claude Code namespaces plugin commands by plugin name) |
| Codex CLI | `~/.codex/prompts/magpie-adversarial-review.md` |
| Gemini CLI | `~/.gemini/commands/magpie-adversarial-review.toml` |
| Copilot CLI | a reusable-prompt entry if the installed Copilot CLI supports one; otherwise `setup` prints the one-line `adversarial-review run` invocation to use instead |

Where a harness has no user-defined command mechanism, the fallback is always the same single-line tool invocation, which works from any harness's shell.

Each command runs every configured reviewer except the harness's own model — from Codex that is Claude (through `claude -p`), Copilot and Gemini; from Claude Code it is Codex, Copilot and Gemini.

## Sandbox

Reviewer CLIs need network access and read their own credentials (`~/.codex`, `~/.copilot`, `~/.gemini`, `~/.claude`), which the reference sandbox denies.
The tool therefore gets one `excludedCommands` entry for the installed plugin path, the same pattern `vetted-op-read` uses, and is invoked in exactly that single-line form (`uvx --from <plugin>/tools/adversarial-review adversarial-review …`).
Outside the sandbox the tool only runs the reviewer CLIs in their own read-only modes and writes nothing to the repository.

## Consumers

- **The shared pre-PR block**, included by every PR-creating skill and enforced by the skill validator the way the pre-flight block is: `security-issue-fix` (before the public fix PR), patch verification, `setup-upstream-fix`, `setup-override-upstream`, and any other skill that runs `gh pr create`.
- **`pr-management-code-review`**: `with-reviewers:<list>` (several reviewers) replaces the single-command `with-reviewer:`, which stays accepted for compatibility. The target is someone else's public PR.
- **Ad-hoc**, through the per-harness commands.

## Testing

`tools/adversarial-review/tests/` (pytest, stdlib, no real model calls):

- **Detection** — stub binaries on a fake `PATH`; each backend reported correctly; `self` excluded for each harness; missing and logged-out CLIs marked unavailable.
- **Command lines** — a snapshot per backend of the exact headless invocation, so a regression that drops a read-only flag fails.
- **Input builder** — given a tracker-shaped context, only the diff, the file list and the public PR text reach the prompt: no CVE IDs, tracker URLs or reporter fields. This test is what makes the absence of a privacy gate safe.
- **Output parsing** — valid JSON, malformed output, injected instructions inside a finding (kept as data), cross-reviewer de-duplication.
- **Concurrency and timeouts** — one slow stub does not block the others; timeouts are reported per reviewer.

Skill side: an eval fixture for the shared pre-PR block (security `issue-fix` and `setup-upstream-fix` run it before the push; the security family runs it under `mode: off`), and a validator check that every PR-creating skill includes the block.

## Rollout

Separate PRs, each reviewable and mergeable on its own:

1. `tools/adversarial-review` and the `magpie-adversarial-review` substrate plugin.
2. `setup`: `detect` in `config` and `verify`, the configuration template, per-harness command generation, the sandbox exclusion.
3. The shared pre-PR block and its inclusion in every PR-creating skill.
4. `pr-management-code-review`: `with-reviewers:`.

## Alternatives considered

- **Per-harness command files only**, each embedding the prompt and the CLI call. Rejected: four copies of the prompt and parsing drift apart, and the agent-run path has nothing to call.
- **An MCP server exposing each reviewer as a tool.** Harness-native permissions, but reviews run for minutes against MCP call timeouts, and it is another long-running server to install and sandbox. A later MCP front end over the same tool remains possible.
- **Gating private targets on the privacy-llm approved-model list.** Rejected once the input was limited to public-bound content: the gate would only have blocked content that is published minutes later anyway, while keeping every non-default model from reviewing security fixes.
- **User-fired slash commands only** (today's model). Kept for ad-hoc use, but not as the default: a review that has to be remembered and typed does not happen on every PR.

## Risks

- **The input builder is the privacy boundary.** If a future change lets tracker or mail content into the prompt, private data reaches third-party models. Mitigated by the shared block accepting only diff and public PR text, and by the input-builder test.
- **Reviewers can read beyond the prompt.** The input builder bounds the prompt, not a reviewer's read-only file tools. `codex -s read-only` does not confine reads, so an instruction injected into the diff could make it read a private file elsewhere on the machine. `copilot` and `gemini` keep their MCP servers (no switch exists to drop them). Mitigated by switching MCP off where the CLI allows it, by the tracker-checkout warning, and by the README telling operators to keep private checkouts away from review machines or leave `codex` out; not eliminated.
- **CLI flag drift.** Vendors change headless flags. Mitigated by per-backend snapshot tests and by `detect` probing versions; a broken backend degrades to *unavailable*, never to a writable mode.
- **Cost and latency.** Two or three reviewers per PR add minutes and model spend. Mitigated by parallel runs, the timeout, and `mode`.
- **Reviewer noise.** Adversarial prompts over-report. Findings are advisory and never block; the human filters.
