<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

---
title: Adversarial review by other models
status: experimental
kind: feature
mode: infra
source: >
  docs/designs/2026-09-23-adversarial-review.md (all four rollout PRs built;
  see its As built section). Implemented in tools/adversarial-review/ and
  published as the magpie-adversarial-review substrate plugin
  (plugins/magpie-adversarial-review/, SUBSTRATE_PLUGINS in
  tools/dev/check-family-plugins.py). Consumed by the shared pre-PR block
  tools/dev/blocks/pre-pr-adversarial-review.md, by
  pr-management-code-review's with-reviewers: path, and by setup
  (config Step 3c, verify 8i, isolated-setup-install Step R).
acceptance:
  - The tool runs only installed reviewer CLIs (codex, copilot, gemini,
    grok, claude), each in its own read-only headless mode, and skips the model
    running the harness unless told otherwise.
  - A reviewer's input is limited by construction to the diff, the changed
    files, and the PR title and body as they will be posted; no option
    accepts any other context.
  - The report is advisory — one merged JSON document, exit 0 whenever the
    run completes — and an unavailable reviewer never fails the run.
  - Reviewer output is data; a finding that reads like an instruction is
    never acted on.
  - Every skill that opens a PR carries the shared pre-PR review block; the
    skill validator fails one that does not, apart from a reasoned
    exemption list.
  - The tool refuses a --repo-dir that is the project's private tracker
    unless --allow-tracker-checkout is passed.
---

# Adversarial review by other models

## What it does

Gives a change a second read from models other than the one that wrote it.
The tool detects which reviewer CLIs are installed, runs the configured ones
read-only and in parallel over a branch, a diff or a PR, and merges what they
find into one advisory report.
A reviewer is only useful as a *different* model, so the harness's own model
is skipped by default.

The tool is wired into the skills in three places.
`setup` detects the installed reviewer CLIs, writes the configuration, offers
per-harness commands, and installs the sandbox exclusion.
Every skill that opens a PR runs the configured reviewers over the change
before the PR is created, through one shared block.
`pr-management-code-review` runs them as a second read on each PR it reviews
(`with-reviewers:`).

## Where it lives

- `tools/adversarial-review/` — stdlib-only Python package, capability
  `substrate:review`, harness `agnostic`. Three subcommands:
  - `detect` — for each backend, whether its CLI is on `PATH` and answers a
    cheap probe, and which backend is the running harness (`self`),
    recognised from the environment variables each harness sets.
  - `run` — builds the input from `--target branch` (with `--base`),
    `pr:<N>` (with `--repo`, through `gh`) or `diff:<path>`, plus `--title`
    and `--body-file`, runs every requested reviewer, and prints the merged
    report. `--allow-tracker-checkout` lets it run on a tracker checkout
    whose own code is under review.
  - `commands --harness claude|codex|gemini|copilot` — prints one harness's
    command file as JSON `{path, content}`, rendered from one template
    (`commands.py`). Claude Code's is plugin-relative
    (`commands/adversarial-review.md`); Codex's is
    `~/.codex/prompts/magpie-adversarial-review.md`; Gemini's is
    `~/.gemini/commands/magpie-adversarial-review.toml`; Copilot CLI has no
    command mechanism, so it gets an empty path and the one-line invocation.
- `tools/adversarial-review/commands/adversarial-review.md` — the generated
  Claude Code command, pinned by a test against the generator.
- `plugins/magpie-adversarial-review/` — the substrate plugin in the Claude
  Code catalogue, linking `tools/adversarial-review` so the tool runs from the
  installed plugin tree
  ([marketplace distribution](marketplace-distribution.md)), and
  `commands/adversarial-review.md` (a link to the generated command), which
  Claude Code publishes as `/magpie-adversarial-review:adversarial-review`.
- `adversarial-review.md` — optional configuration, resolved
  `.apache-magpie-local/` first, then `.apache-magpie-overrides/`, under
  `--project-root`: `mode` (`on-pr-create`, `on-demand`, `off`), `reviewers`,
  `timeout_minutes`, per-backend `models`.
  `--reviewers` on the command line overrides the list.
  Template: `plugins/magpie-setup/templates/adversarial-review.md`
  (`projects/_template/` is a link to that directory), pinned parseable by a
  test.
