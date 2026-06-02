<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Prerequisites for running framework skills](#prerequisites-for-running-framework-skills)
  - [Prerequisites for running the agent skills](#prerequisites-for-running-the-agent-skills)
    - [1. An agent that speaks the `SKILL.md` convention](#1-an-agent-that-speaks-the-skillmd-convention)
    - [2. Email connection (Gmail MCP, today)](#2-email-connection-gmail-mcp-today)
    - [3. GitHub connection (GitHub MCP / `gh` CLI)](#3-github-connection-github-mcp--gh-cli)
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

### 1. An agent that speaks the `SKILL.md` convention

[Claude Code](https://www.anthropic.com/claude-code) is the reference
implementation the skills are written against. Any agent that reads
the `.claude/skills/*/SKILL.md` files and follows their step-by-step
instructions should work; there is no hard dependency on Claude Code
specifically.

The agent runs against pre-disclosure CVE content (private mail
threads, draft advisories, in-flight tracker discussions). Run it
with the credential-isolation setup documented in
[`docs/setup/secure-agent-setup.md`](setup/secure-agent-setup.md) — a layered
defence built around Claude Code's filesystem sandbox, tool-level
permission rules, and a clean-env wrapper that strips credential-
shaped variables from the agent's environment. The required system
tools (`bubblewrap`, `socat`, `claude-code` itself) are pinned with
a 7-day upstream-release cooldown, mirroring the same convention the
framework uses for its `[tool.uv] exclude-newer` and Dependabot
configs.

### 2. Email connection (Gmail MCP, today)

The import, sync, and security-cve-allocate skills **read the security-list
mail thread** associated with each tracker and draft replies on that
thread. Today this goes through the
[Claude Gmail MCP](https://docs.anthropic.com/en/docs/build-with-claude/mcp)
connected to the personal Gmail account of a security-team member
who is subscribed to the adopting project's security list (see
`<project-config>/project.md → Mailing lists`). That is enough
access for the skills to see inbound reports and create drafts on
the right threads.

There is now an official ASF alternative for the **read** side:
[`apache/comdev`'s `mcp/ponymail-mcp/`](https://github.com/apache/comdev/tree/main/mcp/ponymail-mcp)
(under the ComDev PMC; originally authored by Rich Bowen, former ASF
board director and ComDev lead, with supply-chain hardening and
private-list restrictions layered in upstream) supports ASF LDAP
OAuth and can read private ASF lists. Individual triagers can wire
it up to read inbound `security@<project>.apache.org` threads
without subscribing a personal Gmail account — see
[`tools/ponymail/tool.md`](../tools/ponymail/tool.md) for the
setup. **Drafts remain Gmail-only** today (PonyMail MCP is
read-only and has no `create_draft` equivalent), so Gmail MCP is
still required for the reply path.

**For ASF projects the PonyMail MCP is a mandatory prerequisite,
not an opt-in backstop.** The reference adopter's manifest declares
`ponymail` with `mandatory: yes` (see
[`<project-config>/project.md → Mail sources`](<project-config>/project.md#mail-sources)),
so the mail-reading skills that run the Step 0 mail-source check
(`security-issue-import`, `security-issue-sync`) **refuse to start**
if it is not installed and reachable — Gmail keeps the `primary`
role for drafts, but PonyMail must also be present. (Skills that
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

### 3. GitHub connection (GitHub MCP / `gh` CLI)

Every skill reads and writes `<tracker>` issues. Claude Code ships
with the GitHub MCP by default, and the skills also use the `gh`
CLI directly for some calls. What the skills need:

- Authenticated `gh auth status` on the shell the agent runs in.
- Collaborator access (any permission level) on `<tracker>` — the
  security-team roster is maintained per-project; for the active
  project see
  [`<project-config>/release-trains.md`](<project-config>/release-trains.md#security-team-roster).
- For `security-issue-fix`: a fork of `<upstream>` on your GitHub
  account (the skill pushes a branch there before opening the PR
  via `gh pr create --web`).

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
