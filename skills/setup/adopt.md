<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/legal/release-policy.html -->
# adopt — commit the repo's recommended defaults for every contributor

Adoption is **not** an install. Installing puts the marketplace and
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
[`docs/setup/individual-use.md`](../../docs/setup/individual-use.md).
The reader-facing page for this sub-action is
[`docs/setup/team-adoption.md`](../../docs/setup/team-adoption.md).

## Inputs

- No positional argument. `setup adopt` adopts the repo you are in.
- `--purge-overrides` — **`unadopt` only.** Also remove
  `.apache-magpie-overrides/`, which is preserved by default.

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

The floor is **fixed**: `magpie-setup`, `magpie-utilities` and
`magpie-agent-guard`.

It does **not** grow to match what this maintainer installed. A
maintainer-only family such as `magpie-security` stays a personal,
user-scope install — committing it would make every contributor pay
its always-on context cost for work only one person does.

If the user asks for a larger floor, say what it costs and let them
decide. Do not propose one.

## Step 2 — Write the default set

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
- **Add whichever of the floor's three entries are missing from an
  existing `enabledPlugins`, and remove nothing** — not other Magpie
  plugins, not other vendors' plugins. The floor is
  `magpie-setup@apache-magpie`, `magpie-utilities@apache-magpie`,
  `magpie-agent-guard@apache-magpie`.
- **If the file does not exist**, create it with exactly those two
  keys: `extraKnownMarketplaces` defining `apache-magpie`, and
  `enabledPlugins` containing the floor.
- **If the file exists but does not parse as JSON, stop and say so.**
  Do not rewrite a file you cannot read; a malformed settings file is
  the user's to fix. Nothing was written — stop without staging.

## Step 3 — Scaffold the overrides store

Scaffold `.apache-magpie-overrides/` exactly as
[`install.md` Step 9](install.md#step-9--scaffold-apache-magpie-overrides-fresh-only)
does — same exclusions, same `project.md` pre-population. `git add`
it; do not commit.

If it already exists, say so and leave it alone.

## Step 4 — Recap

Tell the user, in this order:

1. **What is staged** — the two paths, and that nothing is committed.
2. **What a contributor will get on clone** — the three floor plugins
   enabled after they trust the repo; no install step for them.
3. **What this does not do** — it does not limit what anyone may
   install for themselves, and it does not install anything for the
   maintainer running it.
4. **Keeping it honest** — an override everyone would want is a
   missing framework feature; `setup:override-upstream <skill>` walks
   it into a PR against `apache/magpie`, after which the local
   override can go.

## Unadopt

`setup unadopt` withdraws the recommendation:

- remove the `apache-magpie` entry from `extraKnownMarketplaces` and
  the three floor entries from `enabledPlugins`, **leaving every other
  key and every other plugin exactly as they are**. If that empties a
  key, remove the empty key rather than leaving `{}`.
- preserve `.apache-magpie-overrides/` unless `--purge-overrides` is
  passed.

**Leave every install alone** — the user's own, and everyone else's.
Un-adopting is the repo withdrawing a recommendation; it uninstalls
nothing. Removing the *install* is
[`uninstall.md`](uninstall.md), a different operation with a
different blast radius. Say which one you did.

Stage, never commit. Show the diff first.

## If the user meant "install"

Before 0.2.0, `adopt` was an alias of `install`. Someone typing it
from memory or from an old runbook probably wants the install.

If the repo has no Magpie install at all, say plainly that `adopt`
now means something else — it commits a recommendation for every
contributor — and offer `setup install` instead. **Do not silently do
either one.** Ask which they meant.
