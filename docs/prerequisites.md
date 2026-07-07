<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Prerequisites for running framework skills](#prerequisites-for-running-framework-skills)
  - [Prerequisites for running the agent skills](#prerequisites-for-running-the-agent-skills)
    - [1. An agentic tool + access to an LLM](#1-an-agentic-tool--access-to-an-llm)
    - [2. A mail backend (read + draft — Gmail is one option, not the only one)](#2-a-mail-backend-read--draft--gmail-is-one-option-not-the-only-one)
    - [3. A tracker + change-request backend (GitHub by default — not required)](#3-a-tracker--change-request-backend-github-by-default--not-required)
    - [4. PMC membership (only for CVE allocation)](#4-pmc-membership-only-for-cve-allocation)
    - [5. Browser (for the human-click steps)](#5-browser-for-the-human-click-steps)
    - [6. Local `<upstream>` clone (only for `security-issue-fix`)](#6-local-upstream-clone-only-for-security-issue-fix)
    - [7. `uv` (for `generate-cve-json`)](#7-uv-for-generate-cve-json)
    - [8. ASF project-metadata MCP (`apache-projects`)](#8-asf-project-metadata-mcp-apache-projects)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Prerequisites for running framework skills

If you only plan to **comment on issues** from the project
board, skip this document — a browser and your tracker
collaborator access are enough. If you plan to **invoke any
framework skill**, check the following before running it.
Each skill also runs a short Step 0 pre-flight against this
list and stops with a clear message if something is missing.

## Prerequisites for running the agent skills

If you only plan to **comment on issues** from the board, skip this
section — a browser and your `<tracker>` collaborator access are
enough.

If you plan to **run any of the agent skills** (`import`, `sync`,
`security-cve-allocate`, `fix`, `generate-cve-json`, `deduplicate`) — typically
as a rotational triager, remediation developer, or release manager —
check the following setup **before** invoking a skill. Each skill also
runs a short Step 0 pre-flight against the same list and stops with a
clear message if something is missing, so you do not discover a
missing piece half-way through a workflow.

### 1. An agentic tool + access to an LLM

Running Magpie needs two things: an **agentic coding tool** that speaks
the `SKILL.md` / [`AGENTS.md`](https://agents.md/) skill convention, and
**access to an LLM** for that tool to drive. There is no hard dependency
on any single vendor for either — any agent that reads the shared
`.agents/skills/*/SKILL.md` files and follows their steps should work.

**Agentic tool — two are fully supported today:**

- **[OpenCode](https://opencode.ai/)** is the **reference implementation**:
  it is open source and model-agnostic, so it can drive *every* LLM-access
  option below.
- **[Claude Code](https://www.anthropic.com/claude-code)** is a second
  complete implementation, powered by Anthropic subscriptions — the paid
  plans, or the free tier Anthropic often grants to open-source
  maintainers.

Support for more runtimes (Codex, Gemini CLI, Cursor, Copilot, …) is
tracked in the
[open adapter issues](https://github.com/apache/magpie/issues?q=is%3Aissue%20is%3Aopen%20adapter).

**Access to an LLM — any one of these works:**

- a **paid LLM subscription** (e.g. Anthropic, for Claude Code);
- a **free subscription** — several providers grant free or discounted
  access to open-source maintainers;
- an **organisation-hosted LLM** — for example the planned
  [`llm.apache.org`](https://llm.apache.org) endpoint for ASF projects;
- an **open-weight model** — hosted on a provider of your choice, or run
  **locally** (Ollama, llama.cpp, vLLM) for sovereign or air-gapped use.

Because **OpenCode is model-agnostic it is the reference tool — it allows
all of the above**; Claude Code is the complete alternative for the
Anthropic-subscription paths. That is also the concrete answer to *"what
does an LLM or agent need to provide to be usable with Magpie?"*: an agent
on the `SKILL.md` / `AGENTS.md` convention, plus any one of the LLM-access
paths above.

The agent runs against pre-disclosure CVE content (private mail
threads, draft advisories, in-flight tracker discussions). Run it
with the credential-isolation setup documented in
[`docs/setup/secure-agent-setup.md`](setup/secure-agent-setup.md) — a layered
defence built around the agent's filesystem sandbox, tool-level
permission rules, and a harness-neutral clean-env wrapper
(`agent-iso.sh`, exposing both a `claude-iso` and an `opencode-iso`
launcher) that strips credential-shaped variables from the agent's
environment. The permission + sandbox posture is enforced for both
harnesses — a `PreToolUse` hook / `tool.execute.before` plugin
(`agent-guard`), plus `permission-audit` / `sandbox-lint` for the
Claude `settings.json` and OpenCode `opencode.json` policies. The
required system tools (`bubblewrap`, `socat`, and the agent CLI
itself — `claude-code` or `opencode`) are pinned with a 7-day
upstream-release cooldown, mirroring the same convention the
framework uses for its `[tool.uv] exclude-newer` and Dependabot
configs.

### 2. A mail backend (read + draft — Gmail is one option, not the only one)

The import, sync, and security-cve-allocate skills **read the security-list
mail thread** for each tracker and **draft replies** on it. Both sides are
vendor-neutral contracts — `contract:mail-source` / `contract:mail-archive`
for reads and `contract:mail-create` for drafts — so **Gmail is one
backend, not a requirement:**

- **Read** backends: the
  [Claude Gmail MCP](https://docs.anthropic.com/en/docs/build-with-claude/mcp)
  (a security-team member's Gmail subscribed to the list), the ASF
  **PonyMail** MCP (below), or a **local mbox / Maildir archive** for
  offline / forensic triage
  ([`tools/mail-source/mbox`](../tools/mail-source/mbox/README.md)).
- **Draft** backends: Gmail, or the offline local **Maildir** backend
  (below).

The ASF-default setup is described next; a project on a different mail
stack declares its own backends in
`<project-config>/project.md → Mail sources`.

There is now an official ASF alternative for the **read** side:
[`apache/comdev`'s `mcp/ponymail-mcp/`](https://github.com/apache/comdev/tree/main/mcp/ponymail-mcp)
(under the ComDev PMC; originally authored by Rich Bowen, former ASF
board director and ComDev lead, with supply-chain hardening and
private-list restrictions layered in upstream) supports ASF LDAP
OAuth and can read private ASF lists. Individual triagers can wire
it up to read inbound `security@<project>.apache.org` threads
without subscribing a personal Gmail account — see
[`tools/ponymail/tool.md`](../tools/ponymail/tool.md) for the
setup. (PonyMail MCP is read-only — it has no `create_draft`
equivalent — so it covers the archive **read** side only.)

On the **draft (reply)** side, Gmail is no longer the only option.
Alongside the Gmail backend, Magpie now ships a local
[**Maildir** draft backend](../tools/maildir/) (`contract:mail-create`,
vendor `Maildir`): it composes an editable RFC 5322 message into a
local Maildir with **no cloud account, no credentials and no
network**, and any Maildir-aware mail client (Thunderbird, mutt,
Evolution, …) picks it up to review, edit and send. So the reply
path no longer requires Gmail — Gmail stays the default where a
triager already reads the list there, and the offline Maildir
backend covers everyone else. Like every `contract:mail-create`
backend, both only ever create drafts; a human sends.

**For ASF projects the PonyMail MCP is a mandatory prerequisite,
not an opt-in backstop.** The reference adopter's manifest declares
`ponymail` with `mandatory: yes` (see
[`<project-config>/project.md → Mail sources`](<project-config>/project.md#mail-sources)),
so the mail-reading skills that run the Step 0 mail-source check
(`security-issue-import`, `security-issue-sync`) **refuse to start**
if it is not installed and reachable — the configured
`contract:mail-create` backend (Gmail by default, or the offline
Maildir backend) handles the drafts, but PonyMail must also be
present for the read side. (Skills that
only read a single Gmail thread opportunistically, such as
`security-cve-allocate`, do not hard-gate on it.) Install it from the **latest `main`** of `apache/comdev`
(the MCP servers ship as in-repo source with no tagged releases —
`main` is the only channel; see
[`tools/ponymail/tool.md → Keeping the checkout current`](../tools/ponymail/tool.md#keeping-the-checkout-current)).
A non-ASF adopter with no `lists.apache.org` archive sets that row
to `mandatory: no`.

**Without this connection:** `security-issue-import` cannot find new
reports, `security-issue-sync` cannot reconcile status with the mail
thread, and no skill can draft replies to reporters. The skills will
refuse to start and tell you to configure the MCP first.

### 3. A tracker + change-request backend (GitHub by default — not required)

Every skill reads and writes issues on the project's **tracker**, and the
`pr-management-*` skills drive its **change-request** (review + merge)
backend. Both are vendor-neutral contracts — `contract:tracker` (GitHub or
JIRA), `contract:change-request` (GitHub PRs, JIRA patches, or dev@
`[PATCH]` mail), `contract:source-control` (Git, GitHub, or SVN) — so
*which* connection you need depends on how the project is hosted, and
**`gh` is not a universal prerequisite:**

- **GitHub-hosted projects (the ASF default).** Authenticate the `gh` CLI
  (`gh auth status`) on the shell the agent runs in, with collaborator
  access (any level) on `<tracker>`. `security-issue-fix` additionally
  needs a fork of `<upstream>` on your GitHub account (it pushes a branch
  there, then opens the PR via `gh pr create --web`). Claude Code also
  ships a GitHub MCP; `gh` covers the rest and is what OpenCode uses.
- **JIRA / SVN-first projects.** No `gh` is required. The tracker is JIRA,
  review + merge run through `jira-patch` or `dev@` `[PATCH]` mail, and
  commits land via SVN — declare those backends in
  `<project-config>/project.md` and install their CLIs (`svn`, the JIRA
  connection) instead.

The security-team roster is maintained per-project; for the active project
see
[`<project-config>/release-trains.md`](<project-config>/release-trains.md#security-team-roster).

### 4. PMC membership (only for CVE allocation)

The adopting project's CVE-tool allocation form is **PMC-gated** on
the server side — only the project's PMC members can submit a CVE
allocation. Non-PMC triagers can still run `security-cve-allocate`; the
skill detects this up front (it asks *"are you a PMC member of
`<PROJECT>`?"*) and produces a relay message for a PMC member to
click through instead. The concrete tool + URL is declared in
[`<project-config>/project.md → CVE tooling`](<project-config>/project.md#cve-tooling).

The same PMC gate applies to ponymail URL lookups on private ASF
lists — only PMC members (via ASF LDAP) can see private-list
archives directly, whether through `ponymail-mcp`'s OAuth flow or
the `lists.apache.org` web UI.

### 5. Browser (for the human-click steps)

Several parts of the process involve a form a human has to fill in
and click — the CVE-tool allocation form, the CVE record `#source`
paste, the `gh pr create --web` compose view. The skills prepare
the URL and the exact text to paste and hand it off to the browser;
they do not try to automate those clicks.

### 6. Local `<upstream>` clone (only for `security-issue-fix`)

The fix skill writes the change in your local clone, runs local
checks and tests, pushes a branch to your fork, and opens a PR via
`gh pr create --web`. You need:

- a clean clone of `<upstream>` reachable from the agent's working
  directory — the path comes from `.apache-magpie-overrides/user.md →
  environment.upstream_clone`, set interactively the first time
  you run the skill;
- the adopting project's dev toolchain installed per
  [`<project-config>/fix-workflow.md → Toolchain`](<project-config>/fix-workflow.md#toolchain);
- a remote named for your GitHub fork that `gh pr create` can push
  to.

### 7. `uv` (for `generate-cve-json`)

The `generate-cve-json` script is a small `uv`-managed Python
project. Install `uv` once
(<https://github.com/astral-sh/uv>); the script bootstraps the
rest.

### 8. ASF project-metadata MCP (`apache-projects`)

The skills that reason about **rosters, people, and release
history** — `contributor-nomination` (Apache ID verification,
vendor-neutrality / employer context), the roster-resolution paths
in `security-issue-sync` / `security-cve-allocate`, and the
forthcoming `release-*` family — read ASF project metadata through
the official ASF
[`apache/comdev` `mcp/apache-projects-mcp/`](https://github.com/apache/comdev/tree/main/mcp/apache-projects-mcp).
It is **read-only and unauthenticated** — it wraps the public
`projects.apache.org/json` feeds, so there is no LDAP/OAuth step.

**For ASF projects this MCP is a mandatory prerequisite.** The
manifest's
[`project_metadata`](<project-config>/project.md#project-metadata)
block declares `kind: apache-projects-mcp` with `mandatory: true`
as the ASF default, and the consuming skills gate on it in their
Step 0 / Step 1 pre-flight rather than degrading to hand-scraping
`committer.cgi` / `committee.html`. Install it from the **latest
`main`** of `apache/comdev` — the same checkout that hosts the
PonyMail MCP (both live under `mcp/` in that repo) — per
[`tools/apache-projects/tool.md`](../tools/apache-projects/tool.md).

**Without this connection:** `contributor-nomination` cannot verify
an Apache ID or cross-check committee affiliation and will stop with
a clear message asking you to register and reach the MCP first. A
non-ASF adopter with no `projects.apache.org` record sets
`project_metadata.mandatory: false` and supplies roster /
affiliation context by hand.
