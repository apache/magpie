<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Setup skill family](#setup-skill-family)
  - [Install & first runs](#install--first-runs)
    - [Try these first](#try-these-first)
  - [Security mailing-list configuration](#security-mailing-list-configuration)
  - [Skills](#skills)
  - [Deep documentation](#deep-documentation)
  - [Typical lifecycle](#typical-lifecycle)
  - [Cross-references](#cross-references)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Setup skill family

> **Scope.** Works on any project, ASF or not — no
> Apache-Software-Foundation-specific assumptions baked in.

> **Two ways to install, and they are complementary.** A **marketplace
> install** puts the skills straight into your agent, per machine, with
> nothing in the repo — the recommended path, see
> [`marketplaces.md`](marketplaces.md). The **pinned snapshot install**,
> `/magpie-setup install`, sets up the gitignored snapshot, the skill
> symlinks, and the overrides scaffold in the repo so every contributor and CI
> job runs one committed version; reach for it when your agent has no
> marketplace, when you need the signed ASF source release, or when the
> project wants that pin. (`adopt` remains an accepted alias of `install`;
> `uninstall` / `unadopt` reverse it.)

The **setup** skill family is the prerequisite for running any
framework skill. It walks a new adopter (or a fresh dev machine on
an existing adopter) through the secure-agent install — pinned
system tools, the project-scope `.claude/settings.json` sandbox
block, the `claude-iso` clean-env wrapper, the user-scope hooks —
and through the ongoing housekeeping (verify install drift, pull
framework updates, sync shared user-scope config across machines).

Why a dedicated install skill family? The framework's other skills
run against pre-disclosure CVE content, private mailing lists, and
in-flight tracker discussions. Without the layered defence the
setup skills install (sandbox + permission rules + clean-env
wrapper), a misconfigured agent can leak credentials or
pre-disclosure content into the model provider's training data or
into a public PR. The setup family is what makes the rest of the
framework safe to use.

## Install & first runs

Install just this family — one plugin, 9 skills. Sandbox, clean environment, and the framework's own install/upgrade.

```text
/plugin marketplace add apache/magpie
/plugin install magpie-setup@apache-magpie
```

<!-- CAPTURE: assets/quickstart/README.md -->
![Claude Code showing the magpie-setup plugin installed and enabled](../../assets/quickstart/families/setup-install.png)

New to Magpie? The [quick start](../quick-start.md) covers the other agents,
the all-in-one alternative, and the secure-isolation setup to run next.

### Try these first

*Illustrative shapes, not real transcripts — your output will differ. Nothing
below sends, merges, or posts anything without you confirming it.*

**Put the agent in its sandbox.**

```text
> /magpie-setup:isolated-setup-install

Proposed changes (nothing applied yet):
  1. .claude/settings.json   sandbox.enabled: true, 14 deny rules
  2. ~/.claude/scripts/      3 hooks + status line
  3. ~/.zshrc                source agent-iso.sh
Apply 1-3? [y/N]
```

**Check it landed.**

```text
> /magpie-setup:isolated-setup-verify

  OK   sandbox.enabled           true
  OK   permissions.deny          14 rules
  WARN pinned tools              bubblewrap 0.11.1 (want 0.11.2)
  OK   status line               wired
```

**See what is wired up.**

```text
> /magpie-setup:status

  install method   marketplace (magpie-setup, magpie-pr-management)
  agent targets    .agents/skills, .claude/skills
  drift            none
```

## Security mailing-list configuration

Set `security_list` in your project manifest to your project's private
security mailing list. If it is missing, blank, or still a template TODO,
security workflows warn and resolve draft CC from
`security_inbox.foundation_security_address` through the normal
project/organization/default configuration chain. For ASF adopters the
organization supplies `security@apache.org`; other adopters use their own
organization's configured address. If neither address is configured,
drafting is blocked until configuration is corrected.

The selected address and fallback are shown before draft confirmation.
This does not configure subscriptions or redirect list searches to the
organization's mailbox. Configure mail reads separately; read-only work
can continue only when its own prerequisites are met. See the shared
[security draft CC resolution](../../tools/mail-source/contract.md#security-draft-cc-resolution)
for the complete rule.

## Skills

| Skill | Purpose |
|---|---|
| [`setup-isolated-setup-install`](../../skills/setup-isolated-setup-install/SKILL.md) | First-time install of the secure agent setup. |
| [`setup-isolated-setup-verify`](../../skills/setup-isolated-setup-verify/SKILL.md) | Verify the secure setup landed correctly (static checks on settings.json, hooks, pinned versions). |
| [`setup-isolated-setup-doctor`](../../skills/setup-isolated-setup-doctor/SKILL.md) | Diagnose in-session sandbox friction (SSH agent, port bind, docker/podman socket) and map each fail to a catalog entry. |
| [`setup-isolated-setup-update`](../../skills/setup-isolated-setup-update/SKILL.md) | Surface drift between the installed setup and the framework's latest. |
| [`setup`](../../skills/setup/SKILL.md) | Adopt and maintain the framework in a project repo through installation, verification, updates, overrides, and unadoption. |
| [`setup upgrade`](../../skills/setup/upgrade.md) | Pull the framework checkout to latest `origin/main`. |
| [`setup verify`](../../skills/setup/verify.md) | Verify the framework is integrated correctly into an adopter tracker. |
| [`setup-status`](../../skills/setup-status/SKILL.md) | Render a Markdown adoption dashboard (install pin, drift, wired agent targets, installed skill families, symlink health) and adjust the wiring in place. |
| [`setup-shared-config-sync`](../../skills/setup-shared-config-sync/SKILL.md) | Commit + push the user's shared Claude config to its sync repo. |
| [`setup-override-upstream`](../../skills/setup-override-upstream/SKILL.md) | Promote a local `.apache-magpie-overrides/<skill>.md` file into a PR against `apache/magpie`; prompts to remove the override once merged and upgraded. |
| [`setup-upstream-fix`](../../skills/setup-upstream-fix/SKILL.md) | Turn a framework bug or quirk hit mid-session into a fix PR against `apache/magpie`, after checking for an existing issue or PR that already covers it. |

## Deep documentation

- [**`secure-agent-setup.md`**](secure-agent-setup.md) — full
  install walkthrough. The authoritative reference the
  `setup-isolated-setup-install` skill steps through.
- [**`secure-agent-internals.md`**](secure-agent-internals.md) —
  how the layered defence works (sandbox + permission rules +
  clean-env wrapper) and why each layer exists.
- [**`install-recipes.md`**](install-recipes.md) — copy-pasteable
  shell recipes (svn-zip / git-tag / git-branch) for bootstrapping
  `setup` into a new adopter repo.
- [**`uninstall.md`**](uninstall.md) — counterpart to `install-recipes.md`:
  remove the framework artefacts the install flow installed. One
  path, full plan surfaced before any write.
- [**`sandbox-troubleshooting.md`**](sandbox-troubleshooting.md) —
  catalog of known sandbox-shaped failure modes (SSH agent /
  Yubikey unreachable, test port-bind blocked, docker/podman
  socket denied) with symptom → root cause → settings.json fix
  for each. The page to grep when a normal-looking operation
  fails in the sandbox in an unexpected way.
- [**`personal-use-unadopted-repo.md`**](personal-use-unadopted-repo.md) —
  recipe for using Magpie against a repo that has not adopted the
  framework: whole-user skill install, one `.gitignore` line,
  `.apache-magpie-local/` personal config, then run skills as if
  adopted. No changes to the target repo's committed files (beyond the
  optional `.gitignore` line) and no opt-in from teammates required.
- [**`per-role-mcp-access.md`**](per-role-mcp-access.md) — how to
  enable an MCP server for yourself only (e.g. a release manager
  enabling a Policy MCP, a security triage member enabling a
  private CVE database) without touching shared project config:
  register the server in user-scope Claude settings, then write a
  personal `.apache-magpie-local/<skill>.md` override.

## Typical lifecycle

```text
new dev machine
  ↓ setup-isolated-setup-install
isolated setup installed
  ↓ setup-isolated-setup-verify (any time, especially after Claude Code upgrade)
verified
  ↓ setup-isolated-setup-update (monthly / after Claude Code upgrade)
drift surfaced
  ↓ setup-upgrade (when framework releases something new)
framework checkout up to date
```

`setup-shared-config-sync` is orthogonal — it commits the user's
`~/.claude/CLAUDE.md` and other shared config to a private sync
repo so a fresh dev machine can pick it up (run after editing any
file under `~/.claude-config/`).

## Cross-references

- [Top-level README — Install](../../README.md#install) — 3-step bootstrap.
- [`docs/prerequisites.md`](../prerequisites.md) — what each framework
  skill needs (Claude Code, Gmail MCP, GitHub auth, browser, etc.).
