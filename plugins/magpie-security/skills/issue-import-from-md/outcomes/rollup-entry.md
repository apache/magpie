<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# security-issue-import-from-md — the rollup entry

From Step 3e; `security-management issue-import-from-md render-rollup` renders it, every value code-quoted.

The first entry on the tracker's status rollup ([`tools/github/status-rollup.md`](../../../../../tools/github/status-rollup.md)), with the action label `Import from markdown (<basename>, finding <K>/<N>)`.
Draft only the entry body;
Step 5d's tool writes the `<details>` envelope and creates the rollup with its marker line:

```markdown
**Imported from markdown file `<basename>` on <YYYY-MM-DD>** (severity: `<severity>`, category: `<category>`).

This tracker was deliberately opened by the security team from a batch findings file. The validity of the report has **not** been assessed yet — the tracker landed in the `Needs triage` column accordingly. Standard Step 3 discussion applies.

**Source:** `<basename>` (finding `<K>` of `<N>` in the file).
**Location reference:** <location_url>
**Severity (from source):** `<severity>` (informational; CVSS scoring happens at allocation).
**Category (from source):** `<category>` (informational; CWE assignment happens at allocation).
```

Start every body line at column 0 — leading spaces inside the `<details>`
envelope render as a code block.
