You are executing Step 6 (disposition pick) of the pr-management-code-review
skill from the Apache Steward framework.

Given the findings list and PR state, auto-pick one of three dispositions:

- APPROVE — green CI, no unresolved threads, zero blocking/major findings,
  at most a few nit/minor findings, no unanswered author questions.
- REQUEST_CHANGES — at least one blocking finding, OR two or more major
  findings, OR one major finding with an unanswered author question.
- COMMENT — everything else: minor-only findings, CI pending or failing,
  unresolved threads, or the maintainer wants to leave observations without
  gating the merge.

Note: CI failure or pending always prevents APPROVE (even with zero findings).
Unresolved threads always prevent APPROVE.

## Output

Return ONLY valid JSON with this structure:
{
  "disposition": "APPROVE" | "REQUEST_CHANGES" | "COMMENT",
  "reason": "<one sentence summarising the deciding factor>"
}

Do not include any text outside the JSON object.
