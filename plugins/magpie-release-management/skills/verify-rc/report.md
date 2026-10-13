<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Step 10 — Hand-back verification report

Aggregate the per-step results into a final report.
`<verify-rc>` is `uv run --project <framework>/tools/release-management release-management verify-rc <command> --load <scratch>/verify-rc-load.json`, as in SKILL.md.

**Overall verdict.** Compute it with the tool, not by hand.
Pass the JSON result of every step, Step 6b's included when it ran,
plus the status of each step the tool does not decide: Step 4, Step 9, Step 6c (🪶 when it ran), and any
`REVIEW` resolved in Steps 5 and 7.

```bash
uv run --project <framework>/tools/release-verify release-verify verdict <step-result>.json … \
  --status rat-license-headers=<status> --status reproducibility=<status> \
  [--status nexus-staging=<status>] [--status notice-license=<PASS|WARN>] [--status source-tree-integrity=<PASS|FAIL>]
```

`overall` is `FAIL` if any step fails, else `PASS-WITH-WARNINGS` if any warns, else `PASS`.
`SKIP` is neutral — it neither passes nor warns — and `skip_steps` lists every skipped step; name each one in the report.
A tool-computed status is final (`ignored_overrides` lists attempts to change one);
`overall: null` means a step is still `unresolved`.

**Report.** Render it with one-line `--finding <step>=<text>` per step (the reason for each skipped one),
and one `--fail-detail` / `--warn-detail` per failing / warning step naming the exact file or check and the RM remediation or review requirement:

```bash
<verify-rc> report --verdict <verdict.json> [--repro <step9.json> --compare <compare.json>] \
  --finding <step>=<one-line> … [--fail-detail "<detail>"]… [--warn-detail "<detail>"]… \
  [--post-to <url>] [--trusted-hardware --committer <github-handle>]
```

`text` is the report: header (RC, staging URL, UTC timestamp), the voter-obligation reminder, the per-step table, FAIL and WARN detail,
the overall verdict, and the reproducibility record (Step 9's verdict, commit, `SOURCE_DATE_EPOCH`, the rebuilt source sha512, each convenience artefact's result),
so another voter can cross-check without rerunning.
The voter-obligation reminder and the trusted-hardware attestation block are SKILL.md's Step 10 text, verbatim;
the command decides whether the attestation applies (`reproducibility_attestation`, and `attestation_withheld_because` when it does not) and never posts.

Return ONLY the command's JSON without `text` and `attestation_withheld_because`:
`step` (`report`), `rc_tag`, `verification_utc`, `overall` (`PASS` | `PASS-WITH-WARNINGS` | `FAIL`),
`voter_obligation_reminder` (always `true`: the reminder was included),
`step_summary[]` of `step`, `status` (`PASS` | `WARN` | `FAIL` | `SKIP`) and `finding`, `fail_details`, `warn_details`,
`reproducibility_attestation` (`true` only when the attestation block is in `post_to_comment`),
and `post_to_comment` (non-null only when `--post-to` was supplied and the RM has not yet confirmed posting).
