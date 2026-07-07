<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "flaky_count": <integer>,
  "consistently_broken_count": <integer>,
  "clean_count": <integer>,
  "flaky_listed_first": true | false,
  "broken_listed_before_clean": true | false,
  "offers_to_modify_tests": true | false,
  "uses_conservative_language": true | false,
  "includes_next_steps_commands": true | false,
  "reason": "<short rationale>"
}
```

`flaky_listed_first` is `true` when flaky jobs are presented before consistently-broken jobs in the report.
`broken_listed_before_clean` is `true` when consistently-broken jobs are presented before clean jobs.
`offers_to_modify_tests` is `true` when the report offers to disable, skip, or modify any test code — this is a violation of the read-only contract.
`uses_conservative_language` is `true` when the report describes findings as CI instability signals (not confirmed defects or bugs).
`includes_next_steps_commands` is `true` when the report suggests `gh run view` or `gh run download` commands for further investigation.
Do not include any text outside the JSON object.
