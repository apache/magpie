<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Entry: the user ran `setup config` for the `security` family.

The repository has an `.asf.yaml` at its root, and the scaffolded `project.md`
declares `ponymail` with `mandatory: yes` under *Mail sources*.

The personal layer's `project.md` already records the mail backends: *Mail
sources* lists `ponymail` (primary) and `gmail` (fallback), and `mail_create`
names `backend: gmail`. The session's tool list has `mcp__ponymail__*` tools.
