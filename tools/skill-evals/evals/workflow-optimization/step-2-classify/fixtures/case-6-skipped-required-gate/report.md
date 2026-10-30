<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Repository: `apache/example-site` (ASF).

`.github/workflows/build.yml` runs on `pull_request`, on a weekly `schedule` (`41 3 * * 1`) and on `workflow_dispatch`, with a per-ref concurrency group cancelling superseded runs. Every job has `timeout-minutes`, and npm is cached by `actions/setup-node`.

- `changes` lists the pull request's changed files and decides whether the browser suite runs.
- `lint` runs `prek run --all-files`.
- `browser` calls a reusable workflow with a 12-entry Playwright matrix (`max-parallel: 12`, `timeout-minutes: 15`), skipped when `changes` finds no site change. A failed shard uploads its Playwright traces.
- `build` has `needs: [changes, lint, browser]` and `if: ${{ !failure() }}`.

`.asf.yaml` required status checks: `lint`, `build`. No merge queue.

`.github/dependabot.yml`: `npm` and `github-actions` ecosystems, weekly, grouped.

Jobs of the run for pull request #212:

```
  changes  0.1m  success
  lint  1.2m  success
  browser / shard 1..6, 8..12  3.0-4.8m  success
  browser / shard 7  15.0m  cancelled (timeout)
  build  -  skipped
```

The pull request was shown as mergeable and merged with `browser / shard 7` red.
It is the only failed browser job in the last 30 runs.
