<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

You are executing the database / query-correctness sub-check from Step 4
of the pr-management-code-review skill from the Apache Magpie framework.

Examine the added or modified code in the diff for query-correctness
problems. Raise a finding only for these patterns:

- **N+1 query**: a database query issued inside a loop where a single
  bulk/batch query would return the same data. Severity: `major`.
- **Unbounded result set**: a query that loads all rows with no limit,
  pagination, or filter, where the result feeds a response or is held in
  memory. Severity: `major`.

Do not raise a finding when the code already batches the query (a single
query using an `IN` / `any_` clause, an eager `selectinload` /
`joinedload`, or a bulk insert/update), or when the result set is bounded
(a `.limit()`, pagination, or a primary-key lookup). Refactors that do not
change query behaviour get no finding.

Category for every finding is "Database / query correctness". The `reason`
must name the specific problem (N+1 query or unbounded result set) and
recommend the fix (a single bulk/batch query, or adding a limit /
pagination).

## Output

Return ONLY valid JSON with this structure:
{
  "findings": [
    {
      "file": "<path>",
      "category": "Database / query correctness",
      "severity": "major" | "minor" | "none",
      "reason": "<one sentence>"
    }
  ]
}

`findings` is an empty array when there is nothing to flag.
Do not include any text outside the JSON object.
