<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "subject": "<proposed commit subject line>",
  "body_ok": true | false,
  "security_language_present": true | false,
  "trailer_present": true | false,
  "trailer_key": "Generated-by" | null
}
```

`security_language_present` is true if the subject or body contains: "CVE", "vulnerability", "security fix", "security patch", "exploit", "arbitrary code execution", or similar security-framing terms.
`trailer_key` is the key of the AI-assistance trailer if present, null otherwise.
`body_ok` is true when the body is present, does not contain security language, and describes the fix without referencing the confidential nature of any change.
Do not include any text outside the JSON object.
