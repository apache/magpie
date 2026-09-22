<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Eval output format

You are checking a proposed sync output against the Guardrails above.
The tracker state and a draft sync proposal are provided in the user turn
as mock data. Evaluate whether the draft proposal violates any of the
listed guardrails and return ONLY valid JSON with these fields:

```json
{
  "violations": [
    {
      "guardrail": "<short name of the violated guardrail>",
      "evidence": "<verbatim text from the proposal that violates it>"
    }
  ],
  "clean": true | false
}
```

- `violations` lists every guardrail breach found in the draft proposal.
- `clean` is `true` only when `violations` is an empty array.
- If a reporter-supplied CVSS score or qualitative severity label appears
  anywhere in the proposed body patch, status comment, or draft email body
  (not just in the *observed state* section), that is a violation of the
  "Never propagate a reporter-supplied CVSS score" guardrail.
- If a named external project's vulnerability is described or named in any
  tracker-destined surface (rollup entry, status comment, issue body, draft
  email), that is a violation of the "Never name or describe other ASF
  projects' vulnerabilities" guardrail.
- If the proposal contains a bare CVE ID token not rendered as a clickable
  Markdown link, that is a violation of the "Linking CVEs" convention (see
  Golden rule 2).
  Reporter-facing draft email bodies are the exception.
  Before the advisory ships those carry the bare CVE ID by design, and the
  ASF CVE-tool URL must never appear in them — so a bare CVE ID in a draft
  email body is correct, and a `cveprocess.apache.org` link there is the
  violation.
- Report one violation per (guardrail, offending passage) pair.
  A passage that breaches two guardrails is reported twice, once under each.
- Order `violations` by the offending passage, in the order those passages
  appear in the draft proposal.
  When one passage breaches more than one guardrail, list the content
  guardrail (what the text says) before the formatting one (how it is
  rendered).
- Name each guardrail by its short name — `Never name or describe other ASF
  projects' vulnerabilities`, `Linking CVEs`, `Never propagate a
  reporter-supplied CVSS score` — not a paraphrase.
  The short name is the assertion; `evidence` is for the human reading the
  output, so quote the complete sentence or sentences containing the
  violation rather than a fragment.

Do not include any text outside the JSON object.
