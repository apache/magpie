<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [vetted-ops](#vetted-ops)
  - [Prerequisites](#prerequisites)
  - [Why](#why)
  - [What it actually guarantees](#what-it-actually-guarantees)
    - [What it does *not* guarantee](#what-it-does-not-guarantee)
  - [Configuration](#configuration)
  - [CLI](#cli)
  - [Wiring it into settings](#wiring-it-into-settings)
  - [Tests](#tests)
  - [Referenced by](#referenced-by)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# vetted-ops

**Capability:** substrate:sandbox

**Harness:** agnostic

A dispatcher for **fixed, policy-scoped forge operations**, so an agent session
needs *one* allowlist entry instead of a dozen wildcard `ask` rules.

## Prerequisites

- **Runtime:** Python 3.11+ via `uv`. The package itself is stdlib-only.
- **CLIs:** the `gh` CLI on `PATH`, authenticated for the repositories the policy
  names. Every operation shells out to it; the dispatcher runs nothing else.
- **Credentials:** whatever `gh` already uses (`~/.config/gh/`). This tool reads
  no credential of its own and stores none.
- **Network:** only what `gh` needs — `github.com` / `api.github.com`.
- **Configuration:** a policy TOML (see *Configuration*). Without one, every
  operation refuses.

## Why

[RFC-AI-0002 Layer 3](../../docs/rfcs/RFC-AI-0002.md) forces confirmation on every
outward-visible action:

```json
"ask": [ "Bash(gh issue edit *)", "Bash(gh issue comment *)",
         "Bash(gh issue close *)", "Bash(gh api * -X *)", … ]
```

The wildcard is doing the work, and it is also the cost. `gh issue edit *` covers
an unbounded argument surface — `--add-label`, `--body`, `--repo <somewhere
else>` — so a human has to read every invocation to know what it does. On a
sweep that touches thirty trackers, that is a hundred prompts, and the hundredth
gets the same attention as the first. Prompt fatigue is itself a security
problem.

This tool removes the wildcard rather than the confirmation. Each operation is a
**closed shape**: a name, typed parameters, and a builder that returns an argv
list. The repository comes from policy, not the command line. Labels, milestones,
assignees, board columns and close reasons must be values the policy declares.
Because the effect set is bounded by construction, the dispatcher can be
`allow`ed once instead of `ask`ed every time.

## What it actually guarantees

Being precise, because a security tool that overstates itself is worse than none:

- **A parameter can never become a command.** Builders return `list[str]`, executed
  with `subprocess.run(..., shell=False)`. There is no string interpolation
  anywhere in the path, so `1; rm -rf /` is simply an invalid issue number.
- **A parameter can never become a flag.** Any parameter starting with `-` is
  refused before validation, which closes flag-injection into `gh`.
- **The repo is not addressable.** No operation takes a repository parameter; it
  is read from policy. An operation cannot be pointed at another repository, and
  parameters that reach an API *path* — repo paths and git refs — refuse `..`,
  so none of them can walk out of the pinned repository either.
- **Body content is free; body *location* is not.** Comment bodies are passed by
  file reference, so the text may contain anything — backticks, `$(…)`,
  newlines. What is constrained is which file may be read: it must resolve inside
  the configured workspace, so an operation cannot be talked into publishing
  `~/.ssh/id_rsa`.
- **GraphQL is named, not written.** `gh api graphql` normally takes a query as a
  string — the widest surface `gh` offers. Here a caller names one of the
  documents shipped in [`queries/`](src/vetted_ops/queries), the dispatcher
  supplies the text, and `owner`/`name` come from policy. A caller can choose
  among the allowlisted queries; it cannot write one, and cannot re-aim one at
  another repository.
- **The catalogue is closed.** Widening the surface means editing
  [`ops.py`](src/vetted_ops/ops.py) — a reviewed code change, not a runtime
  decision.

### What it does *not* guarantee

**Per-caller scoping is least-privilege, not a security boundary.** The policy
declares which operations each caller may run, and `--caller` is required. But
within one agent session the agent is a single principal that chooses what to
pass as `--caller`. This protects against *the wrong skill reaching for the wrong
operation* — a real and common failure, especially under prompt injection, where
a hostile issue body talks a read-only triage pass into closing something. It
does **not** stop a determined agent.

A genuine boundary needs the runtime to bind scope to permissions. Today no
portable mechanism exists: plugin manifests cannot declare permissions, and
`permissionMode` is unsupported for plugin-shipped agents. The closest available
primitive is a subagent with a restricted `tools` list, which is **Claude
Code-specific** — the only other shipping runtime adapter is Codex
(`experimental`). See
[`tools/spec-loop/specs/vetted-command-surface.md`](../spec-loop/specs/vetted-command-surface.md)
for that trajectory.

**This is not a substitute for the sandbox.** It reduces prompt volume at Layer 3.
Layers 0–2 are unchanged and still carry the load.

## Configuration

Adopter-owned, at
`.apache-magpie-overrides/tools/vetted-ops/config.toml` by default:

```toml
# Body files must resolve inside this directory.
workspace = "/tmp/agent-scratch"

[repos]
tracker  = "acme/tracker"
upstream = "acme/product"

[values]
labels        = ["needs triage", "cve allocated", "pr merged"]
upstream_labels = ["ready for maintainer review", "area:scheduler"]  # issues *and* PRs
milestones    = ["1.2.3", "1.3.0"]
assignees     = ["alice", "bob"]
issue_states  = ["open", "closed", "all"]
pr_states     = ["open", "closed", "merged", "all"]
close_reasons = ["completed", "not planned"]

board_project_id      = "PVT_kwDO…"   # ProjectV2 node id
board_status_field_id = "PVTSSF_…"    # its Status field id

[values.board_columns]           # column name -> single-select option id
"Assessed"      = "aee65beb"
"CVE allocated" = "aae2beb3"

[callers]                        # caller -> operations it may run
"security-issue-sync"   = ["issue-view", "issue-comments", "issue-add-label",
                           "issue-set-milestone", "issue-comment", "comment-update"]
"security-issue-triage" = ["issue-view", "issue-comments"]
"pr-management-triage"  = ["pr-list", "pr-view", "pr-checks", "gql-pr-liveness",
                           "pr-add-label", "pr-remove-label", "pr-draft", "pr-ready",
                           "pr-comment", "pr-update-branch", "run-rerun-failed",
                           "workflow-approve"]
"pr-management-code-review" = ["pr-view", "pr-diff", "pr-comments", "pr-reviews",
                               "gql-pr-review-threads", "pr-review-approve",
                               "pr-review-request-changes", "pr-review-comment"]
"pr-management-stats"   = ["pr-list", "pr-view", "gql-pr-review-threads"]
"issue-triage"          = ["repo-issue-view", "repo-issue-comments", "repo-issue-list",
                           "repo-issue-add-label", "repo-issue-remove-label",
                           "repo-issue-comment"]
"issue-stale-sweep"     = ["repo-issue-list", "repo-issue-view", "repo-issue-comment",
                           "repo-issue-close", "repo-issue-reopen"]
"issue-backlog-stats"   = ["repo-issue-list"]
"license-compliance-audit" = ["repo-view", "repo-tree", "repo-file"]
"flaky-test-triage"     = ["run-list", "run-view", "pr-view"]
"release-verify-rc"     = ["release-list", "release-view", "tags", "repo-file"]
"contributor-nomination" = ["user-profile", "pr-list", "repo-issue-list"]
"mentoring-welcome"     = ["repo-issue-view", "repo-issue-comment", "pr-view"]
```

`mentoring-welcome` needs no operation of its own: it works on upstream issues
and PRs, which the issue and PR families already cover. A family earns new
operations only when it has a shape the catalogue lacks.

Grant the narrowest set that lets a skill finish its job: `pr-management-stats`
is a read-only dashboard, so it gets no write operation at all, and a
prompt-injection payload in a PR title cannot talk it into one.

The policy is never supplied on the command line: a caller cannot widen its own
policy.

## CLI

```bash
vetted-op list-ops                          # the catalogue
vetted-op policy                            # resolved policy, as JSON
vetted-op --caller <name> <operation> [param …]
vetted-op --caller <name> <operation> [param …] --dry-run   # print argv, run nothing
```

Exit codes: `0` ok, `2` usage, `3` refused by policy or validation, `4` the
underlying command failed.

## Wiring it into settings

Replace the wildcard `ask` rules with one `allow` entry, and keep an `ask` on
anything still invoked directly:

```json
"permissions": {
  "allow": [ "Bash(uv run --project <plugin>/tools/vetted-ops vetted-op *)" ]
}
```

The dispatcher must live where the agent cannot rewrite it — otherwise an agent
that edits `ops.py` has defeated the whole design. Shipping it inside the
installed plugin tree satisfies this: the plugin install is not a path the agent
edits. If you vendor it into a repo the agent *does* edit, add a
`permissions.deny` on `Write`/`Edit` for that path, and understand that the
guarantee is then only as strong as that rule.

## Tests

```bash
uv run --project . python -m pytest
```

The suite asserts the properties above rather than the plumbing: hostile
parameters are refused, every builder produces a `gh` argv, the repo cannot be
influenced by a parameter, body files outside the workspace are rejected while
hostile body *content* passes through untouched, and a caller cannot run an
operation outside its manifest.

## Referenced by

- [RFC-AI-0002](../../docs/rfcs/RFC-AI-0002.md) — the layered agent-isolation posture.
- [`tools/spec-loop/specs/vetted-command-surface.md`](../spec-loop/specs/vetted-command-surface.md)
