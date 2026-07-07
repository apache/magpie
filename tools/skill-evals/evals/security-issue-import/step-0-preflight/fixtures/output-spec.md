<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Eval output format

You are executing Step 0 item 5 (disclosure governance config read) in
isolation. The contents of `security-intake-config.md` — or a message
indicating the file is absent — are supplied in the user turn. Load the
`disclosure_governance.reporter_acknowledgement_model` and
`disclosure_governance.window_days` values (or their ASF defaults when the
file or block is absent) and return ONLY valid JSON with these fields:

```json
{
  "reporter_acknowledgement_model": "manual | auto | none",
  "window_days": <int>,
  "config_file_found": <bool>
}
```

Do not include any text outside the JSON object.
