<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Entry: `magpie-security-issue-import`'s pre-flight found `project.md` missing
and started `setup config` for that one skill (family `security`).

The repository has an `.asf.yaml` at its root, and the scaffolded `project.md`
declares `ponymail` with `mandatory: yes` under *Mail sources*.

The session's tool list has no `mcp__ponymail__*`, `mcp__apache-projects__*` or
`mcp__gmail-plaintext__*` tools. The user has not said how they draft mail.
