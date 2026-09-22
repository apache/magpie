<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# The pinned-snapshot model

Read this on the snapshot path only. A marketplace install — the
default — needs none of it, and `SKILL.md` carries the table that
decides which path a machine is on.

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
  [`docs/setup/install-recipes.md`](../../../../docs/quick-start/other-install-methods.md)
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
  [`docs/setup/agentic-overrides.md`](../../../../docs/setup/agentic-overrides.md)
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

## The golden rules that bind only here

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
- The `magpie-*` symlinks `setup install` creates in every active
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
