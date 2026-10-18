<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# `gate:G2` — real CI not green

The rollup is not `SUCCESS`, or it is `SUCCESS` with no real-CI context — only bot checks such as `Mergeable`, `DCO`, `boring-cyborg`, which succeed unconditionally and pull the rollup to green before real CI is allowed to run.
The real-CI patterns are `real_ci_patterns` in the shared `pr-management-config.md` ([shared rules](../../../../../tools/pr-management/README.md#shared-rules)).
Gate drops are reported as counts; read this only when the maintainer asks why a PR is not a candidate. [`quick-merge screen`](../../../../../tools/pr-management/README.md#quick-merge-screen--pr-management-quick-merge) applied the gate.
