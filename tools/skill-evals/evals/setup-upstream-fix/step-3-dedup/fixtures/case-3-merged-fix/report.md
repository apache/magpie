<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Quirk: the config path was left stale after a tool rename.
Searches run:
- `gh search prs --repo apache/magpie --state all "legacy config path rename"` → 1 MERGED PR
  #725, merged last week, which added exactly this fallback.
The fix is already on `main`; the local snapshot simply predates it.
