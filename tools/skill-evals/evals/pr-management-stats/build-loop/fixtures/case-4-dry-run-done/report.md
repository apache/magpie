<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

The maintainer ran the stats skill with `dry-run`. `stats build` printed:

```json
{"out": "/scratch/dashboard.html", "format": "html", "summary": {"health": "✅ Healthy", "open": 40, "ready": 5, "untriaged": 0, "untriaged_over_4_weeks": 0, "recommendations": [], "line": "Summary: 40 open · 30 triaged (75%) · 20 responded (66% of triaged) · 5 ready for review · 1 drafted by triager in last 7d."}, "partial": false, "cap_note": null, "warnings": [], "publish": {"gist_id": "abc123", "command": "gh api -X PATCH gists/abc123 --input /scratch/dashboard.gist-payload.json", "payload": "/scratch/dashboard.gist-payload.json"}}
```
