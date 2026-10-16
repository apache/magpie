<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# security-issue-import-from-scan — the triage report

From Step D, as the skill carried it; `security-management issue-import-from-scan render-report` lays it out.

Emit one markdown report per scan: a one-line distribution, then a
per-bucket section with a row per finding (id, title, severity, grounding
citation, recommended action) and clickable references.

**Publish the report as a secret gist (default)** and surface the URL —
`gh gist create --desc "<title>" <report.md>` (secret is the default; do
**not** pass `--public`). The gist is the portable, shareable artifact.

**Cross-scan processing report (multi-scan runs).** When more than one scan is processed, also produce a cross-scan **processing report**:
a per-scan outcome table, an aggregate disposition breakdown **with percentages**, a severity-vs-disposition analysis (how many flagged Medium/High findings survived triage as real vulnerabilities), and a short *"what the scanner is / isn't good for"* assessment.
This is what goes to the gist and the optional report-back PR.
