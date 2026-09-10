---
# SPDX-License-Identifier: Apache-2.0
# https://www.apache.org/licenses/LICENSE-2.0
name: magpie-setup
family: setup
mode: Meta
description: |
  Adopt and maintain the apache-magpie framework in a project.
  Installs from the agent's marketplace by default; the pinned
  snapshot install is the fallback where no marketplace reaches.
  Sub-actions:
    `setup` - first-time install, marketplace-first; snapshot fallback is main-checkout only. `adopt` is an alias.
    `setup upgrade` - refresh the gitignored snapshot per the committed lock (main-checkout only)
    `setup worktree-init` - symlink a worktree's snapshot to the main's
    `setup verify` - health check + drift detection
    `setup skill-sources` - fetch/pin/symlink skills from trusted external sources listed in the adopter trust list (main-checkout only)
    `setup override <skill>` - open or scaffold an agentic override in `.apache-magpie-overrides/`
    `setup uninstall` - reverse the install (snapshot, locks, symlinks, hook, doc sections); preserves `.apache-magpie-overrides/` by default (main-checkout only). `unadopt` is an alias.
when_to_use: |
  Invoke when the user says "adopt apache-magpie", "adopt
  apache/magpie", "set up magpie in this repo",
  "install magpie",
  "follow .claude/skills/magpie-setup", or follows the
  framework's README install instructions. Also for periodic
  maintenance: "upgrade magpie", "verify magpie setup",
  "check magpie drift", "the snapshot is stale".
argument-hint: "[install|upgrade|worktree-init|verify|override skill-name|uninstall]"
capability: capability:platform
license: Apache-2.0
---

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/legal/release-policy.html -->

