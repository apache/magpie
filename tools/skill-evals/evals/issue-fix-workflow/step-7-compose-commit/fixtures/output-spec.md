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

These fields describe the commit message exactly as drafted in the report; do not rewrite the subject or body. Report `security_language_present: true` when the drafted subject or body still contains security-framing terms so the caller can require a scrub.
`body_ok` is true when the message is structurally sound per convention: the subject carries the tracker key prefix (e.g. `AIRFLOW-9999:`) and the body is a short paragraph explaining the cause and fix. It is independent of the security-language scrub, so a message that still contains security framing is still `body_ok: true` (that concern is reported separately via `security_language_present`); set it false only for a structural problem such as a missing tracker key prefix.
`security_language_present` is true if the subject or body contains: "CVE", "vulnerability", "security fix", "security patch", "exploit", "arbitrary code execution", or similar security-framing terms.
`trailer_key` is the key of the AI-assistance trailer if present, null otherwise.
Do not include any text outside the JSON object.
