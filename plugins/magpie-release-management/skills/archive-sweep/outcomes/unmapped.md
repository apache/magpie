<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Outcome — unmapped versions

A version in `unmapped` matched a loose train (a release line naming no single `N.x` train) or several trains.
Decide its train from `release-trains.md`, list it in that train's `"versions"` in `trains.json`, and re-run `retention` until `mapping_complete` is true;
`render` refuses while any version is unmapped.

A retention rule `keep` cannot express goes to the RM; nothing may drop the latest-of-each-train floor.
