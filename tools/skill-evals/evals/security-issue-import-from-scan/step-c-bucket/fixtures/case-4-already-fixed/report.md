<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

#### FINDING-014: Filter parameter does not escape LIKE wildcards

| Attribute | Value |
|-----------|-------|
| Severity | Low |
| Attacker Capability Required | An authenticated API user supplying a filter value. |
| Impact | Filter-semantics / minor information exposure. |

Description: the CONTAINS filter branch does not escape LIKE wildcards.

Fix status: this code was already fixed on the default branch in apache/<upstream>#67496, merged AFTER this scan's commit.
