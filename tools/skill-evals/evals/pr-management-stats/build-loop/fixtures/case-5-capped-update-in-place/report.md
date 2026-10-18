<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

The maintainer ran the stats skill with `fast-closed`. `stats build` printed:

```json
{"out": "/scratch/dashboard.html", "format": "html", "summary": {"health": "🔥 Action needed", "open": 900, "ready": 130, "untriaged": 80, "untriaged_over_4_weeks": 12, "recommendations": [], "line": "Summary: 900 open · 300 triaged (40%) · 90 responded (30% of triaged) · 130 ready for review · 4 drafted by triager in last 7d."}, "partial": false, "cap_note": "Search cap: the closed/merged series hit GitHub's 1000-result limit (1640 matched). Weeks starting 2026-08-28, 2026-09-04 are cap-truncated; authoritative weeks: 2026-09-11, 2026-09-18, 2026-09-25, 2026-10-02.", "warnings": [], "publish": {"gist_id": "abc123", "command": "gh api -X PATCH gists/abc123 --input /scratch/dashboard.gist-payload.json", "payload": "/scratch/dashboard.gist-payload.json"}}
```
