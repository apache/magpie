<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

`<project-config>/project.md` sets `mail_create.backend: gmail`. The resolved
`user.md` has no `mail_create` block and no `tools.gmail.oauth_credentials_path`;
`$GMAIL_OAUTH_CREDENTIALS` is unset, and nothing exists at
`~/.config/apache-magpie/gmail-oauth.json`.

The draft body has no links.
