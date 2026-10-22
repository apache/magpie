<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Repository: `apache/example-parser` (ASF).

`.github/workflows/rust.yml` has jobs `clippy`, `check`, `docs`, `bench-clippy` and `test`, each compiling the crate with its own checkout and toolchain setup, all with `timeout-minutes: 15`, triggered on `pull_request` and on `push` to `branch-*` only, with a per-ref concurrency group cancelling pull request runs, and `Swatinem/rust-cache` in every job.
No path filters; most pull requests change only `src/`.

`.asf.yaml` required status checks: `clippy`, `check`, `docs`, `bench-clippy`, `test`. No merge queue.

`.github/dependabot.yml`: `cargo` and `github-actions` ecosystems, weekly, grouped.

Job timings for a recent pull request run:

```
  clippy  1.1m  52.3m  <- short
  check  0.9m  52.1m  <- short
  docs  0.8m  52.4m  <- short
  bench-clippy  1.0m  52.2m  <- short
  test  6.5m  52.0m
jobs: 5, median run 1.0m, short (<2m): 4
```
