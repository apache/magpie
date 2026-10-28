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

`overall` is `"pass"` when no check is ⚠ or ✗, `"warn"` when there are ⚠ but no ✗,
`"fail"` when any check is ✗.
An `inconclusive` or `unchecked` check counts as neither ⚠ nor ✗ for `overall`, but still gets a `follow_up` entry.
`follow_up` is an empty array when every check is ✓.
Give one entry per distinct `skill`: when several checks point at the same skill or command, merge their reasons into that entry.
A finding whose remedy is the operator's own decision or edit, with no skill or command of its own, goes into the reason of the entry for the same check rather than an entry of its own.
Order the entries by urgency: a hard fail that stops the run (claude-code below its `min_version` floor) first, then the rest in the order `remediation.md` lists their checks.
`skill` is the skill slug (e.g. `"setup-isolated-setup-install"`) or
`"sandbox-add-project-root.sh --all-worktrees"` for the check-8 helper.
Do not include any text outside the JSON object.
