<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Harness: Claude Code, running inside the sandbox, on an adopted marketplace install.
The run started from the session-start notice, so the version has already moved; this is Gather.

`python3 -P -m setup_preflight.upgrade gather` printed:

```json
{
  "configured": true,
  "install": "marketplace",
  "listing_known": true,
  "project_findings": [],
  "shadowed": [],
  "layers": {
    "adopted": true,
    "personal_dir": "/work/project/.apache-magpie-local",
    "personal_dir_exists": true,
    "personal_layers": [
      "/work/project/.apache-magpie-local"
    ],
    "config_layers": [
      "/work/project/.apache-magpie-local",
      "/work/project/.apache-magpie-overrides"
    ],
    "legacy_local_dir": null,
    "main_worktree": null
  },
  "isolated": {
    "state": "in-use",
    "recorded": "sha256:3f1c9a0d2b7e4c51",
    "current": "sha256:3f1c9a0d2b7e4c51",
    "changed": false,
    "updated_at": "2026-11-12",
    "interval_days": 7,
    "due": false,
    "attention": false
  }
}
```