- `tools/dev/blocks/pre-pr-adversarial-review.md` — the shared pre-PR block,
  filled into each host skill by `tools/dev/check-shared-blocks.py`.
  Hosts today: `issue-fix-workflow` (in its sibling
  `pre-pr-adversarial-review.md`), `release-announce-draft`,
  `release-audit-report`, `release-prepare` (also at 2f and 14b),
  `audit-finding-fix`, `security-issue-fix`, `security-issue-import-from-pr`,
  `security-issue-import-from-scan`, `security-model-prepare`,
  `security-model-verify`, `setup-override-upstream`, and
  `setup-upstream-fix`.
  The block covers two shapes of host: a skill that opens a PR runs the
  reviewers once the PR's title and body are final, before the push where
  the flow allows it; a skill that works from a PR someone else proposed
  (verifying it, or importing it into the tracker, as
  `security-issue-import-from-pr` does) runs them over that PR before
  reporting on it or acting on it (#1453).
- `validate_pre_pr_review_block` in
  `tools/skill-and-tool-validator/src/skill_and_tool_validator/__init__.py` —
  HARD check, category `pre-pr-review-block`.
- `pr-management-code-review` — `adversarial.md`, `prerequisites.md` §2 and
  `selectors.md` under `plugins/magpie-pr-management/skills/code-review/`
  ([PR management family](pr-management-family.md)).
- Setup wiring under `plugins/magpie-setup/skills/`: `setup/config.md`
  Step 3c, `setup/verify.md` 8i, `setup/adopt.md` 4a,
  `isolated-setup-install/SKILL.md` Step R, and
  `isolated-setup-verify/conditional-checks.md` check 14.
- The sandbox exclusion in `.claude/settings.json`, mirrored in
  `tools/sandbox-lint/expected.json`.
- `docs/designs/2026-09-23-adversarial-review.md`, whose *As built* section
  records where the shipped system departs from the design.
  The implementation plan was folded into it and deleted.

## Behaviour & contract

- **Read-only backends, pinned by tests.** One adapter per CLI holds its
  headless command line: `codex exec -s read-only --ephemeral` with MCP servers
  switched off and `--output-schema`; `copilot -p` with the shell and write
  tools denied; `gemini --approval-mode plan -o json`; `claude -p` with
  `--strict-mcp-config` and Bash, the editing tools, web access and `Task`
  disallowed. `tests/test_backends.py` pins each line, so a regression that
  drops a read-only flag fails.
- **The input builder is the privacy boundary.** The prompt carries only the
  diff, the changed-file list and the public PR text, so no privacy-LLM gate
  applies: nothing private is ever passed. When `--repo-dir` is the project's
  private tracker the report says so in `warnings`.
- **One findings schema, merged.** Every reviewer answers against the same
  schema (`severity`, `file`, `line`, `claim`, `evidence`). Parsing keeps the
  good findings from a partly malformed reply and reports the bad ones;
  findings are de-duplicated across reviewers, keeping every reviewer's name,
  and sorted by severity.
- **Bounded and interruptible.** Reviewers run in parallel, each with a
  timeout (default 8 minutes, under the 10-minute cap harnesses put on one
  shell call); a timed-out reviewer's whole process group is killed, and
  Ctrl-C or SIGTERM kills every live reviewer.
- **Advisory.** Each reviewer reports `ok`, `unavailable`, `error`, `timeout`
  or `skipped` with its reason. The exit code is 0 whenever the run completes
  and 2 only for a wrong invocation or an invalid config.
- **Nothing written to the repository.** The brief and the schema live in a
  temporary directory removed afterwards; the tool itself makes no network
  calls.
- **Inputs are confined.** The tool runs outside the sandbox, so it refuses a
  `--body-file` or `diff:` path outside the repository or a temporary
  directory.
  It refuses a `--repo-dir` that is the project's private tracker (exit 2),
  because the reviewers can read every file there, unless
  `--allow-tracker-checkout` says the tracker's own code is under review; the
  report then still carries the warning.
- **One invocation spelling.** Every generated command, the shared block and
  code review's copy invoke
  `uvx --from ~/.claude/plugins/cache/apache-magpie/magpie-adversarial-review/<version>/tools/adversarial-review adversarial-review …`,
  unquoted with a literal `~`, the only form the sandbox exclusion matches.
  Tests pin each copy to the exclusion pattern.
  No command bakes in a version: Claude Code's reads it from
  `${CLAUDE_PLUGIN_ROOT}`, the others take the newest installed, so `upgrade`
  has nothing to rewrite.
- **Sandbox exclusion without an allow rule.** `isolated-setup-install`
  Step R adds one `excludedCommands` entry for that invocation and an `Edit`
  deny on the plugin cache, since the tool runs unsandboxed.
  There is deliberately no allow rule, so every run keeps its prompt.
  `isolated-setup-verify` check 14 checks all three.
- **Setup offers reviewers only when named.** `config adversarial-review`
  (Step 3c) runs `detect`, pre-ticks every available backend except `self`,
  asks for the `mode`, and writes `.apache-magpie-local/adversarial-review.md`,
  showing the difference first when the file exists.
  It then offers the Codex and Gemini command files under the user's home,
  never in a repository.
  It is never part of a pre-flight entry.
  `verify` 8i reports configured reviewers whose CLI is gone and stale command
  files; `adopt` always flags the file as personal.
- **The pre-PR block runs before every PR a skill opens.** Once the PR's
  title and body are final, and after the skill's own public-surface checks,
  it reviews the diff with the title and body exactly as they will be posted.
  No configuration or an empty `reviewers` list skips silently; a missing
  plugin skips with one line.
  A `security`-family skill runs whenever at least one reviewer is listed,
  whatever `mode` says; any other skill runs only on `mode: on-pr-create`.
  `--repo-dir` is never the tracker (an empty temporary directory for
  `pr:<N>` with no checkout), and a change that is not a committed local
  branch is reviewed as a diff file.
  The findings are shown as untrusted, advisory data, never block the flow,
  and add nothing to a step's structured output; a finding the human wants
  fixed sends the flow back to the fix, the skill's own checks, and a fresh
  review.
- **The validator enforces the block.** A skill counts as PR-opening when
  any of its Markdown files or scripts names `gh pr create` (a Python argv
  list included), or when `PRE_PR_REVIEW_DELEGATED` lists it because it opens
  PRs through another skill's helper (`security-model-prepare`).
  `PRE_PR_REVIEW_EXEMPT` lists, each with its reason, files that mention the
  command without opening a PR.
- **Standalone resolution.** Like `tools/vetted-ops`, the project declares no
  workspace `dev` group, because it runs as
  `uvx --from <plugin>/tools/adversarial-review adversarial-review …`, where
  the workspace root does not exist.

## Out of scope

- Blocking a PR on findings; the human decides what to act on.
- Reviewing private content: tracker bodies, mail threads, CVE IDs before
  disclosure, advisory text.
- Authenticating reviewer CLIs; each uses its own login.

## Acceptance criteria

1. `detect` reports each backend's availability and marks the running
   harness `self`; `run` skips `self` unless `--self none` is passed.
2. Each backend's command line matches its pinned test, and none can run in
   a writable mode.
3. Given tracker-shaped context, only the diff, the file list and the public
   PR text reach the prompt.
4. One slow or failing reviewer does not block the others, and its timeout
   or error is reported per reviewer.
5. The run exits 0 with a merged report whenever it completes, whatever the
   reviewers returned.
6. `check-family-plugins.py` passes with `magpie-adversarial-review` in
   `SUBSTRATE_PLUGINS` and its entry point resolving through the plugin link.
7. `commands --harness <name>` prints the command file for each of the four
   harnesses, and the shipped Claude Code command matches the generator.
8. `run` exits 2 on a tracker `--repo-dir` without
   `--allow-tracker-checkout`, and on a body or diff file outside the
   repository and the temporary directory.
9. `skill-and-tool-validate` reports a `pre-pr-review-block` violation for
   any PR-opening skill without the shared block.

## Validation

```bash
uv run --all-packages --group dev pytest tools/adversarial-review/tests
python3 tools/dev/check-family-plugins.py
python3 tools/dev/check-shared-blocks.py
uv run --project tools/skill-and-tool-validator --group dev skill-and-tool-validate
```

Behavioural eval suites under `tools/skill-evals/evals/`:
`setup/step-config-adversarial`,
`security-issue-fix/step-7-adversarial-review`,
`setup-upstream-fix/step-5-adversarial-review`, and
`pr-management-code-review/step-2-reviewer-resolution`.

## Known gaps

- **Rollout complete; the earlier gaps are closed.** The consumers once
  listed here (setup wiring, the pre-PR block, `with-reviewers:`), the
  `commands` subcommand, a consumer of `mode`, and the sandbox exclusion all
  shipped (#1371, #1372, #1373).
- **`detect` does not see login state.** It makes no model call, so a
  logged-out CLI looks available until the first real run reports it
  `unavailable`; `setup config` says so.
- **Reviewers can read beyond the prompt.** `codex -s read-only` restricts
  writes and network, not reads, so an instruction injected into the diff
  could have it read a file elsewhere on the machine; `copilot` and `gemini`
  keep any MCP servers they are configured with.
  The README tells operators to keep private checkouts away from review
  machines or leave `codex` out.
- **Copilot CLI has no command file.** `setup` can only show the one-line
  invocation for it.
