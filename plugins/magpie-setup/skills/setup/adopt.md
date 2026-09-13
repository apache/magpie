<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/legal/release-policy.html -->
# adopt — commit the repo's recommended defaults for every contributor

Adoption is **not** an install. Installing puts the Apache Magpie
Marketplace and
plugins into *this machine's* agent and writes nothing to the
repository. Adopting is the separate, deliberate act of a repo's
maintainers committing a recommendation that every contributor picks
up on clone:

1. **The default plugin set** — `extraKnownMarketplaces` plus an
   `enabledPlugins` floor in the repo's `.claude/settings.json`.
2. **The overrides store** — `.apache-magpie-overrides/`, where the
   project's own skill-behaviour changes live.

Neither is required to use Magpie in this repo. A contributor can
install whatever they like and ignore both; see
[`docs/setup/individual-use.md`](../../../../docs/setup/individual-use.md).
The reader-facing page for this sub-action is
[`docs/setup/team-adoption.md`](../../../../docs/setup/team-adoption.md).

## Inputs

- No positional argument. `setup adopt` adopts the repo you are in.
- `--purge-overrides` — **`unadopt` only, never `adopt`.** Also remove
  `.apache-magpie-overrides/`, which is preserved by default.
  [`uninstall`](uninstall.md) takes the same flag, with the same
  default.

## Step 0 — Pre-flight

1. **Main checkout only.** `adopt` writes committed repo files. In a
   worktree, stop and say so.
2. **Claude Code only, for the default set.** On any other client,
   skip the default set entirely and say why rather than writing a
   file that does nothing: Codex can only default-install all ten
   families, and Gemini has no workspace-extension mechanism. The
   overrides store in Step 4 still applies on every client.
3. **Is this the user's decision to make?** Adoption commits files
   that change what every contributor's agent loads. If there is any
   sign this is not a maintainer acting for the project — they say
   they are "just trying it", they are working in someone else's
   repo, they came here from an install flow — say what adoption
   commits and confirm before going further.

## Step 1 — Decide the default set

The floor is **seeded** with `magpie-setup`, `magpie-utilities` and
`magpie-agent-guard`, in that order, and that is what it stays unless
the maintainer explicitly asks for more.

It **never grows automatically** — not to match what this maintainer
installed, not to match what the framework has started shipping. A
maintainer-only family such as `magpie-security` stays a personal,
user-scope install — committing it would make every contributor pay
its always-on context cost for work only one person does.

If the user asks for a larger floor, say what it costs and let them
decide. Do not propose one. A floor they enlarge is still the floor:
every later step — the lock in Step 2, the wiring in Step 3, `verify`,
`uninstall` and `unadopt` — reads the list the lock actually carries,
in floor order, never a fixed count.

## Step 2 — Write the floor lock

The floor from Step 1 is recorded in `.apache-magpie.lock`, committed
at the repo root. This is the project's adoption record, and it is
harness-neutral: write it on **every** client, including the ones that
cannot express the derived wiring in Step 3.

```text
# .apache-magpie.lock — committed; the project's floor.

method:       marketplace
url:          apache/magpie
min_version:  0.3.0

plugins:
  - magpie-setup
  - magpie-utilities
  - magpie-agent-guard
```

