<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Setup skill family](#setup-skill-family)
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

## Skills

| Skill | Purpose |
|---|---|
| [`setup-isolated-setup-install`](../../skills/setup-isolated-setup-install/SKILL.md) | First-time install of the secure agent setup. |
| [`setup-isolated-setup-verify`](../../skills/setup-isolated-setup-verify/SKILL.md) | Verify the secure setup landed correctly (static checks on settings.json, hooks, pinned versions). |
| [`setup-isolated-setup-doctor`](../../skills/setup-isolated-setup-doctor/SKILL.md) | Diagnose in-session sandbox friction (SSH agent, port bind, docker/podman socket) and map each fail to a catalog entry. |
| [`setup-isolated-setup-update`](../../skills/setup-isolated-setup-update/SKILL.md) | Surface drift between the installed setup and the framework's latest. |
| [`setup upgrade`](../../skills/setup/upgrade.md) | Pull the framework checkout to latest `origin/main`. |
| [`setup verify`](../../skills/setup/verify.md) | Verify the framework is integrated correctly into an adopter tracker. |
| [`setup-shared-config-sync`](../../skills/setup-shared-config-sync/SKILL.md) | Commit + push the user's shared Claude config to its sync repo. |

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
- [**`unadopt.md`**](unadopt.md) — counterpart to `install-recipes.md`:
  remove the framework artefacts the adopt flow installed. One
  path, full plan surfaced before any write.
- [**`sandbox-troubleshooting.md`**](sandbox-troubleshooting.md) —
  catalog of known sandbox-shaped failure modes (SSH agent /
  Yubikey unreachable, test port-bind blocked, docker/podman
  socket denied) with symptom → root cause → settings.json fix
  for each. The page to grep when a normal-looking operation
  fails in the sandbox in an unexpected way.

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

- [Top-level README — Adopting the framework](../../README.md#adopting-the-framework) — 3-step bootstrap.
- [`docs/prerequisites.md`](../prerequisites.md) — what each framework
  skill needs (Claude Code, Gmail MCP, GitHub auth, browser, etc.).
