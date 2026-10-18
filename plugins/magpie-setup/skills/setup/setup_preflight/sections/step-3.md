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

**The actions.**  The `below-floor` finding names the harness its listing
came from (`facts.harness`); the commands differ per client, and naming one
the operator cannot run in this session wastes their turn:

| Harness | a floor plugin absent | a floor plugin below `min_version` |
|---|---|---|
| Claude Code | `claude plugin install <plugin>@apache-magpie` | `claude plugin update <plugin>@apache-magpie` |
| Codex | `codex plugin add <plugin>@apache-magpie` | `codex plugin update <plugin>` |
| Gemini CLI | `gemini extensions install https://github.com/apache/magpie` | `gemini extensions update magpie` |

Gemini installs the framework as one extension, so on it the floor is
carried by the `magpie` extension as a whole: update that one extension
rather than naming individual plugins.

Copilot CLI installs from a repo URL or catalogue and has no plugin CLI to
read a listing or run an action with. There the floor stays unknown: run
nothing, and leave it to the user.

Where there is no such CLI, run nothing and print the commands instead.

Then step 5 applies: whichever of these you took, the session is still
below the floor and has to be restarted.
