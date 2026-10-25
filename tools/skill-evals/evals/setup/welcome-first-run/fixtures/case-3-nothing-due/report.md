<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

There is no `.apache-magpie.lock` and no `.apache-magpie-overrides/`.
The personal layer at `.git/apache-magpie/` holds only a `reconciled.json`
recording the user's welcome-guide answers. The running agent is Claude Code
with magpie-setup 0.4.0 installed.

The user hid both the general and the setup welcome guides for good on
earlier runs. No required configuration resolves here yet.
The user invoked `/magpie-setup:setup verify`.

The welcome check printed:

```json
{
  "verdict": "ok"
}
```
