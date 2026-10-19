<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

The user runs `/magpie-setup config` in `~/code/foo-private`, a private Git repository, and picks the `local-files` tracker backend with `tracker.local.root: security`. The access check is done: the user said only the security team can read the repository, and the descriptor was written with `detect --write --access-restricted`.

`magpie-local-tracker --root security detect` printed:

```json
{
  "summary": "<root>/SEC-0001/issue.md; metadata as front-matter; fields as '### <Field>' sections; comments in comments.md",
  "reports_found": 9,
  "field_layout": {
    "layout": "default",
    "description": "fields are level-3 heading sections",
    "sample_field_names": [
      "Affected versions",
      "Severity",
      "Summary"
    ]
  },
  "notes": []
}
```
