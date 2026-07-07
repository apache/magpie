<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Login argument: powercontrib
Target: pmc
Upstream: apache/example-project

gh api users/powercontrib --jq '.name'
"Taylor Wu"

gh api users/powercontrib --jq '.company'
BigSystems

Nominator confirmed employer: yes — "BigSystems, that's correct."

Apache ID supplied by nominator: twu99

Verification: GET https://people.apache.org/committer.cgi?twu99
HTTP 404 — not found