<!-- Placeholder convention (see ../../AGENTS.md#placeholder-convention-used-in-skill-files):
     <project-config>           → adopter's `.apache-magpie-overrides/` directory
     <snapshot-dir>             → `.apache-magpie/` (gitignored snapshot of the framework)
     <committed-lock>           → `.apache-magpie.lock` (committed — project's pin)
     <local-lock>               → `.apache-magpie.local.lock` (gitignored — per-machine record)
     <upstream>                 → adopter's public source repo (the repo this skill is being run in)
     <framework-source>         → the apache-magpie source we download a snapshot from
                                   — one of: signed zip from ASF dist, git tag, git branch.
                                   See [`docs/setup/install-recipes.md`](../../docs/setup/install-recipes.md). -->

# setup

**The marketplace install is the default.** Magpie's skills go
straight into the agent the user already runs — one
`marketplace add`, then one `plugin install` per skill family —
with nothing committed to the repo, no snapshot, no lock files,
no symlinks. `setup` with no arguments proposes that path; every
other method is **optional**, for where a marketplace cannot
reach. Walk-through:
[`install.md` → Marketplace install](install.md#marketplace-install--the-default-path).
Per-agent reference:
[`docs/setup/marketplaces.md`](../../docs/setup/marketplaces.md).

## The install paths

| Path | What it sets up | Take it when |
|---|---|---|
| **`marketplace`** *(default)* | The agent's own plugin mechanism installs the skills, per machine. Nothing in the repo; updates arrive through the agent's plugin update. | The agent has a plugin / extension mechanism — Claude Code, Codex CLI, VS Code + Copilot, Gemini CLI, Cursor, `microsoft/apm`. The normal case. |
| **`svn-zip` / `git-tag` / `git-branch`** — the **pinned snapshot install** *(fallback)* | The gitignored snapshot at `<snapshot-dir>`, both lock files, gitignored `magpie-*` symlinks, the overrides scaffold, the post-checkout hook. | Only where a marketplace cannot reach: the agent has no plugin mechanism, the project needs the signed ASF source artefact, or it wants every contributor and CI job pinned to one committed framework version with drift detection. |
| **`local`** | Committed symlinks into the in-repo `skills/` source. No fetch, no snapshot. | The Apache Magpie framework checkout itself (see below). |

A project on one path can have contributors on the other, but
*one machine* takes one of them ([Golden rule 10](#golden-rules)).

**Everything below describes the pinned-snapshot machinery — a
marketplace install needs none of it.** On that path this skill
is **the only framework artefact an adopter project commits**;
every other apache-magpie skill (security, pr-management, issue)
is a gitignored symlink into the gitignored snapshot at
`<snapshot-dir>` that this skill manages, under a model of
**snapshot + agentic overrides + drift-aware updates** (not
submodule, not vendored copy):

- The framework is downloaded into `<snapshot-dir>` and
  **gitignored** in the adopter repo. The snapshot is a build
  artefact, not source.
- Three snapshot fetch methods are supported (see
  [`docs/setup/install-recipes.md`](../../docs/setup/install-recipes.md)
  for verbatim copy-pasteable recipes):
  - **svn-zip** — released, signed zip from ASF distribution
    (recommended for production once releases ship).
  - **git-tag** — pinned to a specific git tag.
  - **git-branch** — tracks a branch tip (default: `main`,
    the WIP path).
- **Two lock files** record the framework version. The
  committed one declares what the project pins to; the local
  one records what each machine actually fetched. Drift
  between them is surfaced and remediated by
  `setup upgrade`.
- Symlinks make the framework's skills callable as if they
  lived in the adopter repo. **Each symlink is named
  `magpie-<framework-skill>`** — every framework skill is
  installed under a `magpie-` prefix so it is namespaced and
  never collides with the adopter's own skills (e.g. the
  snapshot's `skills/pr-management-triage/` becomes
  `magpie-pr-management-triage`, invoked as
  `/magpie-pr-management-triage`). **`.agents/skills/` is the
  one canonical home**: its `magpie-*` entries link into
  `<snapshot-dir>/skills/<framework-skill>/`. Every other agent
  target (`.claude/skills/`, `.github/skills/`, …) gets a thin
  per-skill **relay** symlink that points back at the canonical
  entry (`.claude/skills/magpie-<n>` →
  `../../.agents/skills/magpie-<n>`) — no matter what layout the
  adopting project previously used (see
  [`agents.md`](agents.md)). The symlinks are
  **gitignored** because their targets disappear on a fresh
  clone before `setup` runs.
- Adopter-specific modifications to framework workflows live as
  agent-readable instructions under
  `.apache-magpie-overrides/<skill-name>.md` (committed). They
  invalidate or change steps the framework's skill would
  otherwise run. See
  [`overrides.md`](overrides.md) for the contract and
  [`docs/setup/agentic-overrides.md`](../../docs/setup/agentic-overrides.md)
  for the design rationale.

**Local self-adoption (the framework checkout only).** The one
repo that cannot be adopted via the snapshot mechanism is the
Apache Magpie framework checkout itself — a remote snapshot of the
framework into itself would be circular. Instead it **self-adopts**
with `method:local`: each canonical `magpie-<skill>` in
`.agents/skills/` is a **committed** symlink into the in-repo
`../../skills/<skill>/` source, and every other active agent
target ([`agents.md`](agents.md)) — `.claude/skills/` (Claude
Code), `.github/skills/` (GitHub's skill loader), and any present
holdout — gets a committed **relay** symlink
(`magpie-<skill>` → `../../.agents/skills/magpie-<skill>`) — with
no snapshot, no remote fetch, and no copy. This makes
the framework's own skills callable while developing the framework,
and every contributor gets them active on a fresh clone with no
setup step. `adopt` detects the framework checkout structurally and
routes there automatically (see
[`install.md` → Local self-adoption](install.md#local-self-adoption-methodlocal)).

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

| File | Purpose |
|---|---|
| [`install.md`](install.md) | First-time install walk-through — recognise existing-snapshot vs needs-bootstrap, write the two lock files, ask the user which skill families and MCP servers to install, create the gitignored symlinks, scaffold `.apache-magpie-overrides/`, install the post-checkout hook, update project docs. The default sub-action. |
| [`upgrade.md`](upgrade.md) | Refresh the gitignored snapshot per the committed lock, reconcile any agentic overrides + symlinks against the new framework structure, surface conflicts. Drives the on-drift remediation flow. |
| [`verify.md`](verify.md) | Read-only health check — snapshot present + intact, both lock files in sync, symlinks point at live targets, `.gitignore` correct, `.apache-magpie-overrides/` exists, drift status (committed vs local), the `setup` skill itself is current. |
| [`skill-sources.md`](skill-sources.md) | Fetch/verify skills from trusted external sources listed in `<project-config>/skill-sources.md`, pin them in the committed `.apache-magpie.sources.lock`, and symlink the provided skills in exactly like framework skills. The runnable half of [trusted external skill sources](../../docs/skill-sources/README.md); the install gate is the adopter trust list. |
| [`locks.md`](locks.md) | The two lock files of the pinned-snapshot path — `<committed-lock>` (the project's pin) and `<local-lock>` (this machine's fetch), their formats, and the per-source pair used by trusted external sources. |
| [`agents.md`](agents.md) | The agent-target registry — *which* directories framework-skill symlinks land in across vendors, and the **canonical-plus-relay** model: `.agents/skills/` is the one canonical home (links into the snapshot/source); every other target (`claude-code`, `github`, holdout natives like Windsurf / Goose) gets a per-skill relay symlink into `.agents/skills/`. Defines active-target selection, SKILL.md format portability, and the Claude-Code-only layer (sandbox/hooks). The source of truth every sub-action consults for the target set. |
| [`overrides.md`](overrides.md) | Agentic-override file management — open / scaffold an override for a framework skill, list existing overrides, help reconcile when the framework changes the underlying skill's structure on upgrade. |
| [`uninstall.md`](uninstall.md) | Reverse the adoption — remove snapshot, locks, symlinks, post-checkout hook, `.gitignore` entries, the adoption sections in `README.md` / `AGENTS.md` / `CONTRIBUTING.md`, and the committed `setup` skill itself. Preserves `.apache-magpie-overrides/` by default; `--purge-overrides` removes it too. Surfaces the full removal plan before any write. |

## Golden rules

**Golden rule 1 — never modify the snapshot.** The
`<snapshot-dir>` is a build artefact, gitignored, and **read-
only** from an adopter's perspective. Every modification an
adopter wants must go into `.apache-magpie-overrides/` (where
it is *committed* and survives the next `upgrade`). The skill,
and any other framework skill consulting overrides at run-time,
**never** writes to `<snapshot-dir>`.

**Golden rule 2 — `<committed-lock>` is the project's pin;
`<local-lock>` is per-machine truth.** They serve different
purposes and live in different places:

- `<committed-lock>` declares what version the *project* uses.
  Edited by the adopter who runs `setup install` first
  (or who later runs `setup upgrade` and accepts the
  new pin). Bumping it is a deliberate project-level action;
  the bump shows up in the `git diff` of the PR that proposed
  it.
- `<local-lock>` records what *this machine* installed. Updated
  silently by `setup install` and `setup
  upgrade`. Per-developer, per-checkout, per-worktree.

**Golden rule 3 — drift surfaces, drift gets remediated.**
Every framework skill (and `setup verify`) checks
`<committed-lock>` vs `<local-lock>` at the top of its run.
On mismatch the skill surfaces the gap and proposes
`setup upgrade`. The user accepts or defers; if they
accept, `upgrade`:

1. Deletes `<snapshot-dir>` outright.
2. Re-installs per the *committed* lock (the new version the
   project chose).
3. Refreshes the gitignored framework-skill symlinks — adds
   any new framework skills the user's family pick covers,
   removes any framework skills that were renamed away or
   removed.
4. Reconciles agentic overrides against the new framework
   structure (surfaces conflicts; never auto-rewrites).
5. Updates `<local-lock>` to the new fetch.

**Golden rule 4 — `.gitignore` keeps the adopter repo clean.**
Gitignored in the adopter repo:

- `<snapshot-dir>` (the entire framework snapshot — gigabytes
  potentially).
- `<local-lock>` (per-machine state).
- `.apache-magpie-local/` (personal, per-developer override
  directory — see Golden rule 7).
- The `magpie-*` symlinks `setup adopt` creates in every active
  target dir — the canonical ones in `.agents/skills/` (they
  target the gitignored snapshot) and the relays in
  `.claude/skills/` / `.github/skills/` / holdouts (they target
  the canonical entries) — both would dangle in a fresh clone.
  The one exception un-ignored in each dir is `magpie-setup`.
- `.apache-magpie-sources/` (the gitignored fetch of every
  trusted external skill source) and
  `.apache-magpie.sources.local.lock` (per-machine source-fetch
  fingerprint), when the adopter trusts any source. See
  [`skill-sources.md`](skill-sources.md).

**Committed**: this skill (`setup`, as the canonical
`.agents/skills/magpie-setup/` plus its relays), the
`<committed-lock>`, the **`.apache-magpie.sources.lock`**
per-source pins (the project's committed vouch for each trusted
source), the `.apache-magpie-overrides/` directory, the
`.gitignore` entries themselves, any project-doc updates the
`adopt` sub-action makes.

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

**Golden rule 6 — copy this skill, symlink the rest; all under
the `magpie-` prefix.** This skill (source `skills/setup/`) is
the **only** framework skill that gets **copied** into an
adopter repo — committed as the canonical
`.agents/skills/magpie-setup/`, with committed relay symlinks to
it from `.claude/skills/magpie-setup` and
`.github/skills/magpie-setup`. All other framework skills are
**symlinked** (canonical link into the gitignored snapshot, plus
relays), each named `magpie-<framework-skill>`
(e.g. `magpie-security-issue-import` → `<snapshot-dir>/skills/security-issue-import/`).
The `magpie-` prefix namespaces every framework skill so it
never collides with an adopter's own skills. Mixing copy and
symlink — copying a security skill, for instance — creates a
maintenance hazard: copies drift from the framework's source-
of-truth, and the drift-detection mechanism (which assumes
the framework version is the one in `<snapshot-dir>`)
silently mis-applies.

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
[`docs/setup/agentic-overrides.md`](../../docs/setup/agentic-overrides.md)
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
by [`skill-and-tool-validator`](../../tools/skill-and-tool-validator/README.md)
(`ALLOWED_FAMILIES`) and mirrored adopter-facing in
[`README.md` → Skill families](../../README.md#skill-families).

Two families are wired up **unconditionally** on every adopt /
upgrade / worktree-init run and the user is **never asked**
about them:

- **`setup`** — every skill with `family: setup` *except* the
  bootstrap `setup` itself (which is copied as `magpie-setup`
  per Rule 6, not symlinked): `setup-isolated-setup-install`,
  `setup-isolated-setup-update`, `setup-isolated-setup-verify`,
  `setup-isolated-setup-doctor`, `setup-override-upstream`,
  `setup-shared-config-sync`, `setup-status`,
  `setup-upstream-fix`, plus any new `family: setup` skill the
  framework grows — each symlinked as `magpie-setup-*`.
- **`utilities`** — the meta / discovery family; skills with
  `family: utilities`: `list-skills`, `write-skill`,
  `optimize-skill`, `skill-reconciler`. These are framework
  self-authoring and discovery tools every adopter gets so the
  framework can grow them without re-prompting.

These two always-on families (`ALWAYS_ON_FAMILIES` in the
validator) are not exposed in the `skill-families:` prompt and
not stored as user-selectable in the lock files; every
sub-action that wires symlinks always covers them **in addition
to** the user's opt-in family picks. Dropping them is *not* a
supported configuration — the secure-setup, discovery, and
skill-authoring flows the framework ships depend on those
skills being callable.

Every **other** family is **opt-in** — offered in the Step 5
prompt and recorded in the lock files. Today those are:
`security`, `pr-management`, `issue`, `release-management`,
`repo-health`, `pairing`, `mentoring`, `contributor-growth`.
The set is computed from the `family:` keys present in the
snapshot minus the always-on families, so a new opt-in family
appears in the prompt automatically the run after it ships.

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

## Sub-actions

The skill dispatches by the first positional argument:

| Invocation | Loads | Purpose |
|---|---|---|
| `setup` (no args) | [`install.md`](install.md) | First-time install. Proposes the **marketplace** install first and falls back to the snapshot only per [Golden rule 10](#golden-rules) — the **main-checkout-only** restriction below applies to that fallback, not to the marketplace path. Idempotent — re-running on an already-installed repo behaves like `verify`. |
| `setup install` | [`install.md`](install.md) | Same as no-arg — explicit form. Main-checkout only. |
| `setup install method:marketplace` | [`install.md` → Marketplace install](install.md#marketplace-install--the-default-path) | The default path, named explicitly. Prints the agent's `marketplace add` + `plugin install` commands; writes nothing to the repo. Works in a worktree, and in a repo that has not adopted anything. |
| `setup install method:svn-zip\|git-tag\|git-branch` | [`install.md`](install.md) | The pinned snapshot install — the fallback path. Main-checkout only. |
| `setup adopt` | [`install.md`](install.md) | Alias of `install`. |
| `setup upgrade` | [`upgrade.md`](upgrade.md) | Refresh snapshot per `<committed-lock>` + reconcile overrides + refresh symlinks. **Main-checkout only** — worktrees pick up upgrades automatically via the symlink installed by `worktree-init`. |
| `setup worktree-init` | [`worktree-init.md`](worktree-init.md) | **Worktree-only.** Symlink the worktree's `<snapshot-dir>` to the main checkout's so this worktree shares one framework state. No fetch, no lock files written; idempotent. |
| `setup verify` | [`verify.md`](verify.md) | Read-only health check + drift status report. Works in both main and worktrees. |
| `setup skill-sources` (aka `skill-sources add <id>`) | [`skill-sources.md`](skill-sources.md) | Fetch/verify/pin/symlink skills from the trusted external sources the adopter listed in `<project-config>/skill-sources.md`. **Main-checkout only** — worktrees share the source snapshots via `worktree-init`. |
| `setup override <skill>` | [`overrides.md`](overrides.md) | Open / scaffold an override file. |
| `setup uninstall` | [`uninstall.md`](uninstall.md) | Reverse the install. Removes snapshot, locks, symlinks, hook, doc sections, and this skill itself. Preserves `.apache-magpie-overrides/` unless `--purge-overrides` is passed. **Main-checkout only.** |
| `setup unadopt` | [`uninstall.md`](uninstall.md) | Alias of `uninstall`. |

**Main-checkout-only sub-actions** (`adopt`, `upgrade`,
`unadopt` — all of them pinned-snapshot operations; a marketplace
install touches no repo state and runs anywhere)
detect their context via `git rev-parse --git-dir` ≠
`git rev-parse --git-common-dir` and refuse to run in a worktree
with a pointer back to the main checkout. The worktree counterpart
of `adopt` is `worktree-init`; for `upgrade`, every worktree
automatically sees the refreshed snapshot once the main runs
upgrade, because each worktree's `<snapshot-dir>` is a symlink to
the main's.

**`adopt` and `upgrade` always chain into `worktree-init` on every
linked worktree as their final pass.** The chain is unconditional
— even on a fresh adoption with no linked worktrees yet (the pass
becomes a no-op), even on an upgrade where every worktree already
looks wired (`worktree-init` is idempotent, repairs broken
symlinks, and adds new always-on-family entries the upgrade
introduced). The user does not need to remember to `cd` into each
worktree and re-run anything; the main-checkout sub-action
propagates state outward to the worktrees by itself. See
[`install.md` Step 12.2](install.md#step-12--post-install-sync--worktree-propagation--sandbox-allowlist--sanity-check)
and
[`upgrade.md` Step 6c](upgrade.md#step-6c--propagate-to-every-worktree-run-worktree-init-unconditionally).

If the snapshot is missing (no `<snapshot-dir>/`) and
`<committed-lock>` exists, the skill treats any sub-action as
the recover-snapshot path: re-install per the committed lock
first, then continue.

## Inputs

| Flag | Effect |
|---|---|
| `from:<git-ref>` / `from:<version>` | Install or upgrade from a specific framework ref or version. Used during `install` (overrides the user prompt; on `method:marketplace` it pins the marketplace to that tag — `/plugin marketplace add apache/magpie@<version>`) and `upgrade` (overrides the committed lock for *this run only* — does NOT update the committed lock). |
| `method:<marketplace\|git-branch\|git-tag\|svn-zip\|local>` | Pick the install method explicitly. **Default during `install`: `marketplace`** — the other methods are the fallback for what a marketplace cannot cover ([Golden rule 10](#golden-rules)), so the agent proposes the marketplace path and names the fallback rather than opening with a three-way method prompt. **`marketplace`** writes nothing to the repo (see [`install.md` → Marketplace install](install.md#marketplace-install--the-default-path)). **`local`** is **framework-checkout only** — it self-adopts by linking the in-repo `skills/` source directly instead of fetching a snapshot (see [`install.md` → Local self-adoption](install.md#local-self-adoption-methodlocal)). |
| `agents:<list>` | Comma-separated **agent targets** to wire symlinks into ([`agents.md`](agents.md) registry ids: `universal`, `claude-code`, `github`, `windsurf`, `goose`, …). Default on `adopt`/`upgrade`: auto — the always-on neutral set (`universal` + `claude-code` + `github`) plus any other registry dir already present in the repo. When passed, **replaces** the auto-detected set for that run, except `universal` (`.agents/skills/`) which is always retained because it is the canonical home every other target relays into — dropping it would leave the relays dangling. |
| `skill-families:<list>` | Comma-separated **opt-in** families — the set to symlink on the snapshot path, the set of `magpie-<family>` plugins to install on the marketplace path — any of the opt-in families declared by a `family:` frontmatter key in the snapshot (today: `security`, `pr-management`, `issue`, `release-management`, `repo-health`, `pairing`, `mentoring`, `contributor-growth`). Default on `adopt`: prompt (see [`install.md` Step 5](install.md#step-5--pick-the-skill-families-and-mcp-servers)). Default on `upgrade`: read the families list from `<committed-lock>` / `<local-lock>`, **auto-include any opt-in family the framework has introduced since the lock was written** (recorded back into the lock), and **ensure every framework skill in the effective family set has a valid symlink** — create or repair missing / broken symlinks, not just add new ones. The flag never accepts the always-on families (`setup`, `utilities`); per [Golden rule 8](#golden-rules) those are wired up unconditionally on every run and there is no way to ask for them or opt out. |
| `--purge-overrides` | *(unadopt only)* Also `git rm -r` `.apache-magpie-overrides/`. Default: preserve. |
| `--no-overrides` | *(any framework skill)* Skip override-file lookup for this single invocation. Runs the skill against framework defaults; override files on disk are not read, modified, or deleted. The safety baseline (confidentiality, privacy, security) still applies. See [One-shot defaults run](../../docs/setup/agentic-overrides.md#one-shot-defaults-run). |
| `dry-run` | Show what the skill would do without writing anything. |

## What this skill is NOT for

- Not for installing the secure agent setup (sandbox, hooks,
  pinned tools). That is
  [`setup-isolated-setup-install`](../setup-isolated-setup-install/SKILL.md).
- Not for upgrading framework tools installed on the host
  (`bubblewrap`, `socat`, `claude-code` itself). That is
  [`setup-isolated-setup-update`](../setup-isolated-setup-update/SKILL.md).
- Not for syncing the user's `~/.claude-config` across
  machines. That is
  [`setup-shared-config-sync`](../setup-shared-config-sync/SKILL.md).
- Not for committing framework changes. Framework PRs go
  against `apache/magpie` directly — the snapshot is
  read-only.

## Failure modes

| Symptom | Likely cause | Remediation |
|---|---|---|
| `setup verify` reports drift between committed and local locks | Project lead bumped `<committed-lock>` since this machine last fetched, or local snapshot is stale on a `main`-tracking adopter | `setup upgrade` |
| Snapshot present but symlinks dangle | Adopter ran `git clone` but not `setup` after — symlinks are gitignored but persist in their target's absence on disk | `setup verify --auto-fix-symlinks` (or `setup install`, idempotent) |
| Worktree off the adopter repo can't find framework skills | Worktrees off the adopter don't auto-inherit the gitignored snapshot | The `adopt` sub-action installs a `post-checkout` git hook that re-runs the snapshot install on worktree creation; verify the hook is present (`setup verify`) |
| The agent offers no `/plugin` (or equivalent) command | That agent has no marketplace — the one case the pinned snapshot install exists for | `setup install method:git-branch` (or `svn-zip` for the signed release) — see [`docs/setup/install-recipes.md`](../../docs/setup/install-recipes.md) |
| Every Magpie skill appears twice, under both `/magpie-<skill>` and `/magpie-<family>:<skill>` | Both install paths are live on this machine — a snapshot install underneath a marketplace one | Keep one ([Golden rule 10](#golden-rules)): `setup uninstall` to drop the repo-side snapshot, or uninstall the plugins if the project needs the committed pin |
| `git clone` of an upstream PR sees no framework skills | Expected — the snapshot is gitignored, so a fresh clone has no `<snapshot-dir>`. The clone needs `setup` once before any framework skill is invocable | `setup` |
| Project decided to stop using apache-magpie | The reverse of adoption — remove the snapshot, locks, symlinks, hook, doc sections, and the `setup` skill itself. `.apache-magpie-overrides/` is preserved by default | `setup unadopt` (add `--purge-overrides` to also drop the overrides directory) |
