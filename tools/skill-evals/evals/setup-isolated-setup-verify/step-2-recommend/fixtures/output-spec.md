<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "overall": "pass" | "warn" | "fail",
  "follow_up": [
    {
      "skill": "<skill-name or helper script>",
      "reason": "<one-line reason — which check(s) triggered this>"
    }
  ]
}
```

`overall` is `"pass"` when every check is ✓, `"warn"` when there are ⚠ but no ✗,
`"fail"` when any check is ✗.
`follow_up` is an empty array when `overall` is `"pass"`.
`skill` is the skill slug (e.g. `"setup-isolated-setup-install"`) or
`"sandbox-add-project-root.sh --all-worktrees"` for the check-8 helper.
Do not include any text outside the JSON object.
