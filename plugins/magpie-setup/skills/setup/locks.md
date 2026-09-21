<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/legal/release-policy.html -->

# locks — the committed record and the local fingerprint

Every **adopted** project has one committed lock, whatever install
method it uses. What the lock means depends on the method:

| Method | The committed lock is | A newer local version is |
|---|---|---|
| `marketplace` | a **floor** — the minimum the project expects | fine, and reported as nothing |
| `svn-zip` / `git-tag` / `git-branch` | a **pin** — the exact version to re-fetch | **drift**, to be reconciled |

The second lock, `<local-lock>`, exists only on the three snapshot
methods: it fingerprints what this machine fetched. A marketplace
install has no local lock, because the agent's plugin manager already
knows what is installed and `claude plugin list --json` reports it.

The framework's lock-file model splits **what the project pins
to** (committed) from **what this machine actually fetched**
(local). This split is the foundation of drift detection and
the multi-installer support.

## `<committed-lock>` — `.apache-magpie.lock`

Committed at the adopter repo root. The **project's pin**.
Edited only by `setup`; do not modify by hand.

```text
# .apache-magpie.lock — committed; the project's pin.

method: <git-branch | git-tag | svn-zip>
url:    <see per-method format below>

# For method=git-branch:
ref:    main

# For method=git-tag:
ref:    v1.0.0          # the tag name
commit: <SHA>           # the commit the tag pointed to when committed

# For method=svn-zip:
ref:    1.0.0           # the version number
sha512: <hash>          # the released zip's SHA-512 (for re-fetch verification)
```

The next adopter who runs `setup install` reads this
file and re-installs to the **same version** the project
declared. This is the core of the "adopt once, all subsequent
users get the same thing" promise.

## `method: marketplace` — the adoption floor

```text
# .apache-magpie.lock — committed; the project's floor.

method:       marketplace
url:          apache/magpie
min_version:  0.2.0

plugins:
  - magpie-setup
  - magpie-utilities
  - magpie-agent-guard
```

Read it as: *this project expects at least Magpie `min_version`, and
expects at least these plugins to be available.*

**Neither line is a ceiling.** A contributor running 0.4.0 with seven
families installed satisfies this lock completely and is told nothing.
Nothing downgrades a plugin, removes one, or pins the marketplace to
`min_version` — the `extraKnownMarketplaces` entry derived from this
lock is written **untagged**, so contributors track the tip and meet
the floor by default.

`min_version` rather than `ref` is deliberate. On `git-tag` and
`svn-zip`, `ref` **is** a pin and re-fetching that exact version is the
point; reusing the key here would put two opposite meanings under one
name in one file.

### Deciding how a machine stands

1. **`method` is not `marketplace`** → `not-marketplace`. The three
   snapshot methods pin; their rules are above, not here.
2. **`method`, `url`, `min_version` or `plugins` is missing or
   unparsable** → `malformed`. Do not guess at a lock you cannot read.
3. **A plugin in `plugins` is not installed** → `plugin-missing`, and
   it goes in `needs`.
4. **An installed plugin's version is below `min_version`** →
   `below-floor`, and it goes in `needs`.
5. **Otherwise** → `satisfied`, `needs` empty.

`plugin-missing` wins over `below-floor` when both are true: a plugin
that is absent has no version to be behind.

**Compare versions as PEP 440, never as strings.** `0.10.0` is *newer*
than `0.9.0`, and `0.2.0` is newer than `0.2.0.dev202609110041` — a
maintainer who adopted mid-cycle against a `.dev` build is correctly
satisfied by the release that follows it. String ordering gets both of
these backwards.

**One version, not per-plugin.** Every Magpie plugin's version tracks
the framework's `pyproject.toml`, so `min_version` is a single
framework version rather than a per-plugin constraint.

### `url` is a security boundary

`url` names the marketplace the floor's plugins come from. Any
automated action taken on this lock's behalf — see the pre-flight in
every skill — runs **without asking only when `url` is
`apache/magpie`**. Any other value is reported and explicitly
confirmed first.

A lock is a committed file in whatever repository the user happened to
open. Treating it as authority to install from an arbitrary marketplace
would make opening a repository enough to install an attacker's code.

## The `reconciled:` block — what was checked, not what to install

