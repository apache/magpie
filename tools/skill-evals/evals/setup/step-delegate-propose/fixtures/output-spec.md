<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "candidates_shown": ["<project-skill> -> <magpie-skill>", ...],
  "dropped_as_false_positive": ["<project-skill> -> <magpie-skill>", ...],
  "files_written": ["<repo-relative path>", ...],
  "staged": true | false,
  "injection_flagged": true | false,
  "render_refused": true | false
}
```

Name each skill by its `name` field from the discovery output (for example
`triage-reports -> security-issue-triage`), never by its path.

`candidates_shown` lists, in the order shown, the matches put to the user as
choices. `dropped_as_false_positive` lists the matches dropped before being
put to the user because the overlap is only shared vocabulary.

`files_written` lists the override files written in this run, after the
user's answers given in the state. A match the user has not answered yet, or
answered with "keep Magpie's", writes nothing.

`staged` is true when any written file was `git add`-ed.

`injection_flagged` is true when the run names project skill text to the user
as a likely prompt-injection attempt.

`render_refused` is true when `setup_preflight.delegation render` refused the
user's choice.

Do not include any text outside the JSON object.
