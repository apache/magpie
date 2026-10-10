<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# `gate:G4` — a workflow run awaits approval

The head SHA is in the `action_required` index: a workflow run is waiting for a maintainer to approve it, so real CI has not run on this head. A rollup that reads `SUCCESS` here is the bot checks talking.
Gate drops are reported as counts; read this only when the maintainer asks why a PR is not a candidate. [`quick-merge screen`](../../../../../tools/pr-management/README.md#quick-merge-screen--pr-management-quick-merge) applied the gate.
