<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Scope: apache/example-repo, default branch only.

Command used:
```bash
zizmor --gh-token "$(gh auth token)" --config zizmor-unpinned-only.yml github:apache/example-repo
```

zizmor output (abbreviated):

```
apache/example-repo/.github/workflows/ci.yml:
  - [unpinned-uses] job: build, step: "Checkout", line 8
    `actions/checkout@v4` uses a floating tag. Pin to a commit SHA.
  - [unpinned-uses] job: build, step: "Setup Python", line 12
    `actions/setup-python@v5` uses a floating tag. Pin to a commit SHA.
  - [unpinned-uses] job: build, step: "Upload artifact", line 28
    `actions/upload-artifact@v4` uses a floating tag. Pin to a commit SHA.
```

Total: 0 injection, 0 fork-secrets, 0 excessive-permissions, 3 unpinned-actions findings (medium).
