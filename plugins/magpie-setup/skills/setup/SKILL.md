---
# SPDX-License-Identifier: Apache-2.0
# https://www.apache.org/licenses/LICENSE-2.0
name: magpie-setup
family: setup
mode: Meta
description: >-
  Install Magpie, configure it for yourself, and adopt it for a repo.
  Installing touches only this machine; configuring writes gitignored
  local files; adopting commits a floor and the project's configuration
  for every contributor. Marketplace by default, pinned snapshot as
  fallback. Sub-actions: `config` (yourself, gitignored), `adopt` /
  `unadopt` (the repo, committed), `upgrade`, `worktree-init`, `verify`,
  `reconcile`, `skill-sources`, `override <skill>`, `uninstall`.
when_to_use: >-
  When the user wants Magpie installed, upgraded, verified, or checked
  for drift. Two routings matter: "configure magpie for me", or a
  skill's pre-flight asking for project configuration, goes to `config`
  — it writes gitignored files and needs nobody's permission. "Adopt
  magpie for this repo" or "commit a default set for the team" goes to
  `adopt` — it commits files for every contributor and is not an
  install.
argument-hint: "[install|config|adopt|unadopt|upgrade|worktree-init|verify|reconcile|override skill-name|uninstall]"
capability: capability:platform
surface_hash: sha256:74323d1713a39c3c
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

