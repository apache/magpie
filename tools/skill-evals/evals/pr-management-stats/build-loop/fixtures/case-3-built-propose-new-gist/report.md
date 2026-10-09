<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

The maintainer ran the stats skill with no arguments. `stats build` printed:

```json
{"out": "/scratch/dashboard.html", "format": "html", "summary": {"health": "⚠️ Needs attention", "open": 412, "ready": 61, "untriaged": 23, "untriaged_over_4_weeks": 2, "recommendations": ["Triage 2 non-draft contributor PRs older than 4 weeks — /magpie-pr-management:pr-triage all PR issues"], "line": "Summary: 412 open · 180 triaged (52%) · 70 responded (39% of triaged) · 61 ready for review · 9 drafted by triager in last 7d."}, "partial": false, "cap_note": null, "warnings": [], "publish": {"gist_id": null, "command": "gh gist create /scratch/dashboard.html --desc \"apache/foo — PR Backlog Dashboard (2026-10-09)\"", "payload": null}}
```
