<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Spec-driven development](#spec-driven-development)
  - [The idea](#the-idea)
  - [Three phases, four beats, one loop](#three-phases-four-beats-one-loop)
  - [Specs are not RFCs](#specs-are-not-rfcs)
  - [A branch per fix or feature](#a-branch-per-fix-or-feature)
  - [Why it never pushes](#why-it-never-pushes)
  - [Security and unattended agent loops](#security-and-unattended-agent-loops)
  - [Keeping specs honest: the update beat](#keeping-specs-honest-the-update-beat)
  - [Layout](#layout)
  - [Quick start](#quick-start)
  - [How this composes with the framework's principles](#how-this-composes-with-the-frameworks-principles)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Spec-driven development

This document explains the **spec-driven build loop** that lives in
[`tools/spec-loop/`](../tools/spec-loop/). It is how this framework can be
developed and maintained against a written description of what it does,
rather than against whatever happens to be in someone's head on a given
afternoon.

## The idea

The loop is a small instance of the general
[Ralph](https://ghuntley.com/ralph/) technique: run a fresh agent context
against a fixed prompt, let it do one well-scoped thing, then run it
again with a clean context. The power is in the funnel that feeds it —
not "a loop that codes," but a pipeline from *what the product should do*
to *one reviewable change at a time*.

Two artefacts carry the state between iterations, so nothing depends on a
long-lived context window:

- **Specs** ([`tools/spec-loop/specs/`](../tools/spec-loop/specs/)) — a
  faithful, plain-Markdown description of each functional area of the
  product: what it does, where it lives in the code, the contract it must
  honour, and its known gaps. The specs are the *desired state*.
- **The implementation plan**
  ([`tools/spec-loop/IMPLEMENTATION_PLAN.md`](../tools/spec-loop/IMPLEMENTATION_PLAN.md))
  — the prioritised list of *work items*: the gaps between the specs and
  the code. Each work item is sized to one branch and one PR.

## Three phases, four beats, one loop

Phase one is a human (or a planning conversation) writing the specs.
Phases two and three are the loop, swapping prompts:

| Beat | Command | What it does | Commits? |
|---|---|---|---|
| **plan** | `loop.sh plan` | Compares specs against the code; rewrites the plan as prioritised work items. | No |
| **build** | `loop.sh` | Implements the single highest-priority work item on its own branch; validates; commits there. | Yes, on a work-item branch |
| **update** | `loop.sh update` | Inverse of plan: finds functionality the code has but the specs don't, and brings the specs back in sync. | Yes, on `sync-specs-<timestamp>` |
| **consolidate** | `loop.sh consolidate` | Shrinks the plan when it grows too long, without dropping planned work. | Yes, the plan only |

Every beat loads the same operational context —
[`tools/spec-loop/AGENTS.md`](../tools/spec-loop/AGENTS.md) (repo map,
validation commands, branch and hard-limit rules) layered on top of the
repository-wide [`AGENTS.md`](../AGENTS.md). Each build iteration reads
only the spec and source files relevant to its one work item, so a fresh
context never drowns in the whole tree.

## Specs are not RFCs

The framework already has [`docs/rfcs/`](rfcs/) — normative principle
documents that say *why* and define the trust posture. Those are the
**constitution**. The specs are the **work orders**: discrete, concrete,
grounded in the actual code. The loop **respects** an RFC principle as a
constraint (it never pushes, it stays in the sandbox), but it never reads,
edits, or restates an RFC, and no spec ever lives under `docs/rfcs/`. The
two formats and lifecycles are deliberately separate; see
[`tools/spec-loop/specs/README.md`](../tools/spec-loop/specs/README.md).

Spec filenames are **topics, not numbers** — `triage-mode.md`,
`pairing-mode.md`, `security-issue-lifecycle.md`. There is no numeric
prefix, because numbering implies a priority the specs don't carry.
Priority lives only in the implementation plan.

## A branch per fix or feature

The defining constraint of this loop: **one work item, one branch, one
PR**. Before plan/build iterations, the runner snapshots open PRs so the
plan beat does not add work already in flight and the build beat skips
planned items that an open PR already covers. The build beat returns to
the integration base, then carves out a
bare `<slug>` branch for the single work item it is about to implement. It
never commits feature work to the base branch, and `loop.sh` stops if it
detects that happening. The result of a run is a fan of independent
branches, each carrying exactly one change — each independently
reviewable and independently revertible.

This is the same discipline the framework asks of every state change,
applied to the framework's own development. It is also what makes the
loop safe to run unattended: the blast radius of any one iteration is a
single local branch.

## Why it never pushes

`git push` and `gh pr create` are in the `ask` list of
[`.claude/settings.json`](../.claude/settings.json) — they require a human
confirmation. The loop honours that: it ends every iteration at a **local
commit** and prints the exact commands for the human to run:

```bash
git push -u origin <slug>
gh pr create --web --base main --head <slug> \
  --title "<subject>" --body-file <prepared-body>
```

Opening the PR with `--web` is the framework's convention so the reviewer
sees the title, body, and generative-AI disclosure in the browser before
submitting. The agent drafts; the human presses the button.

## Security and unattended agent loops

The loop runs the agent headless with `--dangerously-skip-permissions`.
That deserves a direct explanation, because it looks, at a glance, like
it throws away the framework's permission gates.

**Why the flag is there.** Headless iterations have no human to answer a
per-tool-call prompt. Without the flag, the agent would stall (or, in
non-interactive mode, deny) the moment it tried to edit a file or run a
validation command. The flag lets the loop do its job — edit, validate,
commit — unattended.

**What it bypasses, and what it does not.** The framework's sandbox is
layered (see [`docs/rfcs/RFC-AI-0004.md`](rfcs/RFC-AI-0004.md) for the
normative statement and `docs/setup/secure-agent-internals.md` for the
mechanism). The harness-specific unattended flag
(`--dangerously-skip-permissions`, `--dangerously-bypass-approvals-and-sandbox`,
`--force`, `--yolo`, etc.) only reaches the top two:

| Layer | Mechanism | Bypassed by the flag? |
|---|---|---|
| 0. Clean environment | wrapper strips credential-shaped env vars before exec | **No** — it is the launching wrapper, not the agent |
| 1. Filesystem + network sandbox | `bubblewrap` + SNI proxy (Linux) / `sandbox-exec` (macOS); default-deny egress | **No** — enforced by the OS, not the agent |
| 2. Tool permissions | `.claude/settings.json` `permissions.deny` | **Yes** |
| 3. Forced confirmation | `.claude/settings.json` `permissions.ask` on `git push`, `gh …` | **Yes** |

So the unattended mode removes the *agent-level* gate (Layers 2–3), but the
*OS-level* boundary (Layers 0–1) is untouched — it is enforced beneath
the agent and cannot be turned off from inside it. This is exactly the
posture these flags' own guidance assumes: use them only inside an
external sandbox.

**How the loop stays safe anyway.** Three things, in order of
importance:

1. **Run it only inside the sandbox harness.** The OS layers the flag
   cannot bypass are the real boundary. Never run the loop on a bare
   machine — launch it through the project's `claude-iso`/sandbox wrapper
   so the filesystem and network allow-lists are in force.
2. **Run it with no push/write credentials in the environment.** The
   clean-env wrapper already strips them; keep it that way. `github.com`
   is on the network allow-list, but a `git push` or `gh pr create` with
   no token cannot authenticate, so it fails closed. As Claude-specific
   defence in depth, the loop also passes
   `--disallowedTools "Bash(git push *)" "Bash(gh *)"` when using the
   Claude harness.
3. **Structural containment.** Every iteration works on its own
   bare `<slug>` branch, the loop guards against commits landing on the
   base branch, and the prompts forbid push/PR. The human-in-the-loop
   gate is not removed — it is *relocated* from per-tool-call to the
   push / PR / merge boundary, where the human reviews a finished branch.

**Net effect.** During a run the per-call confirmation gate is traded for
autonomy, but credentials are absent, egress is fenced, and the blast
radius of any iteration is a single local branch the human has not yet
pushed. That is the same reason the loop is the project's *manual-loop
evidence* and must never be promoted to auto-merge: the autonomy is
bounded to producing local branches, nothing more. An operator who wants
the per-call gate back can drop the flag and pre-authorise the loop's
tools with `--allowedTools` instead — at the cost of the loop pausing on
anything it was not pre-authorised to do.

## Keeping specs honest: the update beat

Not every contribution comes through the loop — people land new skills and
tools the normal way. When that happens the specs fall behind the code.
The **update** beat is the fix: it inventories `.claude/skills/`,
`tools/`, and `docs/modes.md`, diffs that against the specs, and back-fills
or corrects the specs (a `proposed` area that now has a shipped skill
becomes `experimental`; a drifted *Where it lives* is corrected; genuinely
new functionality gets a new topic-named spec). It edits **only** the spec
directory — it documents reality, it doesn't change it — and lands as one
reviewable `sync-specs-<timestamp>` PR. The runner owns
`tools/spec-loop/.last-sync`: it passes incremental-scope guidance into
the prompt, then amends or creates the marker commit after the sync
finishes. Run it after a batch of normal PRs merges, or on a schedule.

## Layout

```text
tools/spec-loop/
├── README.md              operator quickstart
├── AGENTS.md              loop-scoped operational context
├── lib.sh                 deterministic runner helpers
├── loop.sh                the runner (plan / build / update / consolidate)
├── PROMPT_plan.md         gap analysis → plan
├── PROMPT_build.md        implement one work item on its own branch
├── PROMPT_update.md       back-fill specs from contributed code
├── PROMPT_consolidate.md  shrink the plan
├── IMPLEMENTATION_PLAN.md prioritised work items (the gaps)
├── specs/                 functional description of the product
│   ├── overview.md
│   ├── triage-mode.md     mentoring-mode.md   drafting-mode.md   pairing-mode.md
│   ├── security-issue-lifecycle.md            privacy-llm-gate.md
│   ├── agent-isolation-sandbox.md             cve-tooling.md
│   ├── adoption-and-setup.md                  adapters.md
│   ├── meta-and-quality-tooling.md            spec-loop-runner.md
│   └── security-reporting.md                  reviewer-routing.md
└── tests/                 deterministic runner fixture tests
```

## Quick start

```bash
# 1. See what's out of sync, then read the plan it writes.
./tools/spec-loop/loop.sh plan 1
$EDITOR tools/spec-loop/IMPLEMENTATION_PLAN.md

# 2. Build the top work item (one branch, one commit) and stop.
./tools/spec-loop/loop.sh 1

# 3. Review the branch it produced, then push + open the PR yourself.
git log --oneline -1
git push -u origin <slug>
gh pr create --web --base main --head <slug> --title "…" --body-file …

# Later: someone merged skills outside the loop — resync the specs.
./tools/spec-loop/loop.sh update 1
```

Stop any run with `Ctrl+C` or `touch STOP`. By default the loop forks
work items from the branch you start it on (typically `main`); set
`SPEC_LOOP_BASE` to build on top of a different branch. Set
`SPEC_LOOP_AGENT` to choose a supported headless agent CLI (`claude`,
`codex`, `cursor`, `gemini`, or `opencode`), and set
`SPEC_LOOP_HARNESS` when a wrapper's name does not imply its run
convention. Set `SPEC_LOOP_PR_LIMIT` to change how many open PRs are
included in the duplicate-work check.

## How this composes with the framework's principles

A loop that runs an agent unattended sounds, at first, like the opposite
of human-in-the-loop. The branch-per-feature constraint is the
reconciliation: the loop's autonomy is bounded to *producing local
branches*, and the human gate sits exactly where the framework always
puts it — at push, at PR, at merge. Nothing the loop does is visible
outside the maintainer's machine until a human chooses to push it. The
loop is the *manual* development cycle the framework can later point to as
evidence; it is not, and must not become, an auto-merge.
