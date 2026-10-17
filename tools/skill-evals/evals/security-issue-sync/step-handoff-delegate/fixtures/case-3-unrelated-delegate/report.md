<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Tracker state

**Tracker:** apache/security-tracker#1077
**Title:** Stored XSS in DAG documentation rendering
**Current step:** Step 6 — the team agreed the report is valid; a CVE is needed
**Labels (current):** `security`, `step-6`, `valid`

## Pre-flight verdict for this run

```json
{
 "verdict": "action",
 "findings": [
  {
   "scope": "skill",
   "code": "handoff-delegates",
   "section": "step-13",
   "facts": {
    "delegates": {
     "security-issue-fix": {
      "delegate": "open-pr",
      "mode": "replace",
      "path": ".claude/skills/open-pr/SKILL.md",
      "source": ".apache-magpie-overrides/security-issue-fix.md"
     }
    }
   }
  }
 ]
}
```
