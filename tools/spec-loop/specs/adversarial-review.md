<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

---
title: Adversarial review by other models
status: experimental
kind: feature
mode: infra
source: >
  docs/designs/2026-09-23-adversarial-review.md (rollout PR 1 of 4).
  Implemented in tools/adversarial-review/ and published as the
  magpie-adversarial-review substrate plugin (plugins/magpie-adversarial-review/,
  SUBSTRATE_PLUGINS in tools/dev/check-family-plugins.py).
acceptance:
  - The tool runs only installed reviewer CLIs (codex, copilot, gemini,
    claude), each in its own read-only headless mode, and skips the model
    running the harness unless told otherwise.
  - A reviewer's input is limited by construction to the diff, the changed
    files, and the PR title and body as they will be posted; no option
    accepts any other context.
  - The report is advisory — one merged JSON document, exit 0 whenever the
    run completes — and an unavailable reviewer never fails the run.
  - Reviewer output is data; a finding that reads like an instruction is
    never acted on.
---

# Adversarial review by other models

## What it does

Gives a change a second read from models other than the one that wrote it.
The tool detects which reviewer CLIs are installed, runs the configured ones
read-only and in parallel over a branch, a diff or a PR, and merges what they
find into one advisory report.
A reviewer is only useful as a *different* model, so the harness's own model
is skipped by default.

This spec covers what has shipped: the tool and its plugin.
Wiring it into the skills — setup, a shared pre-PR block in every PR-creating
skill, and a multi-reviewer second read in `pr-management-code-review` — is the
remaining rollout, recorded under *Known gaps*.

## Where it lives

- `tools/adversarial-review/` — stdlib-only Python package, capability
  `substrate:review`, harness `agnostic`. Two subcommands:
  - `detect` — for each backend, whether its CLI is on `PATH` and answers a
    cheap probe, and which backend is the running harness (`self`),
    recognised from the environment variables each harness sets.
  - `run` — builds the input from `--target branch` (with `--base`),
    `pr:<N>` (with `--repo`, through `gh`) or `diff:<path>`, plus `--title`
    and `--body-file`, runs every requested reviewer, and prints the merged
    report.
- `plugins/magpie-adversarial-review/` — the substrate plugin in the Claude
  Code catalogue, linking `tools/adversarial-review` so the tool runs from the
  installed plugin tree
  ([marketplace distribution](marketplace-distribution.md)).
- `adversarial-review.md` — optional configuration, resolved
  `.apache-magpie-local/` first, then `.apache-magpie-overrides/`, under
  `--project-root`: `mode`, `reviewers`, `timeout_minutes`, per-backend
  `models`. `--reviewers` on the command line overrides the list.
- `docs/designs/2026-09-23-adversarial-review.md` and its implementation plan.

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

## Validation

```bash
uv run --all-packages --group dev pytest tools/adversarial-review/tests
python3 tools/dev/check-family-plugins.py
```

## Known gaps

- **No consumer is wired yet.** The design's rollout PRs 2–4 are unbuilt:
  `setup` running `detect` in `config` and `verify`, writing the
  configuration and the per-harness commands, and installing the sandbox
  exclusion; the shared pre-PR block in every PR-creating skill; and
  `with-reviewers:` in `pr-management-code-review`, which today still takes a
  single user-fired `with-reviewer:` slash command. The tool README's
  statements that skills run it and that setup installs its exclusion
  describe that target state.
- **No `commands` subcommand.** The design's `commands --harness <name>`,
  which would print the per-harness command files for `setup`, does not
  exist; only `detect` and `run` ship.
- **The `mode` key is parsed but unused** until the pre-PR block consumes it.
- **Reviewers can read beyond the prompt.** `codex -s read-only` restricts
  writes and network, not reads, so an instruction injected into the diff
  could have it read a file elsewhere on the machine; `copilot` and `gemini`
  keep any MCP servers they are configured with. The README tells operators
  to keep private checkouts away from review machines or leave `codex` out.
- **The sandbox blocks it.** Reviewer CLIs need network access and their own
  credentials, which the reference sandbox denies, and no `excludedCommands`
  entry ships for the tool yet.
