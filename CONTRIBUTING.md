<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Contributing](#contributing)
  - [English as code](#english-as-code)
  - [What this framework is](#what-this-framework-is)
  - [Repository layout](#repository-layout)
    - [Directory tree](#directory-tree)
  - [Skill families](#skill-families)
    - [Skill anatomy](#skill-anatomy)
  - [Tool families](#tool-families)
  - [Cross-cutting concerns](#cross-cutting-concerns)
  - [Agent harnesses](#agent-harnesses)
  - [Code in this repo](#code-in-this-repo)
    - [Python (uv-managed)](#python-uv-managed)
    - [Groovy](#groovy)
    - [Shell scripts](#shell-scripts)
  - [Getting set up](#getting-set-up)
    - [Lightening the agent context](#lightening-the-agent-context)
  - [Making changes](#making-changes)
  - [Authoring with an agent](#authoring-with-an-agent)
  - [Running the dev loop](#running-the-dev-loop)
  - [Opening a pull request](#opening-a-pull-request)
  - [Your first contribution](#your-first-contribution)
  - [Confidentiality](#confidentiality)
  - [Authoritative references](#authoritative-references)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Contributing

Thanks for helping improve this repository. It is the **generic,
project-agnostic framework** for agent-assisted repository
maintainership across ASF projects (and equally for any non-ASF
open-source community that wants in). The framework is named
**Apache Magpie** — see [`MISSION.md`](MISSION.md) for the
project's motivation, scope, and design commitments.

Before sending a patch, please skim this file end-to-end: it lays
out the layering the repository depends on, the cross-cutting
concerns every change must respect, and the dev loop CI enforces.
A patch that ignores any of these is hard to land no matter how
correct it is in isolation.

## English as code

The most important thing to understand about this repository,
before you make any change, is that **English is the primary
programming language here**. Not as metaphor — as engineering.

Sixty-some years ago, COBOL was designed around an ambitious idea:
let programmers write business logic in something close to plain
English (`MULTIPLY HOURS-WORKED BY HOURLY-RATE GIVING GROSS-PAY`),
on the theory that the compiler should meet humans halfway. The
idea was sound; the implementation wasn't. Compilers of the 1960s
could parse the syntax but not the meaning, so COBOL ended up
verbose, brittle, and still requiring programmer discipline to
write code the compiler could actually run. The full-English
vision was abandoned, and for the next half-century, programming
languages drifted in the *opposite* direction — more terse, more
rigorous, more demanding of the human, on the assumption that the
human would always be the one meeting the machine halfway.

**We have come full circle.** Today's interpreters can read
English. A modern coding agent — Claude Code, Codex, Gemini CLI,
any of the runtimes listed in
[Agent harnesses](#agent-harnesses) — reads a plain-English
description of a workflow (*"sweep the inbox since last week,
classify each message against the six triage classes, draft a
confirmation reply for each one that needs one"*) and executes
it. The compiler is now sophisticated enough that the
English-as-code vision actually works. COBOL was right about
where things should go; it was sixty years early on the question
of what would interpret it.

This repository is built on that observation. The skill files
under `skills/<name>/SKILL.md` are **programs**. They are
written in English. They are executed by an agent. They have
inputs, outputs, control flow, error handling, edge cases, and
unit tests (the eval suite under [`tools/skill-evals/`](tools/skill-evals/)).
A `SKILL.md` is no less code than a `.py` file — it is code at a
**higher abstraction level**, interpreted by a more capable
interpreter.

Traditional programming languages (Python and Groovy in this
repo) still have their place. They handle the deterministic
pieces where bit-exact output matters more than judgement — CVE
JSON emission, OAuth dance, archive parsing, dashboard rendering.
Those live under [`tools/`](tools/) as ordinary code with
ordinary tests. But they are the *minority* of the surface area.
The bulk of what this project does — assess a security report,
classify a PR, mentor a contributor, allocate a CVE — is encoded
in English-language skill files. That is the project's bet, and
it is the bet you need to internalise before contributing.

Three practical consequences:

- **A change to a skill file is a code change.** Treat it like
  one. Run the eval suite. Think about boundary conditions. Add
  the equivalent of a regression test (an eval fixture) for the
  bug you fixed. The fact that the file ends in `.md` does not
  make it a doc — it makes it a program with a markdown syntax.
- **A change to a tool's `tool.md` is a code change.** Tool
  contracts in markdown are read by the skills at runtime;
  rewording the contract is rewording the API.
- **You author both layers agentically** — see
  [Authoring with an agent](#authoring-with-an-agent) below. The
  loop is the same whether the artefact is an English skill file
  or a Python bridge, because the meta-level operation (state
  intent, iterate, probe edges, test) is the same. Only the
  feedback signal differs — eval suite for the English layer,
  `pytest` / `mypy` / `ruff` for the traditional-language layer.

Read the rest of this guide with that frame in mind. When
something looks like "just documentation", check whether it
sits under `skills/` or `tools/<system>/tool.md`. If it
does, it's code — and the rules for changing code apply.

## What this framework is

Four streams of day-to-day work, all built on the same skill +
tool + sandbox + HITL substrate:

- **Security-issue handling** — inbound triage, deduplication,
  agent-drafted reporter replies under human review, CVE
  allocation, audit-logged tracking through publication.
- **Issue and PR triage and management** — including audit-tool
  findings ingested as actionable issues.
- **Conversational contributor mentoring** — meeting new
  contributors where they are; the agent absorbs the mechanical
  review so the human conversation stays on design.
- **Development-cycle skills for committers and contributors** —
  multi-agent dev workflows, self-review and pre-flight patterns,
  scoped agent-drafted patches under the developer's seat.

The framework is **project-agnostic by design**. Adopters configure
their identity, rosters, canned responses, release trains, and
security model in their own `<project-config>/` directory in their
adopter tracker repo, alongside a gitignored snapshot of this
framework managed by the
[`setup`](skills/setup/SKILL.md) skill.
None of that adopter-side content lives here.

The framework's normative commitments are codified in
[RFC-AI-0004](docs/rfcs/RFC-AI-0004.md) — six principles
(HITL, sandbox, vendor neutrality, conversational + correctable,
write-access discipline, privacy by design) that every change
must respect. If you only read one document before contributing,
read that one.

## Repository layout

The tree has four layers, each with a clearly-scoped job. A
skill running against an adopter project must be able to resolve
every piece of context it needs from some combination of the four
— no hard-coded project assumptions anywhere in this repo.

- **Root docs** carry the cross-cutting rules every contributor
  and agent is expected to have read.
  [`README.md`](README.md) is the framework overview and adoption
  entry point. [`AGENTS.md`](AGENTS.md) is the editorial contract:
  tone, brevity, confidentiality, linking conventions, the
  placeholder substitution rule (`<PROJECT>`, `<tracker>`,
  `<upstream>`, `<security-list>`). [`MISSION.md`](MISSION.md) is
  the establishment proposal that explains why the project exists.
  [`docs/rfcs/`](docs/rfcs/) holds the normative RFCs.
- **Skills** live under [`skills/`](skills/).
  Each is a `SKILL.md` that encodes one workflow. Skills use the
  `<PROJECT>` / `<tracker>` / `<upstream>` placeholders everywhere
  and resolve them at runtime; they must not contain project-
  specific strings.
- **Tools** live under [`tools/`](tools/), one subtree per
  external system the skills talk to. Each subtree is
  project-agnostic. Adapter-side variables are declared in the
  subtree and filled in by the adopter's `<project-config>/`.
- **Project template** under [`projects/_template/`](projects/_template/)
  is the bootstrap scaffold for an adopter's `<project-config>/`
  directory. The adopter clones it into their own tracker repo
  and fills in the TODOs.

### Directory tree

```text
.
├── README.md             # Framework overview + adoption entry point
├── MISSION.md            # Project-establishment proposal (the why)
├── AGENTS.md             # Editorial contract: tone, placeholders, linking
├── CONTRIBUTING.md       # This file
├── docs/
│   ├── rfcs/             # Normative RFCs — RFC-AI-0002, 0003, 0004
│   ├── setup/            # Adoption, sandbox, privacy-LLM docs
│   ├── security/         # Human-facing security-team docs
│   ├── issue-management/ # Issue-* skill docs
│   ├── pr-management/    # PR-* skill docs
│   ├── mentoring/        # Mentor-skill docs
│   ├── modes.md          # The A/B/C/D mode model
│   └── mode-economics.md # Token-cost calibration for each mode
│
├── .claude/
│   └── skills/           # Agent workflows (invoked via the Skill tool)
│       ├── security-*/   # Security-issue lifecycle (10 skills)
│       ├── pr-management-*/  # PR triage, review, mentor, stats (4 skills)
│       ├── issue-*/      # Issue triage, fix, reassess, reproducer, stats (5 skills)
│       ├── setup-*/      # Adoption, sandbox install/verify/update (7 skills)
│       ├── contributor-nomination/
│       ├── write-skill/
│       └── list-skills/
│
├── projects/
│   └── _template/        # Scaffold for an adopter's <project-config>/
│
├── tools/                # Project-agnostic adapters per external system
│   ├── github/           # Forge + tracker bridge (read + write)
│   ├── jira/             # Tracker bridge (read-only Groovy; write path = issue #301)
│   ├── gmail/            # Mail backend (read + write + drafts)
│   ├── ponymail/         # Archive viewer (read-only)
│   ├── mail-source/      # Abstract mail-backend contract; imap/ + mbox/ stubs
│   ├── vulnogram/        # ASF CVE allocation (Python)
│   ├── cve-org/          # MITRE CVE Services v2 (publication check)
│   ├── privacy-llm/      # Redactor + checker (per RFC-AI-0004 §6)
│   ├── agent-isolation/  # Bubblewrap sandbox + network allowlist
│   ├── sandbox-lint/     # Lint settings.json for sandbox correctness
│   ├── skill-and-tool-validator/  # Validate SKILL.md frontmatter + links + placeholders
│   ├── skill-evals/      # Behavioral eval harness for skill steps
│   ├── dashboard-generator/  # HTML dashboard reference impl (Groovy + Python)
│   ├── pr-management-stats/  # Maintainer dashboard data layer
│   ├── security-tracker-stats-dashboard/  # Security-side stats
│   ├── probe-templates/  # Boilerplate for sandbox-probe scripts
│   └── dev/              # Local checkers (placeholders, agent pre-commit)
│
├── .pre-commit-config.yaml   # prek hook set (see "Running the dev loop")
├── pyproject.toml            # Workspace-level Python config
├── uv.lock                   # Reproducible Python lockfile
└── .github/                  # CI: pre-commit, zizmor, link-check, ISSUE_TEMPLATE
```

The adopter-side `.apache-magpie/` snapshot, the per-user
`user.md`, and the `<project-config>/` directory all live in the
**adopter's** tracker repo, not here. The framework never carries
those files.

## Skill families

A skill is a single workflow the agent runs end-to-end with the
maintainer in the loop. Each skill is a markdown file (`SKILL.md`)
with YAML frontmatter, often supported by sibling step-detail files
and bundled scripts. The skill router reads only the frontmatter
`description` field to decide whether to load the skill; the body
is loaded only after the decision.

| Family | Skills | Purpose |
|---|---|---|
| `security-*` | `security-issue-import`, `security-issue-import-from-md`, `security-issue-import-from-pr`, `security-issue-triage`, `security-issue-sync`, `security-issue-deduplicate`, `security-cve-allocate`, `security-issue-fix`, `security-issue-invalidate` | Full lifecycle of a security report from arrival on `<security-list>` through CVE publication. |
| `pr-management-*` | `pr-management-triage`, `pr-management-code-review`, `pr-management-mentor`, `pr-management-stats` | Maintainer-side PR queue management — sweep, classify, review, mentor first-time contributors, surface backlog trends. |
| `issue-*` | `issue-triage`, `issue-fix-workflow`, `issue-reproducer`, `issue-reassess`, `issue-reassess-stats` | Issue-tracker triage, agent-drafted fixes for confirmed bugs, automated reproduction of bug reports, reassessment of EOL backlogs. |
| `setup-*` | `setup`, `setup-isolated-setup-install`, `setup-isolated-setup-verify`, `setup-isolated-setup-update`, `setup-isolated-setup-doctor`, `setup-override-upstream`, `setup-shared-config-sync` | Framework adoption, sandbox install + verify + update + diagnostic, override-promotion workflow, shared-config sync. |
| `contributor-nomination` | one skill | Build the evidence brief for a committer or PMC nomination. |
| Meta-skills | `write-skill`, `list-skills` | Author new skills following framework conventions; print a human-readable skill index. |

Each skill's frontmatter `description` is the agent-router contract.
Be precise — vague descriptions cause the router to load the wrong
skill or miss the right one. The
[`skill-and-tool-validator`](tools/skill-and-tool-validator/README.md) catches the
common shapes of bad description (action-inventory, distinct-from-
sibling-skill, chain-handoff narrative).

### Skill anatomy

A skill directory typically contains:

- **`SKILL.md`** — the main workflow document. YAML frontmatter
  (name, description, license) followed by the procedure.
- **Step-detail files** — one per substantial step (`step-1-…md`,
  `step-2-…md`, …) for multi-step skills.
- **Bundled scripts** — `tools/<skill>-helpers/` or inline scripts
  the skill invokes deterministically (these don't need an LLM).
- **Fixtures + evals** — under [`tools/skill-evals/evals/<skill>/`](tools/skill-evals/evals/),
  one fixture directory per step + case combination, each with
  an `expected.json` the model output must match.

Skills must follow the **proposal → confirm → apply** pattern for
any mutation: surface the action and the diff, wait for explicit
maintainer confirmation, then execute. Read-only inspection is fine
without confirmation; anything that writes to a tracker, posts a
comment, sends an email, or modifies the filesystem is gated.

## Tool families

Tools are project-agnostic adapters to external systems. Each
subtree has a `tool.md` or `README.md` documenting the adapter
surface and what variables the active project's `<project-config>/`
needs to fill in.

| Family | Tools | What they bridge to |
|---|---|---|
| Forge / tracker | `github/`, `jira/` | GitHub Issues + PRs (full); JIRA (read-only Groovy bridge — write path tracked at [#301](https://github.com/apache/magpie/issues/301)) |
| Mail | `gmail/`, `ponymail/`, `mail-source/imap/`, `mail-source/mbox/` | Gmail (full); PonyMail archive (read-only); IMAP + mbox stubs |
| CVE workflow | `vulnogram/`, `cve-org/` | ASF Vulnogram (CVE allocation + JSON generation); MITRE CVE Services v2 |
| Runtime / safety | `agent-isolation/`, `privacy-llm/`, `sandbox-lint/` | Bubblewrap + network-allowlist sandbox; redactor + checker for privacy-LLM gating; settings.json linter |
| Dev loop | `skill-and-tool-validator/`, `skill-evals/`, `dev/` | SKILL.md validation; behavioral eval harness; local placeholder + pre-commit checkers |
| Reporting | `dashboard-generator/`, `pr-management-stats/`, `security-tracker-stats-dashboard/` | HTML dashboards for maintainer + security review |
| Authoring | `probe-templates/` | Boilerplate scaffold for sandbox probes |

New tool subtrees follow the same pattern: a `tool.md` or
`README.md`, an adapter-surface declaration with variables the
adopter fills in, and (for code) a `pyproject.toml` if Python or
a self-contained `.groovy` if Groovy.

## Cross-cutting concerns

Every change must respect these six principles
([RFC-AI-0004](docs/rfcs/RFC-AI-0004.md)). They cut across all
skills and all tools.

1. **Human-in-the-loop on every state change.** Every write,
   transition, comment, mail send, label flip, or filesystem
   mutation needs explicit maintainer confirmation. Read-only
   inspection is fine without confirmation; a skill that auto-
   applies without confirmation is a bug.
2. **Secure sandbox by default.** Agent processes run inside a
   `bubblewrap` sandbox with a network allowlist (see
   [`tools/agent-isolation/`](tools/agent-isolation/) and the
   [`setup-isolated-setup-*`](skills/) skill family).
   Skills must not assume unrestricted host access; tools that
   need network access declare the hosts they reach.
3. **Vendor neutrality.** Skills are markdown-with-YAML, not
   vendor-specific prompts. Anywhere a project-specific name
   would go, use the placeholders `<PROJECT>` / `<tracker>` /
   `<upstream>` / `<security-list>` / `<private-list>` /
   `<default-branch>` — the `check-placeholders` prek hook
   catches violations. Per-CLI runtime ports are tracked at
   issues [#313](https://github.com/apache/magpie/issues/313)–[#322](https://github.com/apache/magpie/issues/322).
4. **Conversational, correctable.** A maintainer override
   (`.apache-magpie-overrides/<skill>.md` in the adopter repo)
   modifies skill behaviour without forking the framework. The
   [`setup-override-upstream`](skills/setup-override-upstream/SKILL.md)
   skill promotes useful overrides back into the framework as PRs.
5. **Write-access discipline.** Outbound messages (PR comments,
   reporter emails, mailing-list posts) are *always* drafted for
   review, never sent autonomously. See AGENTS.md for the draft
   format and threading rules.
6. **Privacy by design.** Private data goes only to LLMs the
   adopter's PMC has approved. The
   [`tools/privacy-llm/`](tools/privacy-llm/) subtree carries the
   redactor and the per-mailing-list gating contract; reporter PII
   on `<security-list>` is redacted with a local map, `<private-list>`
   content never reaches a non-approved LLM. Full design in
   [`docs/setup/privacy-llm.md`](docs/setup/privacy-llm.md).

The placeholder discipline (3) is enforced mechanically:
[`tools/dev/check-placeholders.sh`](tools/dev/check-placeholders.sh)
fails the commit if it finds hardcoded project names like
`apache/airflow` or `Apache Airflow` inside `skills/` or
`tools/`. The others are enforced by reviewer taste + skill-
validator + eval cases.

## Agent harnesses

The framework's reference runtime today is **Claude Code** — skills
are loaded from `skills/<name>/SKILL.md`, MCP servers from
the user's Claude Code config, and the sandbox from
`setup-isolated-setup-install`.

RFC-AI-0004 §3 commits the framework to **vendor neutrality across
LLM backends**. The current state per harness:

| Harness | State | Tracking |
|---|---|---|
| Claude Code | Primary, fully supported | — |
| Codex CLI | Partial — Claude Code plugin delegates rescue + adversarial-review subtasks to Codex | First-class runtime tracked at [#313](https://github.com/apache/magpie/issues/313) |
| Gemini CLI | Not yet ported | [#314](https://github.com/apache/magpie/issues/314) |
| Local LLM (Ollama / llama.cpp / vLLM) | Not yet ported | [#315](https://github.com/apache/magpie/issues/315) |
| Cursor (Composer + Agent CLI) | Not yet ported | [#316](https://github.com/apache/magpie/issues/316) |
| Aider | Not yet ported | [#317](https://github.com/apache/magpie/issues/317) |
| GitHub Copilot CLI + Coding Agent | Not yet ported | [#318](https://github.com/apache/magpie/issues/318) |
| Goose (Block) | Not yet ported | [#319](https://github.com/apache/magpie/issues/319) |
| Amazon Q Developer CLI | Not yet ported | [#320](https://github.com/apache/magpie/issues/320) |
| JetBrains Junie | Not yet ported | [#321](https://github.com/apache/magpie/issues/321) |
| OpenHands | Not yet ported | [#322](https://github.com/apache/magpie/issues/322) |

MCP servers used by the Claude Code runtime today: Slack, Gmail,
Google Calendar, Google Drive, plus framework-internal ones for
the ponymail / incubator-mail / incubator-reports surfaces. MCP-
compatible harnesses (Gemini CLI, Goose, Copilot CLI) should pick
these up directly once the skill-format adapter lands for that
harness.

## Code in this repo

The framework's primary programming language is English — skill
files under `skills/` and tool contracts under `tools/`
are programs executed by the agent (see
[English as code](#english-as-code)). Several deterministic
operations are also implemented in traditional programming
languages where bit-exact output matters more than judgement.
This section covers the traditional-language code; the English
layer is covered under [Skill families](#skill-families) and
[Tool families](#tool-families) above.

### Python (uv-managed)

All Python lives under `tools/`, each as its own `uv`-managed
package with `pyproject.toml`. The workspace's `uv.lock` at the
repo root pins versions across all packages.

| Package | Purpose |
|---|---|
| [`tools/cve-tool-vulnogram/generate-cve-json/`](tools/cve-tool-vulnogram/generate-cve-json/) | Emits paste-ready CVE 5.x JSON from a tracker body. Invoked by `security-issue-sync` and `security-cve-allocate`. |
| [`tools/cve-tool-vulnogram/oauth-api/`](tools/cve-tool-vulnogram/oauth-api/) | OAuth helper for Vulnogram API authentication. |
| [`tools/gmail/oauth-draft/`](tools/gmail/oauth-draft/) | Gmail OAuth helper for the drafts-only mail-source flow. |
| [`tools/skill-and-tool-validator/`](tools/skill-and-tool-validator/) | Validates `SKILL.md` frontmatter, internal links, and placeholder discipline. |
| [`tools/skill-evals/`](tools/skill-evals/) | Behavioral eval harness for skill steps. Pure-stdlib runner; no third-party deps. |
| [`tools/sandbox-lint/`](tools/sandbox-lint/) | Lints `settings.json` for sandbox-correctness regressions. |
| [`tools/privacy-llm/checker/`](tools/privacy-llm/checker/) | Verifies that data destined for an LLM matches the privacy-LLM policy. |
| [`tools/privacy-llm/redactor/`](tools/privacy-llm/redactor/) | Redacts reporter PII before content reaches a non-approved LLM. |

Common invocation pattern (run from the package directory):

```bash
cd tools/cve-tool-vulnogram/generate-cve-json
uv run pytest                  # unit tests
uv run ruff check              # lint
uv run ruff format             # auto-format (check-only in CI)
uv run mypy                    # type-check
```

To run a package's CLI from the repo root:

```bash
uv run --project tools/cve-tool-vulnogram/generate-cve-json generate-cve-json <N> --attach
```

`skill-evals` is a special case — pure stdlib, no `uv` needed:

```bash
PYTHONPATH=tools/skill-evals/src python3 -m skill_evals.runner \
    tools/skill-evals/evals/security-issue-import/
```

### Groovy

Two Groovy reference implementations live in the tree. Groovy is
used where a deterministic CLI is needed but Python's startup cost
or async story is awkward — JVM warmup is a one-time cost per
invocation, after which HTTP and JSON are fast and stdlib-only.

| File | Purpose |
|---|---|
| [`tools/jira/bridge.groovy`](tools/jira/bridge.groovy) | Read-only JIRA REST bridge — `search <JQL>`, `issue <KEY>`, `projects`. Uses `@Grab` for HTTP deps, no separate install step. |
| [`tools/dashboard-generator/reference.groovy`](tools/dashboard-generator/reference.groovy) | Reference impl of the issue-reassess-stats HTML dashboard. Reads `verdict.json` artefacts from a campaign directory and emits HTML. |

Install Groovy 3.x or newer on `PATH` — `sdk install groovy` via
[SDKMAN!](https://sdkman.io/) or your package manager. Then:

```bash
# JIRA bridge — list open issues for a project
ISSUE_TRACKER_URL=https://issues.apache.org/jira \
ISSUE_TRACKER_PROJECT=FOO \
  groovy tools/jira/bridge.groovy \
    search 'project = FOO AND status = Open AND resolution = Unresolved'

# Dashboard generator
groovy tools/dashboard-generator/reference.groovy \
    /path/to/campaign-dir --output dashboard.html
```

The first invocation downloads `@Grab` dependencies into the
local Grape cache; subsequent runs are fast.

Both Groovy files have parallel Python reference implementations
under the same subtree (`reference.py` for the dashboard;
[#301](https://github.com/apache/magpie/issues/301) tracks
the Python port of the JIRA bridge alongside the write path).
**Languages other than Groovy or Python are welcome via PR** — the
contract that matters is the CLI surface and the JSON output shape.

### Shell scripts

- [`tools/agent-isolation/`](tools/agent-isolation/) holds the
  shell scripts (`agent-iso.sh`, sandbox status-line helpers,
  the placeholder pre-commit script) that wire the agent into
  the bubblewrap sandbox. POSIX bash.
- [`tools/dev/`](tools/dev/) holds the local pre-commit checkers
  invoked from `.pre-commit-config.yaml`.

Shell scripts are deterministic — no agent in the execution path
— so they are tested by running them and observing the output.

## Getting set up

You need these tools on your machine:

- **`uv`** — the Python runner for every Python package.
  `curl -LsSf https://astral.sh/uv/install.sh | sh` or your package
  manager.
- **`prek`** — the `pre-commit`-compatible hook runner.
  `uv tool install prek` or `pipx install prek`.
- **`gh` CLI** — needed to drive tracker reads (and writes) if you
  run any skill end-to-end. `brew install gh` or equivalent.
- **`groovy`** — only if you're working on a Groovy tool. SDKMAN!
  (`sdk install groovy`) or your package manager.

First-time clone:

```bash
git clone git@github.com:apache/magpie.git
cd magpie
uv tool install prek
prek install                   # wire the hooks into .git/hooks
prek run --all-files           # runs every hook on every file
```

Note that if you are already using `prek` for some other project, you
may need to do the following:

```bash
git config --local core.hooksPath .git/hooks
prek install
```

The hooks are described in detail under [Running the dev loop](#running-the-dev-loop).

If you intend to actually run framework skills against an adopter
project (not just edit the framework), follow the
[`setup-isolated-setup-install`](skills/setup-isolated-setup-install/SKILL.md)
skill to install the bubblewrap sandbox and pinned tools, then
[`setup-isolated-setup-verify`](skills/setup-isolated-setup-verify/SKILL.md)
to confirm the install. The full adoption tutorial lives at
[`docs/setup/install-recipes.md`](docs/setup/install-recipes.md).

### Lightening the agent context

Many skills in this repository are runtime workflows for adopters
(security triage, PR management, CVE allocation). They have no use
while you are *editing the framework itself*, but they still load
into the agent's context window and crowd out the files you
actually need to read.

Opt out per skill by adding a `.claude/settings.local.json` to your
clone (gitignored) and listing the skills you want disabled:

```json
{
  "$schema": "https://json.schemastore.org/claude-code-settings.json",
  "skillOverrides": {
    "magpie-pr-management-code-review": "off",
    "magpie-pr-management-mentor": "off",
    "magpie-pr-management-stats": "off",
    "magpie-pr-management-triage": "off",
    "magpie-security-cve-allocate": "off",
    "magpie-security-issue-deduplicate": "off",
    "magpie-security-issue-fix": "off",
    "magpie-security-issue-import": "off",
    "magpie-security-issue-import-from-md": "off",
    "magpie-security-issue-import-from-pr": "off",
    "magpie-security-issue-invalidate": "off",
    "magpie-security-issue-sync": "off",
    "magpie-setup-isolated-setup-install": "off",
    "magpie-setup-isolated-setup-update": "off",
    "magpie-setup-isolated-setup-verify": "off",
    "magpie-setup-override-upstream": "off",
    "magpie-setup-shared-config-sync": "off",
    "magpie-setup": "on",
    "magpie-write-skill": "on"
  }
}
```

The file is per-clone and per-user; nothing from it gets committed.
Flip a skill back to `"on"` (or remove the entry) when you start
working on that area.

## Making changes

Think about **which layer the change belongs in** before you start
editing:

| You want to change … | Edit under … |
|---|---|
| The framework's overall purpose, mission, or scope | [`MISSION.md`](MISSION.md) |
| A normative principle that cuts across the framework | [`docs/rfcs/`](docs/rfcs/) (new RFC) |
| An editorial / confidentiality / placeholder rule | [`AGENTS.md`](AGENTS.md) |
| A skill's workflow | [`skills/<name>/SKILL.md`](skills/) |
| An adapter surface for an external system | the matching [`tools/<system>/`](tools/) subtree |
| Bootstrap scaffolding for an adopter `<project-config>/` | [`projects/_template/`](projects/_template/) |
| Sandbox / privacy-LLM / dev-loop infrastructure | [`tools/agent-isolation/`](tools/agent-isolation/), [`tools/privacy-llm/`](tools/privacy-llm/), [`tools/dev/`](tools/dev/) |
| Anything project-specific (canned reply, milestone convention, scope label) | **not in this repo** — that lives in the adopter's `<project-config>/` |

Rules of thumb for each layer:

- **Root docs, skills, and tool adapters are project-agnostic.**
  Never paste concrete names into them. Use `<PROJECT>` /
  `<tracker>` / `<upstream>` / `<security-list>` placeholders.
  URL targets in markdown links may point at concrete paths so the
  links stay clickable during review — the placeholder lives in
  the visible label only. Enforced by the `check-placeholders`
  prek hook.
- **Skills never mutate state without user confirmation.** If you
  add a new action, write the proposal / confirm / apply shape into
  the skill and the guardrails into AGENTS.md. See the existing
  skills for the pattern. The skill-evals suite has explicit
  guardrail cases that catch unconfirmed mutations.
- **Tool adapters declare their adopter-side variables.** If a
  recipe varies per project (different Gmail domains, different
  GitHub org, different board node IDs), the adapter declares the
  variable and the active project's `<project-config>/project.md`
  fills it in. The adapter does *not* read `<project-config>/`
  itself — the calling skill resolves the variable and passes it
  via environment.
- **Skill behaviour changes require eval updates.** If you change
  what a skill should output for a given input, the corresponding
  eval case under [`tools/skill-evals/evals/<skill>/`](tools/skill-evals/evals/)
  needs its `expected.json` updated in the same PR. See AGENTS.md
  *Keeping evals and mode-economics in sync* for the rule.

## Authoring with an agent

Most contributions to this repository are authored **agentically**,
in a conversation between you and a coding agent (Claude Code today;
any of the harnesses tracked in [Agent harnesses](#agent-harnesses)
once their adapters land). The loop is different from traditional
programming, and worth describing explicitly — getting the rhythm
right is the difference between a smooth contribution and a
frustrating one.

**The framework is code at two abstraction levels.** The bulk —
skills, tool contracts, RFCs — is English, executed by an agent
(see [English as code](#english-as-code)). The minority — Python
and Groovy bridges under [`tools/`](tools/) — is traditional-
programming-language code, executed by `python` / `groovy`. Both
layers are best authored by describing intent to the agent and
reviewing the diff, not by typing each line by hand. The artefact
you ship is text; the *method* by which the text gets produced is
a conversation.

**Lead with intent, not with code.** When you sit down to make a
change, open with **what** you want and **why** — not a code
snippet, not a file path, not a half-drafted solution. The agent's
job is to figure out **how**. Examples of good opening prompts:

- *"I want `security-issue-triage` to also flag reports that arrive
  with a draft GHSA URL in the body. Why: those reports are
  almost always pre-coordinated by an external CNA, and the
  current flow treats them as fresh inbound — which wastes a
  triage cycle. Find the right step and propose the change."*
- *"Add a Bugzilla bridge per `tools/<system>/tool.md`. Why: see
  issue #302 — Apache OpenOffice is blocked on this. Don't write
  the full implementation yet; first show me the contract surface
  (subcommand list + flag shapes) and we'll iterate."*
- *"The placeholder linter is flagging a false positive on
  `<security-list>` inside a quoted block. Why: the rule is "no
  hardcoded project names in skill prose", and quoted examples
  *are* prose. Trace the rule, propose the narrowest fix that
  preserves the original intent, and run the existing tests."*

Each of these is **intent-first**. You're telling the agent the
shape of the answer and the constraint that matters, then handing
over the synthesis. The agent will surface decisions you didn't
think of (which is exactly what you want it to do) — and you'll
correct the ones it gets wrong.

**Iterate, don't dictate.** Once the agent proposes a change, treat
the proposal as a draft, not a final. The loop is:

1. **Agent proposes** — a diff, a new file, a refactor plan.
2. **You read carefully** — does the change match what you meant?
   Does it respect the placeholder convention? Does it follow the
   proposal / confirm / apply pattern? Does it touch files outside
   the intended layer?
3. **You push back specifically** — *"the variable name should
   match what `tools/jira/tool.md` calls it"*, *"this needs a
   guardrail case in the eval suite"*, *"don't add a comment that
   restates the function name"*. Specific corrections converge fast;
   vague ones produce mush.
4. **Agent revises** — and the loop repeats.
5. **Tests run** — `prek run --all-files`, `uv run pytest` in the
   affected Python package, the eval suite for the affected skill.
   When something fails, the failure is part of the conversation —
   show the agent the error, let it diagnose.

The conversation usually converges in three or four rounds. If
it doesn't, the intent was probably under-specified — back up,
restate the goal more sharply, and try again from a clean turn.

**Probe boundary conditions explicitly.** This is the single
highest-leverage habit. After the agent has a working first cut,
ask:

- *"What happens if the field is empty? If it's malformed JSON?
  If the upstream API returns a 503? If two skills disagree on the
  same input?"*
- *"What's the smallest input that breaks this?"*
- *"What's the existing skill / tool that does something similar —
  and does this change behave the same way at the edges?"*

The agent will often find edge cases it didn't handle, propose
fixes, and (importantly) codify the edge cases as eval fixtures
or test cases. That codification is what stops the same edge case
regressing six months later when somebody else iterates on the
same skill.

**Author = editor; agent = typist with opinions.** Your job is
to know what *should* exist and to recognise when the draft has
landed. The agent's job is to type confidently, surface decisions,
and push back when your instruction is internally inconsistent.
Both jobs are essential — neither side runs the loop alone. When
the agent says *"this contradicts the rule in AGENTS.md line 47"*
or *"the eval case under `step-3-classify/` will fail with this
change"*, listen — that's the agent earning its seat.

**Where traditional programming languages enter the picture.** The
Python and Groovy bridges under `tools/` are written in lower-level
languages with stronger machine-checked feedback than the English
layer gets. Both layers are code (see
[English as code](#english-as-code)); they differ in what *catches*
your mistakes — `pytest` / `mypy` / `ruff` catch syntactic and type
bugs deterministically; the eval suite catches semantic regressions
in skill behaviour. The loop is the same — intent-first, iterate,
probe edges — but for the Python / Groovy pieces the inner-loop
feedback is faster. When working on a Python bridge:

- Run `uv run pytest` *between every revision*, not just at the
  end. A failing test halfway through is information; a stack of
  failing tests at the end is a mess.
- `mypy` errors are the agent's responsibility to diagnose, not
  yours — paste the error back into the conversation and let the
  agent reason about it.
- Resist the temptation to hand-edit the agent's code mid-loop.
  If something needs to change, *tell the agent what to change* —
  hand-edits desynchronise the agent's mental model from the
  actual file and the next iteration drifts.

**Concrete first moves.** The framework provides agent entry
points for the two most common authoring tasks:

- **New skill** — invoke [`/magpie-write-skill`](skills/write-skill/SKILL.md).
  The meta-skill walks you through the framework's skill shape
  (frontmatter, resources, placeholder convention, prompt-injection
  defences, privacy-LLM gate-check), scaffolds the directory, and
  validates the result via [`skill-and-tool-validator`](tools/skill-and-tool-validator/).
- **Modify an existing skill** — open the conversation with the
  skill's `SKILL.md` in context. State what behaviour should change
  and why; the agent will propose the diff plus the eval-case
  updates that go with it.
- **New tool bridge** — start from the contract doc (`tools/<system>/tool.md`
  or [`tools/mail-source/contract.md`](tools/mail-source/contract.md))
  and the closest existing bridge as a reference. Ask the agent to
  draft the subcommand surface first, then the implementation, then
  the README.
- **Documentation change** — quote the existing prose, state what
  feels wrong, let the agent propose a rewrite. Doc PRs are the
  fastest agentic loop in the repository.

**When the agent gets stuck or goes in circles**, the usual causes:
the intent is under-specified (restate it more sharply); the agent
is missing context from a file it didn't read (point at the file
explicitly); the change spans more than one concern (split the
work). Walking away for a minute and coming back with a fresh
opening prompt often beats forcing the existing conversation to
converge.

**The agent is not the reviewer.** Once you're happy with the
change, **you** are responsible for the PR — its scope, its
commit message, its description, and its correctness. CI, the
eval suite, and the human reviewer on the PR are the
verification layer. The agentic loop produces the artefact; the
PR review process verifies it. Both are necessary; neither
substitutes for the other.

## Running the dev loop

Every change should pass `prek run --all-files` locally before you
open a PR — CI runs the same config. The hook set:

- **`doctoc`** — regenerates TOCs on every `.md` file (except
  skill `SKILL.md` files, which keep YAML frontmatter at the top,
  and skill-evals fixture/README files).
- **`pre-commit-hooks`** — `end-of-file-fixer`, `trailing-whitespace`,
  `mixed-line-ending`, `check-merge-conflict`, `detect-private-key`.
- **`markdownlint-cli2`** — flags structurally bad markdown
  (broken anchors via MD051, dangling link refs via MD053).
  Style choices are intentionally left alone.
- **`typos`** — fast spell-checker. Allowlist of project-specific
  terms (`CNA`, `Vulnogram`, `ponymail`, etc.) in `.typos.toml`.
- **`check-placeholders`** — local script at
  [`tools/dev/check-placeholders.sh`](tools/dev/check-placeholders.sh)
  that refuses hardcoded references like `apache/airflow` or
  `Apache Airflow` inside `skills/` or `tools/`. The
  framework convention is the `<PROJECT>` / `<tracker>` /
  `<upstream>` placeholder set.
- **Per-package Python checks** — `ruff check`, `ruff format --check`,
  `mypy`, `pytest` against each `tools/*/` Python package, scoped
  to changes inside that package directory via the hook's `files:`
  pattern.

Separate GitHub workflows:

- **`pre-commit.yml`** — runs `prek run --all-files` in CI.
- **`zizmor.yml`** — lints GitHub Actions workflows for known-bad
  patterns; runs on every PR.
The link check ([lychee](https://lychee.cli.rs/)) is **not** a
separate workflow — it runs as the `lychee` hook inside
`prek run --all-files` (the `pre-commit.yml` workflow above), and so
is part of the required `prek` status check. It is a **hard gate**: a
single broken internal link, dead `#anchor` fragment, or unreachable
external URL fails `prek` and blocks merge. The hook is
`language: rust`, so prek installs lychee itself — `prek run lychee`
locally (no separate lychee install needed) catches the same errors
before you push.

To run a single Python package's tests directly:

```bash
cd tools/skill-and-tool-validator
uv run pytest
```

To run a Groovy tool directly:

```bash
groovy tools/jira/bridge.groovy projects
```

To run skill-evals for one skill:

```bash
PYTHONPATH=tools/skill-evals/src python3 -m skill_evals.runner \
    tools/skill-evals/evals/security-issue-import/
```

See [`tools/skill-evals/README.md`](tools/skill-evals/README.md)
for the full eval invocation surface (single step, single case,
agent self-eval mode).

## Opening a pull request

- **Base branch:** `main`. Do not open PRs against any other branch
  unless explicitly coordinated.
- **Scope:** one concern per PR. A skill change, a tool-adapter
  addition, and a doc update land as separate PRs.
- **Commit message:** Conventional Commits style — `feat(skills): …`,
  `fix(tools/github): …`, `docs(rfcs): …`, `chore(deps): …`, etc.
  Imperative-present subject, ≤72 chars, plain prose body
  explaining *why*. Pass via HEREDOC to preserve formatting:

  ```bash
  git commit -m "$(cat <<'EOF'
  feat(tools/foo): add bar capability

  Why: skills X and Y need a way to do Z; previously they shelled
  out to a one-off snippet that didn't survive a sandbox change.

  EOF
  )"
  ```

- **PR description:** one `## Summary` section (1–3 bullets of
  *what changed and why*) and one `## Test plan` section (how you
  verified). The `gh pr create` template in this repo matches.
- **CI gates:** `prek run --all-files`, `zizmor`, `lychee`, and
  every entry in the `tests-ok` pytest-matrix umbrella must pass.
  All gates run automatically on every PR.
- **Reviews:** at least one approval from a repo collaborator. Any
  change that edits [`AGENTS.md`](AGENTS.md), an RFC, or a skill
  file should get an extra set of eyes because those ripple into
  every future sync.
- **Rebase + prek before push.** Hooks auto-fix many issues; CI
  rejects unfixed. Standard incantation:

  ```bash
  git fetch origin main
  git rebase origin/main
  prek run --all-files
  git push
  ```

## Your first contribution

Good entry points, in rough order of ramp-up cost:

1. **Pick a [`good first issue`](https://github.com/apache/magpie/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22).**
   The current backlog has 24+ such issues, including 22 net-new
   tool / adapter bridges and per-CLI runtime ports tracked at
   [#301–#322](https://github.com/apache/magpie/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22+sort%3Acreated-desc).
   Before you start work, please leave a comment on the issue so a
   maintainer can assign it to you. That keeps two people from working
   on the same issue at the same time.
   Two clusters:
   - **Tool bridges** ([#301–#312](https://github.com/apache/magpie/issues/301)) — JIRA write path, Bugzilla, IMAP / mbox concrete wiring, GitLab, Mailman 3 / Hyperkitty, Discourse, Zulip, Matrix, Forgejo, OSV.dev, Pagure.
   - **Agent-CLI runtime adapters** ([#313–#322](https://github.com/apache/magpie/issues/313)) — Codex, Gemini, local-LLM, Cursor, Aider, gh-copilot, Goose, Amazon Q, Junie, OpenHands.

   Each issue is self-contained: tool location, suggested
   capabilities, why-useful context, references to existing tools
   to mirror the shape of.

2. **Documentation improvements.** Read a skill or a doc, find a
   gap or a stale reference, fix it. The `docs/setup/`,
   `docs/security/`, and `docs/pr-management/` trees are all
   actively curated and welcome refinement. The `link-check`
   workflow surfaces broken anchors and dead URLs daily — work
   from that report is high-value.

3. **Eval fixtures.** [`tools/skill-evals/evals/`](tools/skill-evals/evals/)
   has 380+ cases across 18 skills, but every skill could use more
   edge cases. A new fixture is a directory with `input.json` +
   `expected.json` + a `README.md` describing the scenario.
   Lower friction than skill code changes — no model behaviour
   change, just better test coverage. See
   [`tools/skill-evals/README.md`](tools/skill-evals/README.md)
   for the fixture format.

4. **A new skill via [`/magpie-write-skill`](skills/write-skill/SKILL.md).**
   The meta-skill walks you through the framework's skill shape
   (frontmatter, resources, placeholder convention, prompt-injection
   defences, privacy-LLM gate-check) and validates via
   [`skill-and-tool-validator`](tools/skill-and-tool-validator/). The scaffold puts
   you in the right shape from the start.

5. **A tool-bridge implementation** (the hardest of these but the
   most rewarding for a first contribution if you're comfortable
   with API design). Pick a `tool/*` stub or a `good first issue`
   bridge, follow the contract in `tools/<system>/tool.md` (or for
   mail backends, [`tools/mail-source/contract.md`](tools/mail-source/contract.md)),
   land a Python or Groovy implementation, document the adapter
   surface variables, and add eval cases for any new skill steps
   that depend on it.

If you're not sure which is the right fit, open a draft issue
describing what you want to try and a maintainer will route you.

## Confidentiality

This repository (`apache/magpie`) is **public**. The
confidentiality rules in AGENTS.md primarily apply to **adopters'
own tracker repositories**, which are private (security tracker
contents must never appear on a public surface). But contributors
to this framework repo should still know the rules — most skills
deal with mail / tracker contents at runtime, and skill prose can
inadvertently leak information shape.

Practical rules for *this* repo:

- **Never paste real reporter PII into a fixture, eval case, or
  doc example.** Use synthetic names and synthetic emails — the
  existing fixtures all do.
- **Never paste a real security tracker URL or `#NNN` reference
  into a skill or doc.** Use `<tracker>#NNN` or a synthetic
  placeholder.
- **Never paste real CVE allocation tool URLs that leak
  pre-publication CVE IDs.** Use `<cve-allocate-url>` or the
  redacted variant.
- **Reporter-supplied CVSS scores are informational only** — never
  treat them as authoritative in skill prose. Full rationale in
  [`AGENTS.md`](AGENTS.md).
- **Per-user config (`user.md`)** stays in adopter repos,
  gitignored. It never lives here.

Anything you're unsure about, ask in the PR description or open a
draft and tag a maintainer.

## Authoritative references

When this file and a layer-specific doc disagree, the
layer-specific doc wins. Re-read it first:

- [`MISSION.md`](MISSION.md) — establishment proposal; the *why*.
- [`README.md`](README.md) — framework overview and adoption
  entry point.
- [`AGENTS.md`](AGENTS.md) — editorial and confidentiality rules.
- [`docs/rfcs/RFC-AI-0004.md`](docs/rfcs/RFC-AI-0004.md) — the six
  principles that govern every change.
- [`docs/rfcs/`](docs/rfcs/) — full RFC set.
- [`docs/setup/`](docs/setup/) — adoption, sandbox, privacy-LLM,
  override workflow.
- [`skills/<name>/SKILL.md`](skills/) — the
  workflow each skill enforces.
- [`tools/<name>/`](tools/) — per-tool adapter contracts.
- [`tools/skill-evals/README.md`](tools/skill-evals/README.md) —
  the eval harness and fixture format.
- [`tools/skill-and-tool-validator/README.md`](tools/skill-and-tool-validator/README.md) —
  the SKILL.md validation contract.
