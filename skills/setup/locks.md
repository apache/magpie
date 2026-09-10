<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/legal/release-policy.html -->

# locks — the two lock files (pinned-snapshot path only)

Lock files exist only on the **pinned snapshot install**. The
default marketplace install has none: the agent's plugin manager
owns the version, and pinning there means adding the marketplace
from a tag (`/plugin marketplace add apache/magpie@<version>`).

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
sources](../../docs/skill-sources/README.md) use their **own**
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
