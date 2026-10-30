<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Repository: `apache/example-lib` (ASF).

`.github/workflows/license.yml`:

```yaml
on:
  push:
    branches: [main]
  pull_request:
  merge_group:
concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: ${{ github.event_name == 'pull_request' }}
jobs:
  rat:
    name: Release Audit Tool (RAT)
    runs-on: ubuntu-slim
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: 3.8
      - run: ./dev/release/run-rat.sh .
```

`.asf.yaml`: merge queue enabled on `main` (`grouping_strategy: ALLGREEN`); required status checks: `Release Audit Tool (RAT)`.

`.github/dependabot.yml`: `github-actions` ecosystem, weekly, grouped.

Run summary (7 days):

```
   40  license  [pull_request]
   12  license  [merge_group]
   11  license  [push]
failing repeatedly (failed / finished):
  41/63  license
```

`gh run view --log-failed` on a failed run: `setup-python`: `The version '3.8' with architecture 'x64' was not found for Ubuntu 26.04.`
