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
    magpie-pr-management/code-review:  sha256:9f1c4e…
    magpie-security/issue-triage:      sha256:4ab70d…
```

- `version` — the framework version `setup` was running the last time
  it wrote this block. Compared as PEP 440 like every other version in
  this file, `.devN` segment included.
- `at` — the date that write happened.
- `skills` — one entry per skill this project's configuration actually
  touches (configures or overrides), `<plugin>/<skill>` mapped to the
  `surface_hash` that skill's `SKILL.md` frontmatter carried at the
  time. Not the whole catalogue — a handful, not the ~75 skills that
  exist.

**Written only by `setup`** (`config`, `adopt`, `reconcile`), never
hand-edited: a hand-written `sha256:` value is indistinguishable from
a real one right up until the comparison it is supposed to gate
silently agrees with a hash nobody actually computed.

**Where the block lives tracks where the configuration it describes
lives, not the install method.** An **adopted** project — `marketplace`
floor or snapshot pin alike — carries it in `.apache-magpie.lock`,
beside whatever that method already records: the lock already states
what the project expects, and this states what state its configuration
is in. A project that has run `setup config` but never `setup adopt`
has no committed lock to hold it, so the identical shape lives in
`.apache-magpie-local/reconciled.json` instead, next to the personal
configuration it describes. Neither configured nor adopted → no block,
because there is no configuration to have gone stale.

**Three more keys travel with this block and are never committed, even
inside an adopted project's `.apache-magpie.lock`:** `verified_at`,
`verify_suggested_at`, and `acknowledged` always live in
`.apache-magpie-local/reconciled.json`, on every project regardless of
adoption state. Running `/magpie-setup verify` and declining a
reconciliation sweep are both per-machine acts — one contributor's
health check, one contributor's yes/no on a prompt they happened to be
shown — and neither is a fact about the project's committed
configuration the way `version`/`at`/`skills` are. Committing
`verified_at` would rewrite the lock every time anyone on the team ran
`verify`, turning a periodic health check into commit noise on a
roughly fortnightly cycle; committing `acknowledged` would bind every
other contributor to one person's decline of a prompt they never saw.
This is the same committed/local split the rest of this file draws
everywhere else: what the project agreed to is shared, what one person
just did on one machine is not.

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
