<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

You are executing Step 2 — Check cache freshness of the
security-tracker-stats-dashboard skill from the Apache Magpie framework.

## Cache freshness rules

Cache directory: `${TRACKER_STATS_CACHE:-/tmp/tracker-stats-cache}/`
Key cache file:  `issues.json`

Evaluate the following decision rules in priority order:

1. **`clear-cache` arg**: if the user passed `clear-cache` in the invocation,
   propose a full fetch unconditionally — even if the cache is present and
   fresh.  `cache_age_hours` still reflects what was found (or `null` if
   missing).

2. **Cache missing**: if `issues.json` does not exist (or the cache directory
   does not exist), propose a full fetch.  Set `cache_age_hours` to `null`.

3. **Cache stale** (> 24 h): if `issues.json` is older than 24 hours, propose
   a fresh fetch.  A fresh fetch re-fetches all data but starts from the
   existing cache directory.

4. **Cache fresh** (≤ 24 h): if `issues.json` is ≤ 24 hours old, run
   immediately without prompting.

Before any full or fresh fetch (5–10 minute operation), surface the
proposal to the user and wait for explicit confirmation.  Incremental
re-renders against a warm cache (~30 seconds) may run without a prompt.

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "action": "run_immediately | propose_refresh | propose_full_fetch",
  "cache_age_hours": <number or null>,
  "reason": "<short human-readable explanation>"
}
```

`action` values:
- `"run_immediately"` — cache is fresh (≤ 24 h); no user prompt needed.
- `"propose_refresh"` — cache is stale (> 24 h); surface a proposal.
- `"propose_full_fetch"` — cache is missing OR `clear-cache` was passed;
  surface a proposal.

`cache_age_hours` is `null` when the cache is missing.
Do not include any text outside the JSON object.
