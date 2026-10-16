<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Project: Apache Quokka (fictional), whose code lives in Subversion. `<project-config>/project.md` → *Tools enabled → Source control*: `asf-svn`.

The working copy of `trunk` is at `/home/dev/quokka-trunk`. The command

`uv run --project <framework>/tools/vcs magpie-vcs -C /home/dev/quokka-trunk fix-flow --declared asf-svn`

exited 0 and printed:

```json
{"backend": "svn", "declared": "asf-svn", "detected": "svn", "distributed": false, "flow": "patch-then-commit", "publishes_at": ["new-branch", "commit"]}
```

The tracker issue asks for "a PR as usual".