The floor above says what the project expects to have installed. It
says nothing about whether the project's own configuration — its
answers to `requires_config`, the overrides it wrote against a
specific skill's steps — was last checked against a build that still
matches those skills' current shape. A plugin can satisfy
`min_version` completely and still carry a configuration written
against a step heading, or a `requires_config` entry, that a later
version renamed or dropped. `setup` closes that gap with a second,
generated block:

```text
# .apache-magpie.lock — committed; the project's floor plus its
# reconciliation state.

reconciled:
  version: 0.2.0.dev202609211315     # what setup last ran against
  at:      2026-09-21
  skills:
    magpie-pr-management-code-review:  sha256:9f1c4e…
    magpie-security-issue-triage:      sha256:4ab70d…
```

- `version` — the framework version `setup` was running the last time
  it wrote this block. Compared as PEP 440 like every other version in
  this file, `.devN` segment included.
- `at` — the date that write happened.
- `skills` — one entry per skill this project's configuration actually
  touches (configures or overrides), keyed by that skill's frontmatter
  `name:` (e.g. `magpie-pr-management-code-review`) and mapped to the
  `surface_hash` that skill's `SKILL.md` frontmatter carried at the
  time. `name:` rather than `<plugin>/<skill>`, deliberately: it is
  already in the running skill's context (its own pre-flight reads it
  for free), it is unique across the framework, and — unlike
  `<plugin>/<skill>` — it is identical under every install shape,
  including a snapshot install, which wires `skills/<name>/` with no
  plugin component to derive at all. Not the whole catalogue: a skill
  is in scope when an override file names it, **or** when its
  `requires_config:` entries resolve from the project's own config
  directories — a project that supplies a skill's configuration has
  configured that skill. How many skills that is depends entirely on
  how much the project configures; it is two for a project with one
  override, and most of the catalogue for a project that commits a
  widely-read `project.md`.

