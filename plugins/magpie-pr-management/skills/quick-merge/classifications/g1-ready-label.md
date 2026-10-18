<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# `gate:G1` — not carrying the ready label

The PR does not carry `ready for maintainer review`. The sweep searches for that label, so this is a defensive re-check: the label came off between the search and the screen.
Gate drops are reported as counts; read this only when the maintainer asks why a PR is not a candidate. [`quick-merge screen`](../../../../../tools/pr-management/README.md#quick-merge-screen--pr-management-quick-merge) applied the gate.
