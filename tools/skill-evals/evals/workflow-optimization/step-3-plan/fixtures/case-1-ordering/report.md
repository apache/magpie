<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Findings for `apache/example-parser`:

- `P0-setup-failure` — `license.yml:18`, Python 3.8 missing on the current image; 41 of 63 runs failed.
- `P1-tiny-jobs` — `rust.yml`, five jobs under two minutes; all are required checks.
- `P1-matrix-on-pr` — `rust.yml:70`, beta and nightly toolchains on every pull request.
- `P2-timeout` — no `timeout-minutes` in any job.
- `P3-pr-cap` — 130 open pull requests; one author without write access holds 37.

The maintainer asked: "Prepare a plan to improve our workflows."
