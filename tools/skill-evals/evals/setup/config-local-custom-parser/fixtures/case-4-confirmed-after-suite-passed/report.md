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

Earlier in this run the agent wrote `.apache-magpie-overrides/tools/local-tracker/parsers/key-value.py` from the template with synthetic sample values, and `key-value.cases.jsonl` beside it. The conformance suite passed on it (generic properties and all 9 fixtures). The agent showed its SHA-256, `3f1c0a9e5b7d2e4f6a8c0b1d3e5f7a9c2b4d6e8f0a1c3e5b7d9f1a3c5e7b9d1f`, handed the user the `trust-parser` command to run in their own terminal, and offered to contribute the parser upstream. The user answered: "I ran trust-parser and confirmed the hash; it printed `\"parser_loads\": true`. Not upstreaming it for now."
