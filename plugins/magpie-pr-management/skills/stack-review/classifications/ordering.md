<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# `ordering`

A layer that is not green on its own, or that only works once a later layer lands.

- **Removed definition still used at the layer's own head** — [`stack-review findings`](../../../../../tools/pr-management/README.md) lists it as a `blocking` finding with a `verify` note: read the quoted line and keep the finding only if it is a real reference (import, call, attribute), not a string, a doc or an unrelated symbol of the same name. Quote the verified line in the finding.
- **A name removed below, referenced at a later head** — a *candidate*. Check layer j's head with `git -C <clone> show` / `git grep`: when the definition is absent there, the use was reintroduced after its removal — `blocking` ordering, layers = the removing and the reintroducing layer; when j re-adds the definition (or the hit is another symbol), it is an observation.
- **A construct above the floor its head declares** — a *candidate* from `floors.json`: a layer below the floor move uses something the old floor lacks. Grep for the constructs the new floor introduced (for a language bump, the release notes of the versions in between; for a dependency floor, the APIs the stack starts calling), quote the line at that layer's head, and record a `major` finding whose `layers` are the whole merge unit (*layers a–b together*).

`seams` only extracts column-0 definitions and deleted modules: a method removed from a class is invisible to it, which is what the Step 4 reading is for.
