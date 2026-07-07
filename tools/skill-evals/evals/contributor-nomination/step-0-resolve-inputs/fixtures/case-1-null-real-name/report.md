<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Login argument: ghostdev
Target: committer
Upstream: apache/example-project

gh api users/ghostdev --jq '.name'
(null)

gh api users/ghostdev --jq '.company'
Widgets Inc

Nominator confirmed employer: yes — "They work at Widgets Inc."
