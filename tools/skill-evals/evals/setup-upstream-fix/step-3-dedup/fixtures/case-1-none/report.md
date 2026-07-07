<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Quirk: a helper in `tools/foo-adapter` mishandles empty input and raises.
Searches run:
- `gh search issues --repo apache/magpie --state all "foo-adapter empty input"` → 0 results.
- `gh search prs --repo apache/magpie --state all "foo-adapter empty"` → 0 results.
No open or closed issue or PR mentions this defect.
