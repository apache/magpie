<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

`setup delegate` in an adopted repository; the user picked the committed
surface.

`setup_preflight.discovery` printed two matches:

```json
{"project_skills": [{"name": "triage-reports", "path": ".claude/skills/triage-reports/SKILL.md"},
                    {"name": "codeql-ci", "path": ".github/skills/codeql-ci/SKILL.md"}],
 "matches": [{"project_skill": {"name": "triage-reports", "path": ".claude/skills/triage-reports/SKILL.md"},
   "magpie_skill": "security-issue-triage", "score": 0.58, "shared_terms": ["classify", "report", "security", "triage"],
   "draft_merge": [], "suggested": "keep"},
  {"project_skill": {"name": "codeql-ci", "path": ".github/skills/codeql-ci/SKILL.md"},
   "magpie_skill": "security-issue-triage", "score": 0.27, "shared_terms": ["security", "team"],
   "draft_merge": [], "suggested": "keep"}]}
```

`triage-reports`: "Triage new security reports for the security team and
classify them." `codeql-ci`: "Configure and run the CodeQL security scan in
CI and post its results to the team channel."

For `triage-reports` the user chose **replace**; `render` printed a valid
block and `resolve security-issue-triage` answered `delegated`.
