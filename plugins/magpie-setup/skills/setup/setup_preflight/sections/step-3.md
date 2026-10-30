<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## step-3 — the marketplace floor

**`url` names something other than `apache/magpie`.** Run **nothing**. Name
the marketplace the lock points at, show the commands it would take, and
let the user decide: the skill stops until they have. A lock is a committed file in whatever repository
happened to be opened, and acting on it automatically would make opening a
repository enough to install someone else's code.

**Comparing versions.** PEP 440, not strings: `0.10.0` is newer than
`0.9.0`, and `0.2.0` is newer than `0.2.0.dev202609110041`. A dev build is
a version like any other — nothing strips the `.devN` segment or rounds to
the release segment. The reconciliation check in step 4 is gated on the
fingerprint, never on this version delta.

**Why an unreadable result is *unknown* rather than *absent*.** Inside a
sandboxed session the plugin cache is read-denied and the running harness's
own listing returns `[]` there — that reads exactly like "nothing installed"
but is not. Acting on it would propose installing a project's entire floor
on every sandboxed run.

For Codex, read only the `installed` list in its JSON envelope; available
catalogue entries are not installed versions. An unfamiliar name form or
schema stays unknown. Require an exact floor plugin name before trusting
a Codex listing, and the exact `magpie` plugin name on Antigravity.

**The actions.**  The `below-floor` finding names the harness its listing
came from (`facts.harness`); the commands differ per client, and naming one
the operator cannot run in this session wastes their turn:

| Harness | a floor plugin absent | a floor plugin below `min_version` |
|---|---|---|
| Claude Code | `claude plugin install <plugin>@apache-magpie` | `claude plugin update <plugin>@apache-magpie` |
| Codex | `codex plugin add <plugin>@apache-magpie` | `codex plugin marketplace upgrade apache-magpie` |
| Antigravity | `agy plugin install https://github.com/apache/magpie` | `agy plugin install https://github.com/apache/magpie` |

Antigravity installs the framework as one plugin, so on it the floor is
carried by the `magpie` plugin as a whole: re-install that one plugin
rather than naming individual plugins. Its listing also shows plugins
without a version, such as Google's own; they are not Magpie's.

`facts.harness` is `null` when the caller supplied the listing and no
harness with a listing command is running. Use the row of the harness this
session runs in; if that is not known, print every row rather than guess.

Copilot CLI installs from a repo URL or catalogue and has no plugin CLI to
read a listing or run an action with. There the floor stays unknown: run
nothing, and leave it to the user.

Where there is no such CLI, run nothing and print the commands instead.

Then step 5 applies: whichever of these you took, the session is still
below the floor and has to be restarted.
