---
# SPDX-License-Identifier: Apache-2.0
# https://www.apache.org/licenses/LICENSE-2.0
name: setup
family: setup
mode: Meta
description: >-
  Install Magpie, configure it for yourself, or adopt it for a repo.
  Installing touches only this machine; configuring writes gitignored
  local files; adopting commits a floor and the project's configuration
  for every contributor. Marketplace by default, pinned snapshot as
  fallback.
when_to_use: >-
  When the user wants Magpie installed, upgraded, verified, uninstalled,
  or checked for drift. "Configure magpie for me", or a skill's
  pre-flight asking for project configuration, goes to `config`: it
  writes gitignored files and needs nobody's permission. "Adopt magpie
  for this repo" goes to `adopt`: it commits files for every
  contributor and is not an install.
argument-hint: "[install|config|adopt|unadopt|upgrade|worktree-init|verify|reconcile|override skill-name|uninstall]"
capability: capability:platform
surface_hash: sha256:df6116cc7828707c
license: Apache-2.0
---

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/legal/release-policy.html -->

<!-- Placeholder convention (see ../../AGENTS.md#placeholder-convention-used-in-skill-files):
     <project-config>           → per file, first hit wins: adopter's
                                  `.apache-magpie-local/` (gitignored, personal) then
                                  `.apache-magpie-overrides/` (committed, project-wide)
     <snapshot-dir>             → `.apache-magpie/` (gitignored snapshot of the framework)
     <committed-lock>           → `.apache-magpie.lock` (committed — project's pin)
     <local-lock>               → `.apache-magpie.local.lock` (gitignored — per-machine record)
     <upstream>                 → adopter's public source repo (the repo this skill is being run in)
     <framework-source>         → the apache-magpie source we download a snapshot from
                                   — one of: signed zip from ASF dist, git tag, git branch.
                                   See [`docs/setup/install-recipes.md`](../../../../docs/quick-start/other-install-methods.md). -->

# setup

**The marketplace install is the default.**
One `marketplace add`, then one `plugin install` per skill family, and nothing is written to the repo.
`setup` with no arguments proposes it; the other methods are fallbacks for where a marketplace cannot reach.
Walk-through: [`install.md` → Step M0b](install.md#step-m0b--pre-fill-from-the-committed-floor), which reads any committed floor first.
Per-agent reference: [`docs/setup/marketplace.md`](../../../../docs/setup/marketplace.md).

## The install paths

| Path | What it sets up | Take it when |
|---|---|---|
| **`marketplace`** *(default)* | The agent's own plugin mechanism installs the skills, per machine. Nothing in the repo; updates arrive through the agent's plugin update. | The agent has a plugin / extension mechanism — Claude Code, Codex CLI, VS Code + Copilot, Gemini CLI, Cursor, `microsoft/apm`. The normal case. |
| **`marketplace` + an adopted floor** | The same per-machine install, plus a committed `.apache-magpie.lock` recording the project's minimum version and plugin set. Contributors are brought up to it by any skill's pre-flight. | The project wants a floor every contributor meets, without pinning anyone to one version. Written by [`adopt`](adopt.md). |
| **`svn-zip` / `git-tag` / `git-branch`** — the **pinned snapshot install** *(fallback)* | The gitignored snapshot at `<snapshot-dir>`, both lock files, gitignored `magpie-*` symlinks, the overrides scaffold, the post-checkout hook. | Only where a marketplace cannot reach: the agent has no plugin mechanism, the project needs the signed ASF source artefact, or it wants every contributor and CI job pinned to one committed framework version with drift detection. |
| **`local`** | Committed symlinks into the in-repo `skills/` source. No fetch, no snapshot. | The Apache Magpie framework checkout itself (see below). |

A project can have contributors on either path, but one machine takes only one ([Golden rule 10](#golden-rules)).

The pinned-snapshot machinery — what the snapshot is, the fetch methods, symlink naming, the overrides scaffold — is in [`snapshot-model.md`](snapshot-model.md).
A marketplace install needs none of it.

## The two lock files

*(Pinned-snapshot path only — a marketplace install has no lock files.)*
The committed `<committed-lock>` records what the project pins to; the gitignored `<local-lock>` records what this machine fetched.
Drift detection and multi-installer support rest on that split.
Trusted external skill sources use their own pair with the same semantics.
Formats, fields, and drift rules: [`locks.md`](locks.md).

## Detail files in this directory

The [*Sub-actions*](#sub-actions) table maps every invocation to the file it loads.
Three more are reference files the sub-actions consult:
[`locks.md`](locks.md) (lock files and the `reconciled:` stamp),
[`agents.md`](agents.md) (agent-target registry, canonical-plus-relay model), and
[`snapshot-model.md`](snapshot-model.md) (pinned-snapshot machinery and the five golden rules that bind only there).
[`failure-modes.md`](failure-modes.md) is for when something has already gone wrong.

## Golden rules

**Golden rule 1 — never modify the snapshot.**
`<snapshot-dir>` is a gitignored build artefact and read-only to adopters.
Every change an adopter wants goes into `.apache-magpie-overrides/`, where it is committed and survives the next `upgrade`.
Neither this skill nor any framework skill reading overrides ever writes to `<snapshot-dir>`.

**Golden rule 5 — `.agents/skills/` is canonical; everything
else just relays into it.**
Whatever layout the project had before, `adopt` wires the framework the same way: the canonical `magpie-*` links live in `.agents/skills/`, and every other active target (`.claude`, `.github`, holdouts) gets per-skill relay symlinks back to them (`.claude/skills/magpie-<n>` → `../../.agents/skills/magpie-<n>`).
The adopter's own non-`magpie-` skills in those directories are left alone.
See [`agents.md`](agents.md).

**Golden rule 7 — agentic overrides are read at run-time** — lookup order and guardrail in [`overrides.md`](overrides.md).

**Golden rule 8 — family membership is declared in
frontmatter; two families are *always* installed, the rest
are opt-in.**
Every framework skill declares its family in a `family:` frontmatter key (e.g. `family: repo-health`).
The sub-actions read that key from the snapshot to build the adopt/upgrade install choice and to wire each family's symlinks.
**Never infer family from the skill-name prefix** — families such as `repo-health` and `contributor-growth` span several prefixes.
The family vocabulary is validated by [`skill-and-tool-validator`](../../../../tools/skill-and-tool-validator/README.md) (`ALLOWED_FAMILIES`) and listed for adopters in [`README.md` → Skill families](../../../../README.md#skill-families).

Two families are wired unconditionally on every adopt / upgrade / worktree-init run, without asking: `setup` (every `family: setup` skill except the bootstrap `setup` itself, which is copied per [Rule 6](snapshot-model.md#the-golden-rules-that-bind-only-here)) and `utilities`.
Both are read from frontmatter like any other family — do not keep a list here.

**Golden rule 10 — marketplace first; the snapshot install is a
fallback, not the default.**
Rules 1–9 govern the pinned-snapshot machinery; this rule decides which path a run takes.
Unless the user passed an explicit `method:`, `install` proposes the **marketplace** install, with the exact commands for the agent in front of it.
It proposes the snapshot only for one of these reasons, named out loud:

- the agent has no plugin / extension mechanism, or its marketplace install has already failed for this user;
- the project needs the **signed ASF source artefact** (`svn-zip`), not a marketplace clone of the repo;
- the project wants **one committed pin** — every contributor and CI job on one framework version, with drift detection;
- the repo is the framework checkout itself (`method:local`).

Never lay the snapshot on top of a working marketplace install "to be safe".
It loads a second copy of every skill, doubling the always-on token cost, and `/magpie-<skill>` (snapshot) and `/magpie-<family>:<skill>` (plugin) then resolve to two *different* versions of the same skill.
Where a repo genuinely needs the pin, the snapshot **replaces** the marketplace install on that machine — uninstall the plugins first.

Five rules bind only on the pinned-snapshot path — the lock files, drift remediation, `.gitignore`, copy-versus-symlink, and reloading `setup` after a self-update (rule 9).
They are in [`snapshot-model.md`](snapshot-model.md) with the machinery they govern; a marketplace install is not subject to them.

## Sub-actions

The skill dispatches by the first positional argument:

| Invocation | Loads | Purpose |
|---|---|---|
| `setup` (no args) | [`install.md`](install.md) | First-time install. Proposes the **marketplace** install first; falls back to the snapshot only per [Golden rule 10](#golden-rules), and only that fallback is **main-checkout only**. Idempotent — on an already-installed repo it behaves like `verify`. |
| `setup install` | [`install.md`](install.md) | Same as no-arg — explicit form. Main-checkout only. |
| `setup install method:marketplace` | [`install.md` → Step M0b](install.md#step-m0b--pre-fill-from-the-committed-floor) | The default path, named explicitly. Prints the agent's `marketplace add` + `plugin install` commands and writes nothing to the repo. Works in a worktree, and in a repo that has adopted nothing. |
| `setup install method:svn-zip\|git-tag\|git-branch` | [`install.md`](install.md) | The pinned snapshot install — the fallback path. Main-checkout only. |
| `setup config` | [`config.md`](config.md) | **Not an install, and not adoption.** Configure the installed skills for *you*, in gitignored `.apache-magpie-local/`. Works on any repo, adopted or not, with nobody's permission. Writes nothing committable and stages nothing. |
| `setup config <skill>` | [`config.md`](config.md) | The same, narrowed to one skill's required configuration. |
| `setup config adversarial-review` | [`config.md`](config.md#step-3c--adversarial-reviewers-optional) | Detect the installed model CLIs and configure them as adversarial reviewers. |
| `setup adopt` | [`adopt.md`](adopt.md) | **Not an install.** Commit the repo's recommended default plugin set and scaffold its overrides store, so every contributor arrives with them. Needs an explicit maintainer decision; stages, never commits. Default set is Claude Code only. |
| `setup upgrade` | [`upgrade.md`](upgrade.md) | Refresh the snapshot per `<committed-lock>`, reconcile overrides, refresh symlinks. **Main-checkout only** — worktrees pick it up through the symlink `worktree-init` installs. |
| `setup worktree-init` | [`worktree-init.md`](worktree-init.md) | **Worktree-only.** Symlink the worktree's `<snapshot-dir>` to the main checkout's so both share one framework state. No fetch, no lock files written; idempotent. |
| `setup verify` | [`verify.md`](verify.md) | Read-only health check and drift report. Works in the main checkout and in worktrees. |
| `setup reconcile` | [`reconcile.md`](reconcile.md) | One-time project-wide sweep: checks anchors and `requires_config` for every configured or overridden skill, proposes fixes one by one, writes the `reconciled:` stamp. Any install method. **Main-checkout only when the stamp goes to the committed lock** (adopted); unrestricted when it goes to the local file. |
| `setup skill-sources` (aka `skill-sources add <id>`) | [`skill-sources.md`](skill-sources.md) | Fetch, verify, pin and symlink skills from the trusted sources listed in `<project-config>/skill-sources.md`. **Main-checkout only** — worktrees share the source snapshots via `worktree-init`. |
| `setup override <skill>` | [`overrides.md`](overrides.md) | Open or scaffold an override file. |
| `setup uninstall` | [`uninstall.md`](uninstall.md) | Reverse the install: remove the snapshot, the local lock, symlinks, hook, doc sections, and this skill. Leaves `.apache-magpie.lock` — that is `unadopt`. Keeps `.apache-magpie-overrides/` unless `--purge-overrides` is passed. **Main-checkout only.** |
| `setup unadopt` | [`adopt.md` → Unadopt](adopt.md#unadopt) | Remove the committed floor lock `.apache-magpie.lock` and the `.claude/settings.json` wiring derived from it. **Keeps `.apache-magpie-overrides/`** unless `--purge-overrides` is passed. Leaves every install — yours and everyone else's — untouched. |

**Main-checkout-only** is marked per row above.
Those sub-actions compare `git rev-parse --git-dir` with `--git-common-dir` and, in a worktree, refuse and point back at the main checkout.
The marker has two reasons: `upgrade` and the snapshot fallback of `install`/`uninstall` are pinned-snapshot operations, while `adopt`/`unadopt` write committed files.
A marketplace install touches no repo state and runs anywhere.

**`reconcile` is restricted only when the project is adopted**, because its stamp then goes to the committed lock.
A configured-but-unadopted project writes the gitignored `.apache-magpie-local/reconciled.json` and has no worktree restriction ([`reconcile.md` Step 0](reconcile.md#step-0--pre-flight)).

**`adopt` and `upgrade` always chain into `worktree-init`** on every linked worktree.
It is a no-op with no worktrees and idempotent where they already look wired, which is how broken symlinks and newly always-on families get repaired — nobody has to re-run anything per worktree.

**A missing snapshot with a committed lock** turns any sub-action into the recover-snapshot path: re-install per the lock, then continue.

### Unrecognised sub-action

When the first positional argument matches no sub-action in the table above and is not a flag from [*Inputs*](#inputs), **do not guess, and do not fall back to `install`**.
The usual cause is a typo (`upgrede`, `reconcie`), and quietly mapping it to the nearest name runs something the user never named — `upgrade`, `reconcile` and `adopt` stage committed files.

Print this instead, using the invocation name this install answers to (`/magpie-setup:setup` on a marketplace install, `/magpie-setup` on the pinned snapshot):

```text
Unknown setup sub-action: `upgrede`.
Did you mean `upgrade`?  →  /magpie-setup:setup upgrade

Sub-actions: install, config, adopt, upgrade, worktree-init, verify,
reconcile, skill-sources, override, uninstall, unadopt
```

- Suggest only a **close** match: an edit distance of one or two, or a prefix of the name.
  When several qualify (`un` → `uninstall`, `unadopt`), name them all.
  When none is close, print only the list.
- Then **stop and wait**. Run a suggested sub-action only once the user confirms it — a plain *"yes"* to a single suggestion is enough — never on your own because it was the only near match.

## Inputs

| Flag | Effect |
|---|---|
| `from:<git-ref>` / `from:<version>` | Install or upgrade from a specific framework ref or version. On `install` it replaces the prompt; with `method:marketplace` it pins the marketplace to that tag (`/plugin marketplace add apache/magpie@<version>`). On `upgrade` it overrides the committed lock for *this run only* and does NOT update it. |
| `method:<marketplace\|git-branch\|git-tag\|svn-zip\|local>` | Pick the install method explicitly. **Default on `install`: `marketplace`.** The others are fallbacks ([Golden rule 10](#golden-rules)), so the agent proposes the marketplace path and names the fallback instead of opening with a three-way prompt. **`marketplace`** writes nothing to the repo ([`install.md` → Step M0b](install.md#step-m0b--pre-fill-from-the-committed-floor)). **`local`** is **framework-checkout only**: it self-adopts by linking the in-repo `skills/` source instead of fetching a snapshot ([`install.md` → Local self-adoption](install.md#local-self-adoption-methodlocal)). |
| `agents:<list>` | Comma-separated **agent targets** to wire symlinks into ([`agents.md`](agents.md) registry ids: `universal`, `claude-code`, `github`, `windsurf`, `goose`, …). Default on `adopt`/`upgrade`: the always-on neutral set (`universal` + `claude-code` + `github`) plus any other registry dir already in the repo. When passed, it **replaces** the detected set for that run — except `universal` (`.agents/skills/`), which is always kept because every other target relays into it. |
| `skill-families:<list>` | Comma-separated **opt-in** families: what to symlink on the snapshot path, which `magpie-<family>` plugins to install on the marketplace path. Any opt-in family declared by a `family:` key in the snapshot (today: `security`, `pr-management`, `issue`, `release-management`, `repo-health`, `pairing`, `mentoring`, `contributor-growth`). Default on `adopt`: prompt ([`install.md` Step 5](install.md#step-5--pick-the-skill-families-and-mcp-servers)). Default on `upgrade`: the families in `<committed-lock>` / `<local-lock>`, **plus any opt-in family added since the lock was written** (recorded back into the lock), and **every framework skill in that set gets a valid symlink** — missing or broken ones are created or repaired. Never accepts the always-on families (`setup`, `utilities`); per [Golden rule 8](#golden-rules) they are wired on every run and cannot be requested or opted out of. |
| `--purge-overrides` | *(`unadopt` and `uninstall`)* Also `git rm -r` `.apache-magpie-overrides/`. Default on both: keep. |
| `--no-overrides` | *(any framework skill)* Skip override lookup for this one invocation and run on framework defaults. Override files on disk are not read, changed, or deleted. The safety baseline (confidentiality, privacy, security) still applies. See [One-shot defaults run](../../../../docs/setup/agentic-overrides.md#one-shot-defaults-run). |
| `dry-run` | Show what the skill would do without writing anything. |

## What this skill is NOT for

- The secure agent setup (sandbox, hooks, pinned tools): [`setup-isolated-setup-install`](../isolated-setup-install/SKILL.md).
- Upgrading host tools (`bubblewrap`, `socat`, `claude-code` itself): [`setup-isolated-setup-update`](../isolated-setup-update/SKILL.md).
- Syncing `~/.claude-config` across machines: [`setup-shared-config-sync`](../shared-config-sync/SKILL.md).
- Committing framework changes. Those go as PRs against `apache/magpie`; the snapshot is read-only.

## Failure modes

What each sub-action does when the ground is not what it expected, and which cases are recoverable: [`failure-modes.md`](failure-modes.md).
