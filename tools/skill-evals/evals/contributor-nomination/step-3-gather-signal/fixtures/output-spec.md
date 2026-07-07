<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "off_github_fields_recorded": ["<field>", ...],
  "project_bar_question_asked": true | false,
  "project_bar_source": "nominator" | "config" | "none",
  "community_interaction_recorded": true | false,
  "employer_context_recorded": true | false,
  "candidate_asked": true | false
}
```

- `off_github_fields_recorded`: list of off-GitHub tracks for which the nominator provided non-blank input (any of: "mailing-list", "documentation", "testing", "user-support", "talks-writing", "release-management", "mentoring", "other")
- `project_bar_question_asked`: true when the skill asked the nominator the project-bar question in this step
- `project_bar_source`: "nominator" if the bar came from the nominator's answer, "config" if it came from contributor-nomination-config.md (question skipped), "none" if no bar was recorded
- `community_interaction_recorded`: true when the nominator provided community-interaction input (even if "not assessed")
- `employer_context_recorded`: true when the employer-concentration question was asked and an answer (including "unknown") was recorded
- `candidate_asked`: true if the skill asked the candidate directly for any information — this must always be false; nominations are private

Do not include any text outside the JSON object.
