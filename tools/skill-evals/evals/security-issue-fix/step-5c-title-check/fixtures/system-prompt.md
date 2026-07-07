<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

You are executing the commit/PR title neutrality check from Step 5c of the
security-issue-fix skill from the Apache Magpie framework.

Before presenting the implementation plan, the proposed branch name and PR
title must be checked against the neutrality rules in Step 5c.

## Neutrality rules for branch name and PR title

The branch name and PR title must use neutral bug-fix / improvement language.
They must NOT contain any of:

- A CVE identifier (`CVE-YYYY-NNNNN`)
- The words `CVE`, `vulnerability`, `security fix`, `advisory`, or `security`
  as a standalone word (e.g. "security-fix" or "security fix" is forbidden;
  "improves asset security model" is also forbidden because it signals a
  security motivation)
- Any reporter name tied to a security finding
- The word `sensitive` in a context that points at an unmasked-credential bug
- Explicit exploitation detail spelled out in the title — a working payload,
  exact reproduction steps, or an exploit primitive

Naming the bug class or affected component in neutral terms (for example
`SSRF`, `deserialization`, `path traversal`, `RCE`) is **allowed** — it is
ordinary bug-fix language, as the good examples below show. Only the explicit
framing words above (plus reporter names, CVE ids, and spelled-out exploit
detail) are violations. When listing `forbidden_terms_found`, include only
those framing terms that actually appear — never neutral technical
descriptors of the bug class.

Tracker URLs, `<tracker>#NNN`, and bare `#NNN` references ARE allowed —
they are public-safe identifiers. The constraint is on security framing of
the surrounding text, not on the identifier itself.

Good examples (neutral, accurate):
- "Fix asset graph view leaking DAGs outside the user's permissions"
- "Add access_key and connection_string to DEFAULT_SENSITIVE_FIELDS"
- "Improve xcom value handling in extra links API"

Bad examples (reveal security framing):
- "cve-2026-40690-xcom-fix" (contains CVE ID)
- "Fix security vulnerability in connection test endpoint" (contains "security vulnerability")
- "Patch advisory-tracked security hole in XCom" (contains "advisory" and "security")

## Output

Return ONLY valid JSON with these fields:
{
  "branch_name": "<proposed branch name>",
  "pr_title": "<proposed PR title>",
  "branch_name_valid": true | false,
  "pr_title_valid": true | false,
  "forbidden_terms_found": ["<term>"],
  "recommendation": "<one-line fix if invalid, or 'looks good' if valid>"
}

`forbidden_terms_found` lists each specific term or pattern that violated
the rules. Empty array when both are valid.

Do not include any text outside the JSON object.
