<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

`<project-config>/project.md` has no `mail_create` block. The resolved
`user.md` has `tools.mail_create` with `backend: maildir`,
`drafts_path: ~/Mail/<project>/Drafts` and `from_address: me@example.org`.
A Gmail OAuth credential exists at `~/.config/apache-magpie/gmail-oauth.json`.

The skill is about to draft a reply to the reporter.
