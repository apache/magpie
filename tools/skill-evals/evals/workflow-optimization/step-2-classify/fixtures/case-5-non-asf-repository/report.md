<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Repository: `example-org/widget` (not an ASF repository, no `.asf.yaml`).

`.github/workflows/ci.yml`: `on: pull_request` and `push` to `release-*` branches only, in a single-package repository where every change touches `src/`, concurrency group cancelling pull request runs, one job `test` with `timeout-minutes: 20` and dependency caching, running 6 minutes.
No merge queue.

`.github/dependabot.yml`: only the `npm` ecosystem, weekly, grouped. No `github-actions` ecosystem.

`.github/workflows/nightly.yml`: `schedule: - cron: '0 3 * * *'`, a 4-minute job that succeeded on every run.

Open pull requests: 14, from 11 authors; nobody holds more than 2.
