<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Scope: apache/example-repo, default branch only.

Command used:
```bash
zizmor --gh-token "$(gh auth token)" github:apache/example-repo
```

zizmor output (abbreviated):

```
apache/example-repo/.github/workflows/pr-check.yml:
  - [injection] job: test, step: "Run tests", line 34
    Unsafe interpolation of `${{ github.event.pull_request.head.ref }}` in a
    `run:` step. A PR author controlling the branch name can inject shell commands.
  - [excessive-permissions] job: release, line 12
    Workflow-level `permissions: write-all` is broader than the job requires.
    Only `contents: write` is used by the upload step.
```

Total: 1 injection finding (high), 1 excessive-permissions finding (medium).
