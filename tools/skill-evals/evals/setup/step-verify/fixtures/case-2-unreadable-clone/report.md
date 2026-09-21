<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

`claude plugin list --json` (installed set):

```json
[
  {
    "id": "magpie-security",
    "version": "0.2.0",
    "scope": "user",
    "enabled": true,
    "installPath": "~/.claude/plugins/cache/apache-magpie/magpie-security/0.2.0",
    "installedAt": "2026-09-10T09:00:00Z",
    "lastUpdated": "2026-09-10T09:00:00Z"
  },
  {
    "id": "magpie-setup",
    "version": "0.2.0",
    "scope": "user",
    "enabled": true,
    "installPath": "~/.claude/plugins/cache/apache-magpie/magpie-setup/0.2.0",
    "installedAt": "2026-09-10T09:00:00Z",
    "lastUpdated": "2026-09-10T09:00:00Z"
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

Session is sandboxed (Claude Code, default filesystem policy).

Attempt to read
`~/.claude/plugins/marketplaces/apache-magpie/.claude-plugin/marketplace.json`:

```text
Error: EACCES: permission denied, open
'/Users/operator/.claude/plugins/marketplaces/apache-magpie/.claude-plugin/marketplace.json'
```

The sandbox's filesystem policy denies reads under
`~/.claude/plugins/` for this session.
