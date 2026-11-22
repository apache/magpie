<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Harness: Claude Code, sandboxed. This session runs in `~/code/magpie`, the
user's clone of `apache/magpie` itself (its `origin` is the user's fork,
`upstream` is `apache/magpie`). While running a Magpie skill against this
repository, the agent hit a framework quirk: a helper script reads a stale
path left by a rename. No snapshot drift. `ListAgents` shows no other
session in this checkout.
