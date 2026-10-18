<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Entered from `setup config` step 3f. The project has **not** adopted Magpie;
the personal layer is `.git/apache-magpie/`, where the checker is installed.

`setup_preflight.discovery` printed:

```json
{"project_skills": [{"name": "triage-reports", "path": ".claude/skills/triage-reports/SKILL.md"}],
 "matches": [{"project_skill": {"name": "triage-reports", "path": ".claude/skills/triage-reports/SKILL.md"},
   "magpie_skill": "security-issue-triage", "score": 0.58,
   "signals": {"name": 0.5, "text": 0.71, "headings": 0.46},
   "shared_terms": ["classify", "report", "security", "team", "triage"],
   "draft_merge": [{"kind": "magpie", "ref": "Step 1 — Gather the tracker state"},
                   {"kind": "project", "ref": "Reproduce locally in the lab"},
                   {"kind": "magpie", "ref": "Step 2 — Classify the disposition"},
                   {"kind": "magpie", "ref": "Step 3 — Draft the triage-proposal comment"}],
   "suggested": "merge"}]}
```

The project skill's description: "Triage new security reports for the
security team, reproduce them in our lab, and classify them."

The user answered **keep Magpie's** for the only match.