- **`min_version` is the Magpie version installed on this machine right
  now** — the version the maintainer is actually validating against.
  Read it from `claude plugin list --json`, or from the running agent's
  equivalent. Record it **verbatim**: a `.devNNNN` build adopted
  mid-cycle is written as it stands, not rounded up or down to a
  release. [`locks.md`](locks.md#method-marketplace--the-adoption-floor)
  explains why PEP 440 makes that correct.
- **`plugins` is the floor from Step 1**, in floor order, and nothing
  else. A family the maintainer happens to have installed does not
  enter the floor because it is installed — only because they asked for
  it in Step 1.
- **`url` is `apache/magpie`.** See
  [`locks.md`](locks.md#url-is-a-security-boundary) — a floor naming
  any other marketplace loses the pre-flight's automatic behaviour, so
  do not write one unless the user has a reason and knows the cost.

**If a lock already exists**, this is a re-adoption. Show the diff
between the existing floor and the one Step 1 produced, and let the
maintainer confirm. Never lower `min_version`: if the existing floor is
*higher* than the installed version, keep the existing value and say
so — a floor going backwards would silently withdraw a requirement the
project already made.

`git add` the lock. **Never commit** — the floor lands through the
project's normal review process, like any other committed file.

## Step 3 — Write the derived wiring

`.claude/settings.json` is **derived from the lock in Step 2**, not
authored here: `extraKnownMarketplaces` names `url`, and
`enabledPlugins` contains `plugins`, each as `<plugin>@apache-magpie`.
The lock is the source of truth; this file is how Claude Code acts on
it.

**Write the marketplace entry untagged** — `"repo": "apache/magpie"`,
with no `@version`. The floor is a minimum, and tagging the marketplace
would convert it into a ceiling that stops contributors receiving any
later release.

On a client that cannot express this — Codex can only default-install
all ten families, Gemini has no workspace-extension mechanism — skip
this step and say so. The lock from Step 2 still stands and is still
the project's record; what is missing is only the automatic wiring.

Show the exact diff you intend to write, then write it. **`git add`
what you write. Never commit** — the change lands through the
project's normal review process, like any other committed file.

### Merge rules

`.claude/settings.json` is not Magpie's file. This repository's own
carries `sandbox` and `permissions` blocks; an adopter's will carry
whatever they put there.

- **Touch only two keys** — `extraKnownMarketplaces` and
  `enabledPlugins`. Every other top-level key is preserved exactly as
  it was.
- **Leave an existing `apache-magpie` marketplace definition alone.**
  An adopter pinning `apache/magpie@0.2.0` has made a deliberate
  choice; do not rewrite it to track `main`.
- **Add whichever of the floor's entries are missing from an existing
  `enabledPlugins`, and remove nothing** — not other Magpie plugins,
  not other vendors' plugins. The floor's entries are the lock's
  `plugins` list, in floor order, each as `<plugin>@apache-magpie`.
  That list is **seeded** with `magpie-setup@apache-magpie`,
  `magpie-utilities@apache-magpie`, `magpie-agent-guard@apache-magpie`
  — a project whose maintainers enlarged it in Step 1 has more, and
  the lock is what you read, never a fixed count.
- **If the file does not exist**, create it with exactly those two
  keys: `extraKnownMarketplaces` defining `apache-magpie`, and
  `enabledPlugins` containing the floor.
- **If the file exists but does not parse as JSON, stop and say so.**
  Do not rewrite a file you cannot read; a malformed settings file is
  the user's to fix. Nothing was written — stop without staging.

## Step 4 — Scaffold the overrides store

Scaffold `.apache-magpie-overrides/` exactly as
[`install.md` Step 9](install.md#step-9--scaffold-apache-magpie-overrides-fresh-only)
does — same exclusions, same `project.md` pre-population. `git add`
it; do not commit.

If it already exists, say so and leave it alone.

## Step 5 — Recap

Tell the user, in this order:

1. **What is staged** — the three paths (the lock, the derived wiring,
   the overrides store), and that nothing is committed.
2. **What the floor means** — a minimum, not a pin. Contributors on a
   newer Magpie are fine and will be told nothing; contributors behind
   it are brought up to it by the pre-flight in any skill they run.
   Nothing is ever downgraded or removed.
3. **What a contributor will get on clone** — the floor plugins the lock
   names, enabled after they trust the repo; no install step for them.
4. **What this does not do** — it does not limit what anyone may
   install for themselves, and it does not install anything for the
   maintainer running it.
5. **Keeping it honest** — an override everyone would want is a
   missing framework feature; `setup:override-upstream <skill>` walks
   it into a PR against `apache/magpie`, after which the local
   override can go.

## Unadopt

`setup unadopt` withdraws the recommendation:

- remove `.apache-magpie.lock`, the committed floor itself. The project
  is withdrawing its recommendation, not only the wiring derived from
  it — leaving the lock in place would mean every contributor's
  pre-flight kept enforcing a floor the project no longer wants.
- remove the `apache-magpie` entry from `extraKnownMarketplaces` and
  the floor entries from `enabledPlugins` — the wiring derived from
  that lock. Read the entries off the lock's `plugins` list before you
  delete it, in floor order, each as `<plugin>@apache-magpie`: a floor
  a maintainer enlarged carries more than the seeded
  `magpie-setup@apache-magpie`, `magpie-utilities@apache-magpie`,
  `magpie-agent-guard@apache-magpie`, and leaving one behind would
  commit a plugin entry whose marketplace definition you just removed.
  **Leave every other key and every other plugin exactly as they are.**
  If that empties a key, remove the empty key rather than leaving `{}`.
- preserve `.apache-magpie-overrides/` unless `--purge-overrides` is
  passed.

**Leave every install alone** — the user's own, and everyone else's.
Un-adopting is the repo withdrawing a recommendation; it uninstalls
nothing. Removing the *install* is
[`uninstall.md`](uninstall.md), a different operation with a
different blast radius: `uninstall` leaves `.apache-magpie.lock` in
place; only `unadopt` removes it. Say which one you did.

Stage, never commit. Show the diff first.

## If the user meant "install"

Before 0.2.0, `adopt` was an alias of `install`. Someone typing it
from memory or from an old runbook probably wants the install.

If the repo has no Magpie install at all, say plainly that `adopt`
now means something else — it commits a recommendation for every
contributor — and offer `setup install` instead. **Do not silently do
either one.** Ask which they meant.
