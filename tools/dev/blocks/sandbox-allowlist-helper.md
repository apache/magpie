<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

```bash
~/.claude/scripts/sandbox-add-project-root.sh --all-worktrees
```

Surface the bypass proposal to the operator *before*
invoking — name the helper, name the target files, and
confirm. The reason for the bypass is *"writing
project-local sandbox-allowlist entries (issue #197 fix)"*.
The bypass triggers `sandbox-bypass-warn.sh`'s bold-red
banner as a backstop, but the agent must propose the bypass
first; do not silently approve.