**The marketplace install is the default.** Magpie's skills go
straight into the agent the user already runs — one
`marketplace add`, then one `plugin install` per skill family —
with nothing committed to the repo, no snapshot, no lock files,
no symlinks. `setup` with no arguments proposes that path; every
other method is **optional**, for where a marketplace cannot
reach. Walk-through:
[`install.md` → Step M0b](install.md#step-m0b--pre-fill-from-the-committed-floor),
which reads any committed floor before walking through the install itself.
Per-agent reference:
[`docs/setup/marketplace.md`](../../../../docs/setup/marketplace.md).

## The install paths

| Path | What it sets up | Take it when |
|---|---|---|
| **`marketplace`** *(default)* | The agent's own plugin mechanism installs the skills, per machine. Nothing in the repo; updates arrive through the agent's plugin update. | The agent has a plugin / extension mechanism — Claude Code, Codex CLI, VS Code + Copilot, Gemini CLI, Cursor, `microsoft/apm`. The normal case. |
| **`marketplace` + an adopted floor** | The same per-machine install, plus a committed `.apache-magpie.lock` recording the project's minimum version and plugin set. Contributors are brought up to it by any skill's pre-flight. | The project wants a floor every contributor meets, without pinning anyone to one version. Written by [`adopt`](adopt.md). |
| **`svn-zip` / `git-tag` / `git-branch`** — the **pinned snapshot install** *(fallback)* | The gitignored snapshot at `<snapshot-dir>`, both lock files, gitignored `magpie-*` symlinks, the overrides scaffold, the post-checkout hook. | Only where a marketplace cannot reach: the agent has no plugin mechanism, the project needs the signed ASF source artefact, or it wants every contributor and CI job pinned to one committed framework version with drift detection. |
| **`local`** | Committed symlinks into the in-repo `skills/` source. No fetch, no snapshot. | The Apache Magpie framework checkout itself (see below). |

A project on one path can have contributors on the other, but
*one machine* takes one of them ([Golden rule 10](#golden-rules)).

**The rest of the pinned-snapshot machinery — what the snapshot is,
the three fetch methods, the symlink naming, the overrides scaffold —
is in [`snapshot-model.md`](snapshot-model.md). A marketplace install
needs none of it.**

## The two lock files

*(Pinned-snapshot path only — a marketplace install has no lock
files.)* The lock-file model splits **what the project pins to**
(committed `<committed-lock>`) from **what this machine actually
fetched** (gitignored `<local-lock>`); that split is the
foundation of drift detection and multi-installer support.
Trusted external skill sources use their own pair with identical
semantics. Formats, fields, and drift rules:
[`locks.md`](locks.md).

## Detail files in this directory

*Sub-actions* above maps every invocation to the file it loads. Three
more are reference the sub-actions consult rather than dispatch to:
[`locks.md`](locks.md) for the two lock files and the `reconciled:`
stamp, [`agents.md`](agents.md) for the agent-target registry and the
canonical-plus-relay model, and
[`snapshot-model.md`](snapshot-model.md) for the pinned-snapshot
machinery and the four golden rules that bind only on that path.
[`failure-modes.md`](failure-modes.md) is read when something has
already gone wrong.

## Golden rules

**Golden rule 1 — never modify the snapshot.** The
`<snapshot-dir>` is a build artefact, gitignored, and **read-
only** from an adopter's perspective. Every modification an
adopter wants must go into `.apache-magpie-overrides/` (where
it is *committed* and survives the next `upgrade`). The skill,
and any other framework skill consulting overrides at run-time,
**never** writes to `<snapshot-dir>`.

**Golden rule 5 — `.agents/skills/` is canonical; everything
else just relays into it.** Regardless of how an adopting
project previously organised its `.claude/skills/` or
`.github/skills/`, `adopt` always wires the framework the same
way: the canonical `magpie-*` links live in `.agents/skills/`,
and every other active target (`.claude`, `.github`, holdouts)
gets per-skill relay symlinks pointing back at the canonical
entries (`.claude/skills/magpie-<n>` →
`../../.agents/skills/magpie-<n>`). The adopter's own native
(non-`magpie-`) skills in those dirs are left untouched. See
[`agents.md`](agents.md).

**Golden rule 7 — agentic overrides are read at run-time.**
Every framework skill that supports overrides starts its run
by consulting **two** directories in precedence order (first
hit wins):

1. `.apache-magpie-local/<this-skill>.md` — personal,
   gitignored. Per-developer overrides that are never
   committed.
2. `.apache-magpie-overrides/<this-skill>.md` — committed,
   project-wide. Overrides shared with every contributor.

Both files are plain markdown the agent interprets — no
templating engine, no patch tool. The additive-only guardrail
applies to both: neither may weaken the framework's safety,
confidentiality, or privacy baseline. See
[`docs/setup/agentic-overrides.md`](../../../../docs/setup/agentic-overrides.md)
for the full contract including the lookup protocol.

**Golden rule 8 — family membership is declared in
frontmatter; two families are *always* installed, the rest
are opt-in.** Every framework skill declares its family in a
`family:` key in its `SKILL.md` frontmatter (e.g.
`family: repo-health`). The sub-actions read that key from the
snapshot to build the adopt/upgrade install choice and to wire
each family's symlinks — **family membership is never inferred
from the skill-name prefix**, because families such as
`repo-health` and `contributor-growth` deliberately span
several prefixes. The canonical family vocabulary is validated
by [`skill-and-tool-validator`](../../../../tools/skill-and-tool-validator/README.md)
(`ALLOWED_FAMILIES`) and mirrored adopter-facing in
[`README.md` → Skill families](../../../../README.md#skill-families).

Two families are wired up **unconditionally** on every adopt /
upgrade / worktree-init run and the user is never asked about them:
`setup` (every `family: setup` skill except the bootstrap `setup`
itself, which is copied rather than symlinked per Rule 6) and
`utilities` (the meta / discovery family). Both are read from the
frontmatter like any other family — do not maintain a list here.

**Golden rule 9 — reload `setup` in-flight after a
self-update.** When a sub-action changes or creates the
content of the committed `setup` skill (in practice:
`adopt` recovering an out-of-date bootstrap, or `upgrade`'s
overwrite-from-snapshot step), the agent **re-reads the
modified files of this skill before continuing** the rest of
the current run. Concretely: after the copy lands on disk,
re-load `SKILL.md` and the sub-action file you are
currently executing (and any helper file you have already
opened, such as `agents.md` or `overrides.md`), then
resume from the step after the overwrite. The reload runs as
the **first thing** that happens after the overwrite, before
any further reconciliation, symlink work, or doc updates.
The reason: the snapshot's skill version may have renamed
steps, added new sub-actions, or changed the symlink
contract; finishing the run against the *old* in-memory
copy of the skill would silently mis-apply the new
framework version the project just pinned to.

**Golden rule 10 — marketplace first; the snapshot install is a
fallback, not the default.** Rules 1–9 govern the pinned-snapshot
machinery; *which* path a run takes is decided here. Unless the
user passed an explicit `method:`, `install` proposes the
**marketplace** install with the exact commands for the agent in
front of it, and proposes the snapshot only for one of these
reasons — named out loud:

- the agent has no plugin / extension mechanism, or its
  marketplace install has already failed for this user;
- the project needs the **signed ASF source artefact**
  (`svn-zip`), not a marketplace clone of the repo;
- the project wants **one committed pin** — every contributor
  and CI job on one framework version, with drift detection;
- the repo is the framework checkout itself (`method:local`).

Never lay the snapshot on top of a working marketplace install
"to be safe": it loads a second copy of every skill — double the
always-on token cost, and `/magpie-<skill>` (snapshot) and
`/magpie-<family>:<skill>` (plugin) then resolve to two
*different* versions of the same skill. Where a repo genuinely
needs the pin, the snapshot **replaces** the marketplace install
on that machine — uninstall the plugins first.

Four rules bind only on the pinned-snapshot path — the lock files,
drift remediation, `.gitignore`, and copy-versus-symlink. They are in
[`snapshot-model.md`](snapshot-model.md) with the machinery they
govern. A marketplace install is not subject to them.

## Sub-actions

The skill dispatches by the first positional argument:

| Invocation | Loads | Purpose |
|---|---|---|
| `setup` (no args) | [`install.md`](install.md) | First-time install. Proposes the **marketplace** install first and falls back to the snapshot only per [Golden rule 10](#golden-rules) — the **main-checkout-only** restriction below applies to that fallback, not to the marketplace path. Idempotent — re-running on an already-installed repo behaves like `verify`. |
| `setup install` | [`install.md`](install.md) | Same as no-arg — explicit form. Main-checkout only. |
| `setup install method:marketplace` | [`install.md` → Step M0b](install.md#step-m0b--pre-fill-from-the-committed-floor) | The default path, named explicitly. Prints the agent's `marketplace add` + `plugin install` commands; writes nothing to the repo. Works in a worktree, and in a repo that has not adopted anything. |
| `setup install method:svn-zip\|git-tag\|git-branch` | [`install.md`](install.md) | The pinned snapshot install — the fallback path. Main-checkout only. |
| `setup config` | [`config.md`](config.md) | **Not an install, and not adoption.** Configure the installed skills for *you*, in gitignored `.apache-magpie-local/`. Works on any repo, adopted or not, with nobody's permission. Writes nothing committable and stages nothing. |
| `setup config <skill>` | [`config.md`](config.md) | The same, narrowed to one skill's required configuration. |
| `setup adopt` | [`adopt.md`](adopt.md) | **Not an install.** Commit the repo's recommended default plugin set and scaffold its overrides store, so every contributor arrives with them. Requires an explicit maintainer decision; stages, never commits. Claude Code only for the default set. |
| `setup upgrade` | [`upgrade.md`](upgrade.md) | Refresh snapshot per `<committed-lock>` + reconcile overrides + refresh symlinks. **Main-checkout only** — worktrees pick up upgrades automatically via the symlink installed by `worktree-init`. |
| `setup worktree-init` | [`worktree-init.md`](worktree-init.md) | **Worktree-only.** Symlink the worktree's `<snapshot-dir>` to the main checkout's so this worktree shares one framework state. No fetch, no lock files written; idempotent. |
| `setup verify` | [`verify.md`](verify.md) | Read-only health check + drift status report. Works in both main and worktrees. |
| `setup reconcile` | [`reconcile.md`](reconcile.md) | One-time project-wide reconciliation sweep — checks anchors + `requires_config` for every configured/overridden skill, proposes fixes item by item, writes the `reconciled:` stamp. Any install method. **Main-checkout only when the stamp target is the committed lock** (adopted); no restriction when it is the local file. |
| `setup skill-sources` (aka `skill-sources add <id>`) | [`skill-sources.md`](skill-sources.md) | Fetch/verify/pin/symlink skills from the trusted external sources the adopter listed in `<project-config>/skill-sources.md`. **Main-checkout only** — worktrees share the source snapshots via `worktree-init`. |
| `setup override <skill>` | [`overrides.md`](overrides.md) | Open / scaffold an override file. |
| `setup uninstall` | [`uninstall.md`](uninstall.md) | Reverse the install. Removes snapshot, the local lock, symlinks, hook, doc sections, and this skill itself. Leaves `.apache-magpie.lock` — that is `unadopt`. Preserves `.apache-magpie-overrides/` unless `--purge-overrides` is passed. **Main-checkout only.** |
| `setup unadopt` | [`adopt.md` → Unadopt](adopt.md#unadopt) | Remove the committed floor lock `.apache-magpie.lock` and the `.claude/settings.json` wiring derived from it. **Preserves `.apache-magpie-overrides/`** unless `--purge-overrides` is passed. Leaves every install — yours and everyone else's — untouched. |

**Main-checkout-only** is marked per row above. Those sub-actions
detect their context with `git rev-parse --git-dir` against
`--git-common-dir` and refuse to run in a worktree, pointing back at
the main checkout. Two different reasons sit behind that one marker:
`upgrade` and the snapshot fallback of `install`/`uninstall` are
pinned-snapshot operations, while `adopt`/`unadopt` write committed
files. A marketplace install touches no repo state and runs anywhere.

**`reconcile` is restricted only conditionally** — when the project is
adopted and its stamp therefore targets the committed lock. A
configured-but-unadopted project writes the gitignored
`.apache-magpie-local/reconciled.json` and has no worktree restriction
at all
([`reconcile.md` Step 0](reconcile.md#step-0--pre-flight)).

**`adopt` and `upgrade` always chain into `worktree-init`** on every
linked worktree, unconditionally — a no-op with no worktrees, and
idempotent where they already look wired, which is how broken symlinks
and newly always-on families get repaired. Nobody has to `cd` into each
worktree and re-run anything.

**A missing snapshot with a committed lock** turns any sub-action into
the recover-snapshot path: re-install per the lock, then continue.
## Inputs

| Flag | Effect |
|---|---|
| `from:<git-ref>` / `from:<version>` | Install or upgrade from a specific framework ref or version. Used during `install` (overrides the user prompt; on `method:marketplace` it pins the marketplace to that tag — `/plugin marketplace add apache/magpie@<version>`) and `upgrade` (overrides the committed lock for *this run only* — does NOT update the committed lock). |
| `method:<marketplace\|git-branch\|git-tag\|svn-zip\|local>` | Pick the install method explicitly. **Default during `install`: `marketplace`** — the other methods are the fallback for what a marketplace cannot cover ([Golden rule 10](#golden-rules)), so the agent proposes the marketplace path and names the fallback rather than opening with a three-way method prompt. **`marketplace`** writes nothing to the repo (see [`install.md` → Step M0b](install.md#step-m0b--pre-fill-from-the-committed-floor)). **`local`** is **framework-checkout only** — it self-adopts by linking the in-repo `skills/` source directly instead of fetching a snapshot (see [`install.md` → Local self-adoption](install.md#local-self-adoption-methodlocal)). |
| `agents:<list>` | Comma-separated **agent targets** to wire symlinks into ([`agents.md`](agents.md) registry ids: `universal`, `claude-code`, `github`, `windsurf`, `goose`, …). Default on `adopt`/`upgrade`: auto — the always-on neutral set (`universal` + `claude-code` + `github`) plus any other registry dir already present in the repo. When passed, **replaces** the auto-detected set for that run, except `universal` (`.agents/skills/`) which is always retained because it is the canonical home every other target relays into — dropping it would leave the relays dangling. |
| `skill-families:<list>` | Comma-separated **opt-in** families — the set to symlink on the snapshot path, the set of `magpie-<family>` plugins to install on the marketplace path — any of the opt-in families declared by a `family:` frontmatter key in the snapshot (today: `security`, `pr-management`, `issue`, `release-management`, `repo-health`, `pairing`, `mentoring`, `contributor-growth`). Default on `adopt`: prompt (see [`install.md` Step 5](install.md#step-5--pick-the-skill-families-and-mcp-servers)). Default on `upgrade`: read the families list from `<committed-lock>` / `<local-lock>`, **auto-include any opt-in family the framework has introduced since the lock was written** (recorded back into the lock), and **ensure every framework skill in the effective family set has a valid symlink** — create or repair missing / broken symlinks, not just add new ones. The flag never accepts the always-on families (`setup`, `utilities`); per [Golden rule 8](#golden-rules) those are wired up unconditionally on every run and there is no way to ask for them or opt out. |
| `--purge-overrides` | *(`unadopt` and `uninstall`)* Also `git rm -r` `.apache-magpie-overrides/`. Default on both: preserve. |
| `--no-overrides` | *(any framework skill)* Skip override-file lookup for this single invocation. Runs the skill against framework defaults; override files on disk are not read, modified, or deleted. The safety baseline (confidentiality, privacy, security) still applies. See [One-shot defaults run](../../../../docs/setup/agentic-overrides.md#one-shot-defaults-run). |
| `dry-run` | Show what the skill would do without writing anything. |

## What this skill is NOT for

- Not for installing the secure agent setup (sandbox, hooks,
  pinned tools). That is
  [`setup-isolated-setup-install`](../isolated-setup-install/SKILL.md).
- Not for upgrading framework tools installed on the host
  (`bubblewrap`, `socat`, `claude-code` itself). That is
  [`setup-isolated-setup-update`](../isolated-setup-update/SKILL.md).
- Not for syncing the user's `~/.claude-config` across
  machines. That is
  [`setup-shared-config-sync`](../shared-config-sync/SKILL.md).
- Not for committing framework changes. Framework PRs go
  against `apache/magpie` directly — the snapshot is
  read-only.

## Failure modes

What each sub-action does when the ground is not what it expected, and
which of them are recoverable:
[`failure-modes.md`](failure-modes.md).
