<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Repository: `apache/example-site` (ASF). The maintainer asks: "Should we move to self-hosted RunsOn runners to fix our queue times?"

`.github/workflows/build.yml`: one job, `build`, runs the site build in a Docker container (`docker compose run site-build`) on `pull_request` and on `push` to `main` (no merge queue), `timeout-minutes: 10`, `actions/setup-node` with `cache: npm`, concurrency group cancelling pull request runs.
Scheduled jobs: none.

`.github/dependabot.yml`: `npm` and `github-actions`, weekly, grouped.

Job timings: `build  1.8m  35.0m`.
Run summary: `25 build [pull_request]`, `9 build [push]`, nothing failing repeatedly.
