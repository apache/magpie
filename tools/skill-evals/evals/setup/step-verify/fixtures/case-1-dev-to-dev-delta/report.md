<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

`claude plugin list --json` (installed set):

```json
[
  {
    "id": "magpie-pr-management",
    "version": "0.2.0.dev202609180100",
    "scope": "user",
    "enabled": true,
    "installPath": "~/.claude/plugins/cache/apache-magpie/magpie-pr-management/0.2.0.dev202609180100",
    "installedAt": "2026-09-18T01:00:00Z",
    "lastUpdated": "2026-09-18T01:00:00Z"
  },
  {
    "id": "magpie-setup",
    "version": "0.2.0.dev202609211315",
    "scope": "user",
    "enabled": true,
    "installPath": "~/.claude/plugins/cache/apache-magpie/magpie-setup/0.2.0.dev202609211315",
    "installedAt": "2026-09-21T13:15:00Z",
    "lastUpdated": "2026-09-21T13:15:00Z"
  }
]
```

`claude plugin marketplace list --json` (marketplace registration):

```json
[
  {
    "name": "apache-magpie",
    "url": "apache/magpie",
    "installLocation": "~/.claude/plugins/marketplaces/apache-magpie"
  }
]
```

`cat ~/.claude/plugins/marketplaces/apache-magpie/.claude-plugin/marketplace.json` (readable — full git
clone, resolved successfully):

```json
{
  "plugins": [
    {"name": "magpie-pr-management", "version": "0.2.0.dev202609211315"},
    {"name": "magpie-setup", "version": "0.2.0.dev202609211315"},
    {"name": "magpie-agent-guard", "version": "0.2.0.dev202609211315"}
  ]
}
```
