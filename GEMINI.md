<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Apache Magpie — Gemini CLI extension context](#apache-magpie--gemini-cli-extension-context)
  - [Upgrade prompt](#upgrade-prompt)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Apache Magpie — Gemini CLI extension context

This context ships with the Apache Magpie Gemini CLI extension. Gemini has no
plugin update/lifecycle hook (unlike Claude Code), so this file is how the
extension prompts you to reconcile after an update.

## Upgrade prompt

The Magpie extension declares its version in `gemini-extension.json`. At the
start of a session, compare that `version` against the value you last recorded
in `magpie-plugin-version` under the extension's state directory (create the
file if it does not exist):

- If the version has **changed** since you last recorded it — the marketplace
  updated the extension — tell the user, once and non-intrusively:

  > Apache Magpie was updated to `<version>`. If this repo adopts Magpie, run
  > `/magpie-setup upgrade` to reconcile the snapshot, agentic overrides, and
  > drift.

  Then record the new version.

- If the version is unchanged, say nothing.

Never run the upgrade yourself: `/magpie-setup upgrade` is a guided,
user-confirmed action, and Magpie never mutates an adopter repo unattended.
