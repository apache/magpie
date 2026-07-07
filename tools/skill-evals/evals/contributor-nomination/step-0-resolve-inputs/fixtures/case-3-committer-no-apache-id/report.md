<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Login argument: newcontrib
Target: committer
Upstream: apache/example-project

gh api users/newcontrib --jq '.name'
"Casey Bloom"

gh api users/newcontrib --jq '.company'
(empty string)

Nominator confirmed employer: "I'm not sure where they work — their GitHub profile doesn't say."
