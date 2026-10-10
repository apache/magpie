<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# `duplicate` — major

[`stack-review findings`](../../../../../tools/pr-management/README.md) reports it from the ledger detectors: the same release note edited in several layers, a generated or lock file regenerated in several layers (regenerate once, in the layer that changes its source), or a lock file changed in a layer whose manifest changed only elsewhere. `layers` names every layer involved.
