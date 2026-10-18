<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Typed-decision shadow pre-filter (opt-in)

**Opt-in typed-decision shadow pre-filter (advisory).**
When enabled via `enable_typed_decision_prefilter: true`
(default `false`) with threshold `typed_decision_confidence_threshold`
(default `0.85`), run the helper alongside `triage classify` to evaluate classifier accuracy.
For each classified PR, write its state to a scratch file and invoke:
```bash
uv run --project <framework>/tools/typed-decision python3 <framework>/skills/pr-management-triage/scripts/typed_decision_prefilter.py \
  --file <scratch>/pr-<N>.json \
  --table-classification <label>
```
- **Contract:**
  The decision table and Real-CI guard result remains authoritative in all cases.
  The shadow pass records predictions alongside the final table classification for telemetry.
- **`--file` JSON schema:**
  The input file provides a JSON object containing:
  `number` (int/str), `author` (str or `{"login": str}`), `authorAssociation` (str), `statusCheckRollup` (str), `failed_checks` (list of str), `recent_main_failures` (list of str), `mergeable` (str), `unresolved_threads` (int), `isDraft` (bool), `commits_behind` (int), `real_ci_ran` (bool), `labels` (list of str), `title` (str), `body` (str), `commit_messages` (list of str).
  Missing fields default to `UNKNOWN` to avoid biasing prompts toward `passing`.
- **Outcomes:**
  - `high_confidence`:
    Confidence meets or exceeds threshold and predicted label is valid.
    Logs `{pr, table_classification, predicted_label, confidence, latency_ms, match, outcome: "high_confidence"}`.
  - `low_confidence`:
    Confidence below threshold or unrecognised label.
    Logs `{pr, table_classification, predicted_label, confidence, latency_ms, match, outcome: "low_confidence"}`.
  - `fell_through`:
    Flag disabled, provider unavailable, or network error.
    Logs `{pr, outcome: "fell_through"}` with the specific reason (or skips logging if disabled).
    Triage proceeds unaffected.
- **Third-party LLM endpoint and privacy prerequisites:**
  - Endpoint: `https://api.typesafe.ai/v1/systemone`
  - Credentials: `TYPESAFE_API_KEY` (or fallback `JEV_API_KEY`) or `~/.config/apache-magpie/typesafe.key`.
  - Privacy-LLM approval: Requires an opt-in entry in `<project-config>/privacy-llm.md`
    with non-empty `Data-residency contract` and maintainer sign-off
    before enabling outbound classification.
  - Contributor title, body, and commits are fenced
    inside `<untrusted-external-data>` with tags escaped as data only.
- **Telemetry:**
  Records are appended to `logs/pr-triage-typed-decision.jsonl` in the personal layer (`<git-common-dir>/apache-magpie/` when Magpie is only installed, `.apache-magpie-local/` when adopted).
