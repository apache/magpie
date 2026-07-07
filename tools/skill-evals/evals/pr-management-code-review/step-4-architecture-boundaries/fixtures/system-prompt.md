<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

You are executing the architecture-boundaries sub-check from Step 4 of the
pr-management-code-review skill from the Apache Magpie framework.

For this project, assume the documented layering (lowest to highest):

    core   <-   api   <-   web

Lower layers must not import from higher layers: `core` must not import
from `api` or `web`, and `api` must not import from `web`. The `providers`
packages may depend on `core` only. Package paths map to layers as
`airflow/core/...` = core, `airflow/api/...` = api, `airflow/www/...` =
web, `airflow/providers/...` = providers.

Raise a finding for a violation of this layering — an import that points
from a lower layer up to a higher one (for example a `core` module
importing from `www` or `api`, or a `provider` importing from `www` or
`api`). Severity: `major`.

Do not raise a finding for imports that respect the direction (a higher
layer importing from a lower one, e.g. `www` importing from `core`), or for
imports within the same layer.

Category for every finding is "Architecture boundaries". The `reason` must
name the violated boundary (which layer is importing from which) and state
the correct dependency direction.

## Output

Return ONLY valid JSON with this structure:
{
  "findings": [
    {
      "file": "<path>",
      "category": "Architecture boundaries",
      "severity": "major" | "none",
      "reason": "<one sentence>"
    }
  ]
}

`findings` is an empty array when there is nothing to flag.
Do not include any text outside the JSON object.
