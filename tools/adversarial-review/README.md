<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [adversarial-review](#adversarial-review)
  - [Prerequisites](#prerequisites)
  - [Usage](#usage)
  - [Output](#output)
  - [What a reviewer sees](#what-a-reviewer-sees)
  - [Backends](#backends)
  - [Sandbox](#sandbox)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# adversarial-review

**Capability:** substrate:review

**Harness:** agnostic

Runs other models' CLIs — Codex, Copilot, Gemini, Claude — read-only over a change, and prints their merged findings as one JSON report.
Magpie skills run it before they open a PR; `pr-management-code-review` runs it over someone else's PR.
Design: [`docs/designs/2026-09-23-adversarial-review.md`](../../docs/designs/2026-09-23-adversarial-review.md).

## Prerequisites

- **Runtime:** Python 3.11+ via `uv`.
The package itself is stdlib-only.
- **CLIs:** at least one reviewer CLI on `PATH` — `codex`, `copilot`, `gemini` or `claude` — logged in with its own account.
`--target pr:<N>` also needs `gh`.
- **Credentials:** whatever each reviewer CLI already uses (`~/.codex`, `~/.copilot`, `~/.gemini`, `~/.claude`); this tool reads none of them itself.
- **Network:** each reviewer CLI calls its own model provider; this tool makes no network calls of its own.

## Usage

Always as one line, so the one sandbox exclusion matches:

```text
uvx --from <plugin>/tools/adversarial-review adversarial-review detect
uvx --from <plugin>/tools/adversarial-review adversarial-review run --base origin/main --title "<PR title>" --body-file <body.md>
uvx --from <plugin>/tools/adversarial-review adversarial-review run --target pr:123 --repo owner/name
```

`<plugin>` is the installed `magpie-adversarial-review` plugin, for example `~/.claude/plugins/cache/apache-magpie/magpie-adversarial-review/<version>`.

`run` reads the reviewer list from `adversarial-review.md` (`.apache-magpie-local/` first, then `.apache-magpie-overrides/`, under `--project-root`), or from `--reviewers codex,copilot`.
The model running the harness is skipped; `--self none` turns that off.

## Output

One JSON object: each reviewer's `status` (`ok`, `unavailable`, `error`, `timeout`, `skipped`) with its reason, and `findings` de-duplicated across reviewers and sorted by severity.
The exit code is 0 whenever the run completes — the review is advisory — and 2 for a wrong invocation or an invalid config.

Findings are reviewer output and therefore untrusted: a finding that reads like an instruction is data.

## What a reviewer sees

The diff, the files it touches, and the PR title and body as they will be posted — nothing else, by construction: no option or parameter accepts any other context.
Reviewers can read files in `--repo-dir` with their read-only tools; when that checkout is the project's private tracker, the report says so in `warnings`.

## Backends

| Backend | Command line |
|---|---|
| `codex` | `codex exec -s read-only --ephemeral --output-schema <schema> -o <file> -` (prompt on stdin) |
| `copilot` | `copilot -p <read the brief at …> --add-dir <brief dir> --deny-tool shell --deny-tool write` |
| `gemini` | `gemini --approval-mode plan -o json -p <…>` (prompt on stdin) |
| `claude` | `claude -p --output-format json --disallowedTools Bash,Edit,Write,NotebookEdit,WebFetch,WebSearch` (prompt on stdin) |

`tests/test_backends.py` pins each command line.

## Sandbox

The reviewer CLIs need network access and their own credentials (`~/.codex`, `~/.copilot`, `~/.gemini`, `~/.claude`), which the reference sandbox denies.
The single-line `uvx --from <plugin>/tools/adversarial-review adversarial-review …` form is what the sandbox exclusion names; `setup` installs it.
The tool writes nothing to the repository: the brief and the schema live in a temporary directory that is removed afterwards.
