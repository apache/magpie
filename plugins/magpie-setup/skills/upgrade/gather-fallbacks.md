<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Gather when the checker cannot answer

Read from [Gather](SKILL.md#gather) when the case below holds; the rest of Gather still applies.

## No checker copy

If the call fails with `ModuleNotFoundError`, no checker copy exists yet: treat the repo as not configured (below), since `setup config` installs the checker.
A location the plan still needs is then worked out without the plugin's copy, which Bash cannot read under the sandbox.
In a framework checkout or on a pinned snapshot, run the in-tree package inside the sandbox (`plugins/magpie-setup/skills/setup/` or `.apache-magpie/tools/setup-preflight/src/` on `PYTHONPATH`).
On a marketplace install, apply [`setup config` Step 2](../setup/config.md#step-2--keep-the-personal-layer-invisible-to-git)'s rule by hand: `.apache-magpie-local/` when `.apache-magpie.lock` is committed, otherwise `<git-common-dir>/apache-magpie/`.

## Magpie installed but not configured here

No personal layer (or no checker copy to ask), no `.apache-magpie-overrides/`, no committed lock: the plan carries one *Add* item, run [`setup config`](../setup/config.md) (personal, gitignored, needs nobody's permission).
It mentions `/magpie-setup:setup adopt` as information only, one line saying adoption commits files for every contributor and is the project's decision; this skill never runs it.
