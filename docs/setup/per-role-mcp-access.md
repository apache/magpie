<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [How to enable a role-specific MCP server](#how-to-enable-a-role-specific-mcp-server)
  - [Overview](#overview)
  - [Prerequisites](#prerequisites)
  - [Step 1 — Register the MCP server in your Claude Code user settings](#step-1--register-the-mcp-server-in-your-claude-code-user-settings)
  - [Step 2 — Write a personal skill override enabling the MCP](#step-2--write-a-personal-skill-override-enabling-the-mcp)
  - [Example recipes](#example-recipes)
    - [Release manager — enable a governance Policy MCP for vote drafting](#release-manager--enable-a-governance-policy-mcp-for-vote-drafting)
    - [Security triage member — enable a private CVE database MCP](#security-triage-member--enable-a-private-cve-database-mcp)
    - [Infrastructure member — enable a deployment MCP for release promotion](#infrastructure-member--enable-a-deployment-mcp-for-release-promotion)
  - [When to graduate to shared project config](#when-to-graduate-to-shared-project-config)
  - [Hard rules](#hard-rules)
  - [Cross-references](#cross-references)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# How to enable a role-specific MCP server

## Overview

Some team members have access to an MCP server that others do not — a
governance Policy MCP a release manager uses, a private vulnerability
database a security triage member consults, or a deployment MCP only
infrastructure members can reach. Enabling that server in shared project
config would either fail for everyone who lacks credentials or expose a
tool that non-members should not have.

This recipe shows how to enable an MCP server **only for yourself**,
for **only the skills that need it**, without touching the committed
project config. The mechanism is the `.apache-magpie-local/` personal
override directory: a gitignored, per-developer layer that the framework
reads before shared config on every skill invocation.

The recipe has two steps:

1. **Register the MCP server** in your Claude Code user-scope settings
   so the agent can reach it in any session.
2. **Write a personal override file** for each skill that should use it,
   so the skill knows to call the MCP when you run it.

Other team members see no change. The shared `.apache-magpie-overrides/`
directory is untouched. The committed lock is untouched.

## Prerequisites

- The framework is adopted in the project repo and your install is up to
  date (`/magpie-setup verify`).
- You have credentials for the MCP server you want to add.
- Your `.apache-magpie-local/` directory exists (created by `/magpie-setup
  adopt`; see [`install-recipes.md`](install-recipes.md)) or create it:

  ```bash
  mkdir -p /path/to/project-repo/.apache-magpie-local
  ```

  On a repo that has not adopted Magpie, perform a whole-user install
  (see [`secure-agent-setup.md`](secure-agent-setup.md) § User-scope
  install), add `/.apache-magpie-local/` to the repo's `.gitignore`,
  then return here.

## Step 1 — Register the MCP server in your Claude Code user settings

Claude Code reads MCP server declarations from `~/.claude/settings.json`
(user scope) in every session. Add your server there so it is available
regardless of which project you are in. Edit or create
`~/.claude/settings.json`:

```json
{
  "mcpServers": {
    "<mcp-server-name>": {
      "command": "<path-to-mcp-binary>",
      "args": ["<arg1>", "<arg2>"],
      "env": {
        "<MCP_TOKEN_VAR>": "<your-token-or-credential>"
      }
    }
  }
}
```

Replace `<mcp-server-name>` with the name you will use in override files
(a short, memorable slug: `policy-mcp`, `vuln-db`, `infra-deploy`).
Replace the `command`, `args`, and `env` fields with what your specific
MCP server requires. Consult the server's own documentation for exact
values.

> **Credentials stay user-scope.** Never add credentials to the project's
> `.claude/settings.json` or to any committed file. User-scope settings
> (`~/.claude/settings.json`) live outside the repo and are never
> committed.

Verify the server is reachable by asking Claude Code to list your active
MCP servers:

```text
What MCP servers do you have available?
```

The response should include the slug you registered.

## Step 2 — Write a personal skill override enabling the MCP

For each framework skill you want to extend, create (or append to) a file
named `.apache-magpie-local/<skill-name>.md`. The skill reads this file
before applying framework defaults, so the override runs first on every
invocation.

The override is plain Markdown. Each modification is one `### Override N
— ...` section. Write what you want the skill to do with the MCP:

```markdown
### Override 1 — Use <mcp-server-name> for <specific purpose>

When performing <step or action>, call the `<mcp-server-name>` MCP server
to <what it provides>. Incorporate the result into <where it goes in the
skill's output> before proceeding. If the MCP server is unavailable,
continue without it and note that the <data type> is missing from the
report.
```

A few guidelines:

- **Name the fallback.** If the MCP is unavailable (credentials expired,
  server down), the skill should not fail hard — note the gap and
  continue.
- **Keep the scope narrow.** One override per use; one file per skill.
  Broad overrides that change many steps at once are harder to reason
  about on upgrade.
- **Phrase it as an instruction, not a constraint.** "Call X to fetch Y
  and include Z in the report" is clearer than "if X is available, maybe
  use Y."

## Example recipes

### Release manager — enable a governance Policy MCP for vote drafting

A release manager has access to a `policy-mcp` server that returns the
project's current release checklist, binding vote rules, and quorum
requirements. The `release-vote-draft` skill normally reads static
guidance from its own body; with the MCP it can fetch live policy.

**`~/.claude/settings.json`** (add alongside any existing `mcpServers`):
```json
"policy-mcp": {
  "command": "/usr/local/bin/policy-mcp-server",
  "args": ["--project", "<project>"],
  "env": { "POLICY_MCP_TOKEN": "<your-token>" }
}
```

**`.apache-magpie-local/release-vote-draft.md`**:
```markdown
### Override 1 — Fetch live release policy from the Policy MCP

Before drafting the vote email, call the `policy-mcp` MCP server with
the release version as the key. Use the returned checklist items to
populate the "What to check" section of the vote email, and use the
returned quorum rule to fill the pass/fail threshold line. If the MCP
is unavailable, fall back to the standard checklist in the skill body
and note that live policy was not fetched.
```

Other committers who run `/magpie-release-management:vote-draft` see no difference —
the skill proceeds with its built-in guidance.

---

### Security triage member — enable a private CVE database MCP

A security triage member has access to a `vuln-db` server that mirrors a
private CVE feed. The `security-issue-triage` skill can use it to cross-
reference a reported vulnerability against known CVEs during triage.

**`~/.claude/settings.json`**:
```json
"vuln-db": {
  "command": "/opt/security/vuln-db-mcp",
  "args": ["--format", "json"],
  "env": { "VULN_DB_API_KEY": "<your-api-key>" }
}
```

**`.apache-magpie-local/security-issue-triage.md`**:
```markdown
### Override 1 — Cross-reference with the private vulnerability database

During the CVSS estimation step, call the `vuln-db` MCP with the
reported component name and version range. If it returns matching CVEs,
include their IDs and CVSS scores in the triage report's "Related known
CVEs" field. If the MCP is unavailable or returns no matches, leave the
field blank and note that the cross-reference was not performed.
```

Other contributors who run `/magpie-security:issue-triage` get the
standard triage output; only your session fetches from `vuln-db`.

---

### Infrastructure member — enable a deployment MCP for release promotion

An infrastructure member has a `infra-deploy` MCP that can push a
release candidate to the distribution mirrors after the vote passes. The
`release-promote` skill normally stops at surfacing the promotion command
for the human to run; with the MCP the skill can confirm the mirror state
automatically.

**`~/.claude/settings.json`**:
```json
"infra-deploy": {
  "command": "/opt/infra/deploy-mcp",
  "args": [],
  "env": {
    "DEPLOY_MCP_HOST": "dist.example.org",
    "DEPLOY_MCP_TOKEN": "<your-infra-token>"
  }
}
```

**`.apache-magpie-local/release-promote.md`**:
```markdown
### Override 1 — Verify mirror propagation via the infra-deploy MCP

After the promotion command has been confirmed and run by the human,
call the `infra-deploy` MCP to poll `<dist-url>/<version>/` until the
artefacts appear or a 5-minute timeout elapses. Report the mirror status
(propagated / partial / timed-out) as the final line of the promotion
summary. If the MCP is unavailable, skip the poll and instruct the
release manager to verify propagation manually.
```

## When to graduate to shared project config

A personal override is the right tool when:

- Only members in a specific role have credentials for the MCP.
- The MCP is experimental and you are evaluating it before proposing it
  to the project.
- The MCP is a personal productivity tool with no shared policy
  implications.

Move to a committed `.apache-magpie-overrides/<skill>.md` (shared by all
contributors) when:

- All team members in the relevant role should have the MCP enabled, and
  they all have (or can get) the credentials.
- The project has decided the MCP integration is standard, not optional.

Move to a framework PR against `apache/magpie` when:

- The integration is useful to all Magpie adopters, not just your
  project (the
  [`setup-override-upstream`](../../skills/setup-override-upstream/SKILL.md)
  skill walks through this).

## Hard rules

These apply to personal override files in the same way as shared ones:

- **Never commit or push `.apache-magpie-local/`**. The directory is
  gitignored for this reason — it may carry credentials and personal
  paths.
- **Never weaken the safety, confidentiality, or privacy baseline.** An
  override that attempts to remove a confirmation step, skip a redaction
  pass, or bypass a sandbox rule is ignored and the conflict is surfaced.
- **Never store credentials in override files**. Reference an environment
  variable or a credential helper; do not embed tokens or passwords in
  plain Markdown.

## Cross-references

- [`agentic-overrides.md`](agentic-overrides.md) — the full override
  contract: lookup chain precedence, allowed shapes (skip / replace / add
  / pre-empt), and hard rules.
- [`setup-override-upstream`](../../skills/setup-override-upstream/SKILL.md)
  — promote a personal or project override into a framework PR once it
  proves its value.
- [`install-recipes.md`](install-recipes.md) — bootstrap Magpie in a
  project repo if you have not adopted yet.
- [`secure-agent-setup.md`](secure-agent-setup.md) — the full install
  walkthrough; covers `~/.claude/settings.json` sandbox allowlist entries
  that may be needed when adding a new MCP server.