**Written only by `setup`**: `adopt`, `reconcile` and `upgrade` write
the committed block, and
[`config`](config.md#step-3b--record-what-this-run-reconciled) writes
only `.apache-magpie-local/reconciled.json`, never the lock. Never
hand-edited: a hand-written `sha256:` value is indistinguishable from a
real one right up until the comparison it is supposed to gate silently
agrees with a hash nobody actually computed.

**`version` and `at` mean "when this block was last written," not "when
the project was last fully swept."** Each of those sub-actions updates
the block without necessarily touching every skill in `skills:` —
[`adopt`](adopt.md) migrates whatever the local stamp already held,
[`upgrade`](upgrade.md#step-5--reconcile-overrides) reconciles whatever
`.apache-magpie-overrides/` covers, and only
[`reconcile`](reconcile.md) itself walks every configured skill in one
pass. (`config` moves the same clock in the local store, on a project
that has not adopted.) `at` still feeds the verify-overdue clock in
[`tools/dev/preflight-block.md`](../../../../tools/dev/preflight-block.md#pre-flight--is-this-project-set-up)
(step 10) — a recent `at` says only that *something* in this project was
reconciled recently, not that everything was.

**Where the block lives tracks where the configuration it describes
lives, not the install method.** An **adopted** project — `marketplace`
floor or snapshot pin alike — carries it in `.apache-magpie.lock`,
beside whatever that method already records: the lock already states
what the project expects, and this states what state its configuration
is in. A project that has run `setup config` but never `setup adopt`
has no committed lock to hold it, so the identical `version`/`at`/
`skills` shape lives in `.apache-magpie-local/reconciled.json`
instead, next to the personal configuration it describes. **`skills`
therefore lives in exactly one place, never both.** **Neither
configured nor adopted — no `.apache-magpie.lock`, no
`.apache-magpie-local/`, no `.apache-magpie-overrides/` — → no block
anywhere**, because there is no configuration to have gone stale. A
skill's own pre-flight treats that absence as nothing-to-reconcile,
silently, not as a sweep to propose.

**`.apache-magpie-local/reconciled.json` is a plain JSON object, never
wrapped in a `reconciled:` key** — the filename already says what it
is. A **configured-but-unadopted** project, which has nowhere else to
keep `version`/`at`/`skills`, carries the full shape:

```json
{
  "version": "0.2.0.dev202609211315",
  "at": "2026-09-21",
  "skills": {
    "magpie-pr-management-code-review": "sha256:9f1c4e…"
  },
  "verified_at": "2026-09-21",
  "verify_suggested_at": "2026-09-07",
  "acknowledged": {
    "skills": {
      "magpie-security-issue-triage": "sha256:4ab70d…"
    },
    "sweep": "0.2.0.dev202609180100"
  }
}
```

An **adopted** project's local file carries only the three
always-local keys below — `version`/`at`/`skills` live in the
committed lock instead, per the invariant above:

```json
{
  "verified_at": "2026-09-21",
  "verify_suggested_at": "2026-09-07",
  "acknowledged": {
    "skills": {
      "magpie-security-issue-triage": "sha256:4ab70d…"
    },
    "sweep": "0.2.0.dev202609180100"
  }
}
```

**Three keys are never committed, even inside an adopted project's
`.apache-magpie.lock`, and live in this file on every project
regardless of adoption state:** `verified_at`, `verify_suggested_at`,
and `acknowledged`. Running `/magpie-setup verify` and being shown a
reconciliation proposal are both per-machine acts — one contributor's
health check, one contributor's own prompt history — and neither is a
fact about the project's committed configuration the way
`version`/`at`/`skills` are. Committing `verified_at` would rewrite the
lock every time anyone on the team ran `verify`, turning a periodic
health check into commit noise on a roughly fortnightly cycle;
committing `acknowledged` would bind every other contributor to one
person's prompt history. This is the same committed/local split the
rest of this file draws everywhere else: what the project agreed to is
shared, what one person's machine has seen is not.

**A `skills` entry for the same skill in both stores is an expected
transitional state, not a fault.** The ordinary way there needs no
hand edit and no bug: a contributor runs `config` on their machine
before the project adopts, a maintainer runs `adopt` on a different
machine, and `adopt` can only migrate the local stamp it can see —
so the contributor's local entry survives beside the newly committed
one. When it happens, the local entry wins for every comparison, and
`/magpie-setup reconcile` names the collision and offers to drop the
redundant local entries, leaving the committed lock as the single
store. That is the whole remedy.

`acknowledged.skills` and `acknowledged.sweep` record when a
reconciliation proposal was **shown**, not when it was declined — the
pre-flight check prints its proposal and continues into the work the
user asked for in the same turn; it never blocks waiting for an
answer, so there is no decline event to write on. `acknowledged.skills`
maps a skill's `name:` to the `surface_hash` it was shown against, and
is re-armed the moment that skill's hash moves again.
`acknowledged.sweep` records the version the project-wide sweep
proposal was shown against — the installed plugin version on a
marketplace install, the framework version otherwise, exactly the
fallback `version` above already takes — and is re-armed only when
that version changes; project-scoped, because the sweep itself is:
keying it per skill would mean the sweep gets proposed once for every
skill the user happens to invoke, rather than once per project, which
is what makes it a one-time cost rather than a recurring one.

## `<local-lock>` — `.apache-magpie.local.lock`

Gitignored at the adopter repo root. The **local snapshot's
fingerprint**. Records what this machine fetched and when.

```text
# .apache-magpie.local.lock — gitignored; per-machine.

source_method:    <git-branch | git-tag | svn-zip>
source_url:       <URL the snapshot was actually fetched from>
source_ref:       <branch / tag / version actually fetched>
fetched_commit:   <commit SHA on disk now>
fetched_at:       <ISO-8601 timestamp>
```

The drift check on every framework-skill invocation compares
this against `<committed-lock>` and surfaces any mismatch as a
proposed `setup upgrade`.

## Source locks — the same split, for trusted external sources

Skills pulled from [trusted external
sources](../../../../docs/skill-sources/README.md) use their **own**
pair of locks with the identical committed-pin / local-fingerprint
split, kept separate from the framework locks so a source re-pin
never entangles a framework upgrade:

- **`.apache-magpie.sources.lock`** (committed) — the project's
  per-source pins, one block per source keyed by `id`
  (`method`/`url`/`ref` + `commit`|`sha512`).
- **`.apache-magpie.sources.local.lock`** (gitignored) — this
  machine's per-source fetch fingerprint.

They are written and reconciled by
[`skill-sources.md`](skill-sources.md) and re-fetched on
`upgrade`; the format and drift semantics live there.
