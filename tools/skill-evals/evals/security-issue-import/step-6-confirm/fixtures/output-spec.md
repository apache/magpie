<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Eval output format

You are executing Step 6 (user confirmation) in isolation. The proposal list
and the user's confirmation reply are provided in the user turn as mock data.
Parse the reply and return ONLY valid JSON with these fields:

```json
{
  "action": "import" | "cancel" | "ambiguous",
  "import_items": [<int>, ...],
  "skip_items": [<int>, ...],
  "reject_with_canned": [{"item": <int>, "canned_name": "<string>"}],
  "edits": [{"item": <int>, "instruction": "<string>"}],
  "ambiguous_tokens": ["<token>", ...]
}
```

`import_items` lists every candidate that will have a tracker created.
A bare confirmation such as `go`, `yes`, `ok`, or `all` means import every
IMPORTABLE candidate. A candidate flagged `no import` (for example an
automated-scanner entry) is never importable: leave it out of `import_items`.
`skip_items` holds ONLY candidates the user explicitly chose to skip. A
`no import` candidate the user never mentioned does NOT go in `skip_items`,
`reject_with_canned`, or `edits`; it simply does not appear anywhere.
When `action` is `"cancel"`, all lists are empty.
`ambiguous_tokens` is empty unless `action` is `"ambiguous"`; otherwise it is
an empty array.

Do not include any text outside the JSON object.
