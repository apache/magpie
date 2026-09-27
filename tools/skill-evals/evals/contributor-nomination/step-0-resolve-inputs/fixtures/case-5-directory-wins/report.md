<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Login argument: asmith-dev
Target: pmc
Upstream: apache/example-project

gh api users/asmith-dev --jq '.name'
Al S.

Nominator: Apache ID is "asmith".
mcp__apache-projects__get_person("asmith") → { "id": "asmith", "name": "Alice Smith" }

gh api users/asmith-dev --jq '.company'
(null)

Nominator confirmed employer: unknown.
