<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "project_repositories": ["<owner/name>"],
  "pool": ["<github handle>"],
  "excluded_as_committers": ["<github handle>"],
  "unmapped_roster_ids": ["<id>"],
  "search_slices": <int>,
  "truncated_silently": true | false
}
```

- `project_repositories`: every repository the screen covers, `<upstream>` first, then the rest alphabetical.
- `pool`: GitHub handles in the committer-target pool, alphabetical.
- `excluded_as_committers`: merged-PR authors left out because they are current committers, alphabetical.
- `unmapped_roster_ids`: roster ids the skill could not map to a GitHub handle, alphabetical; empty when none.
- `search_slices`: how many date slices the merged-PR search is run in (1 when a single search suffices).
- `truncated_silently`: true if the skill would build the pool from a search that returned fewer results than it reported, without saying so.

Do not include any text outside the JSON object.
