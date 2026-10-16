<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# security-issue-import-from-scan — per-source report destinations

From *Inputs — sources*.

Each scan's per-source report destination is resolved below; the gist
and the optional report-back PR (Step F) are produced *in addition*.

| Per-scan source | How to read it | Per-scan report destination |
|---|---|---|
| A **GitHub issue** (e.g. `<scan-repo>#NN`) | Read the issue body + comments for the scan report folder URL(s) | Propose posting the triage report **as a comment on that issue** (draft → confirm → post) |
| A **report folder** (local path or tree URL) | Read it via the scan-format adapter | Write the report to **`issue_analysis.md`** in that folder (read-only remote tree → local copy, or fold into the report-back PR) |
