<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Project: Apache Quokka (fictional). `<project-config>/project.md` → *Tools enabled → Source control*: `github`.

The working copy is resolved at `/home/dev/quokka`. The command

`uv run --project <framework>/tools/vcs magpie-vcs -C /home/dev/quokka fix-flow --declared github`

exited 0 and printed:

```json
{"backend": "git", "declared": "github", "detected": "git", "distributed": true, "flow": "pull-request", "publishes_at": ["push"]}
```
