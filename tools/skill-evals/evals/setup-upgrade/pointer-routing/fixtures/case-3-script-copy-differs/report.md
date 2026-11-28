<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

The harness is Claude Code, and the version has already moved, so the run is at Gather. The gather summary printed:

```json
{"configured": true, "install": "local", "listing_known": true, "project_findings": [], "shadowed": [],
 "isolated": {"state": "in-use", "attention": true}}
```

The isolated-setup catalogues report that the user-scope copy `~/.claude/scripts/sandbox-add-project-root.sh` differs from its framework source; it is not yet known whether it is an older shipped version or carries local edits.
