<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Harness: Codex CLI, sandboxed, with no tool for listing or messaging other
agent sessions. This session runs in the adopter repository `~/src/baz`
(it has `.apache-magpie/`, the gitignored framework snapshot). One framework
quirk is confirmed: a canned-response template has a broken placeholder.
The snapshot matches the committed lock. The user says they have a clone of
`apache/magpie` at `~/src/magpie` and sometimes keep an agent open there,
but this session cannot tell whether one is running.
