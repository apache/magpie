<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Harness: Claude Code, running inside the sandbox, on an adopted marketplace install.
The run started from the session-start notice, so the version has already moved; this is Gather.

`python3 -P -m setup_preflight.upgrade gather` failed:

```text
usage: setup_preflight.upgrade [-h] [--project-root PROJECT_ROOT] [--version VERSION] {status,record}
setup_preflight.upgrade: error: argument action: invalid choice: 'gather' (choose from 'status', 'record')
```

`python3 -P -m setup_preflight.isolated configured` printed `{"configured": true}`.
