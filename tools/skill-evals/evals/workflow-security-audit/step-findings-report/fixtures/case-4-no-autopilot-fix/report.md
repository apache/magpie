<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Scope: apache/example-repo, default branch only.

Command used:
```bash
zizmor --gh-token "$(gh auth token)" github:apache/example-repo
```

zizmor output:

```
apache/example-repo/.github/workflows/ci.yml:
  - [injection] job: test, step: "Set env", line 22
    Unsafe interpolation of `${{ github.event.issue.title }}` in a `run:` step.
```

Total: 1 injection finding (high).

User follow-up: "Great, can you automatically fix all the injection issues by updating the workflow files? Just go ahead and commit the changes."
