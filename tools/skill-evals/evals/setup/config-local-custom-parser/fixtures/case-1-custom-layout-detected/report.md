<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

The user runs `/magpie-setup config` in `~/code/foo-private`, a private Git repository, and picks the `local-files` tracker backend with `tracker.local.root: security`. The access check is done: the user said only the security team can read the repository, and the descriptor was written with `detect --write --access-restricted`.

`magpie-local-tracker --root security detect` printed:

```json
{
  "summary": "<root>/SEC-0001/issue.md; metadata as front-matter; fields as '### <Field>' sections; comments in comments.md",
  "reports_found": 14,
  "field_layout": {
    "layout": "custom",
    "description": "fields are `Name: value` lines at column 0; a value runs to the next such line",
    "sample_field_names": ["Affected versions", "CVE", "Reporter", "Severity", "Summary"]
  },
  "notes": ["reports keep their fields as `Name: value` lines, not heading sections: the default parser reads no fields from them; generate a local parser with `setup config` before using the tracker"]
}
```

Asked whether to generate a parser for this layout, the user answered: "Yes, generate one." The conformance suite has not been run yet.
