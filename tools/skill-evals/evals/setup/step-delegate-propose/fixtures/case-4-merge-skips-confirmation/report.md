<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

`setup delegate security-issue-triage` in an adopted repository, personal
surface (`.apache-magpie-local/`).

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

The user chose **merge** and asked to add `skip: Step 4 — Confirm with the
user before posting`, because "our skill posts the comment itself".
`setup_preflight.delegation render` printed to stderr: `render: refused: the
merge would skip a baseline step (Step 4 — Confirm with the user before
posting), which no delegate may remove` and exited 1. The user has not
answered since.
