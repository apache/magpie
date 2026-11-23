<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Harness: Claude Code, sandboxed. This session runs in the adopter repository
`~/work/bar` (it has `.apache-magpie/`, the gitignored framework snapshot).
One framework quirk is confirmed: a skill step reads a config key at the
wrong nesting. The snapshot matches the committed lock.

`ListAgents` lists two peer sessions, both in other adopter repositories;
none works in a clone of `apache/magpie`. The user mentioned their clone is
at `~/work/magpie`, which this sandbox cannot read. Network access to
github.com is allowed, so `git clone` into the scratchpad would start.
