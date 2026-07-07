<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Eval task

You are evaluating the **disposition-bucketing** step (Step C) of the `security-issue-import-from-scan` skill.

A single scan finding's evidence is provided below (the per-finding evidence block, plus any fix-status note). Classify it into exactly one disposition bucket, decide whether it creates a `<tracker>` issue, and give the one-line grounding.

Return a JSON object with exactly these fields:

```json
{
  "id": "<finding id>",
  "disposition_bucket": "PR-worth" | "import-as-tracker" | "defense-in-depth" | "by-design" | "duplicate" | "already-fixed",
  "creates_tracker": true | false,
  "grounding": "<one line: the Security-Model section / precedent tracker / fixing PR that grounds the call>"
}
```

Field rules:
- `creates_tracker` is `true` **only** when `disposition_bucket` is `import-as-tracker`. PR-worth, defense-in-depth, by-design, duplicate, and already-fixed are all `false` — a scanner finding below the CVE bar never creates a tracker.
- `import-as-tracker` requires a genuine Security-Model violation reachable by an **in-scope (non-trusted-role)** attacker. A finding whose attacker is a trusted role (connection-configuration user, DAG author, operator) or whose precondition is the deployment manager's responsibility is `by-design` (or `defense-in-depth`), **regardless of the scanner's severity label**.
- A finding already fixed on the default branch since the scan's commit is `already-fixed`.
- `grounding` must be non-empty.
