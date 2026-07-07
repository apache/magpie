<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Tracker state

**Tracker:** apache/security-tracker#1055
**Title:** SSRF via unchecked HTTP redirect in HttpOperator
**Current step:** Step 6 — CVE allocation
**Labels (current):** `security`, `step-6`, `cve-worthy`, `MEDIUM`
**Milestone:** (none)
**Days since last activity:** 1

## Step diagnosis

The team reached consensus during Step 3–5 that the issue is CVE-worthy:
an HttpOperator with `allow_redirects=True` (default) leaks credentials to
an attacker-controlled server via an open redirect. CVSS estimated MEDIUM.

The tracker is now at Step 6. No CVE has been allocated yet
(`cve_tool_link` body field is blank).

## Proposed changes (2b output)

Items proposed:
1. Add label `step-6` (already present — skip)
2. Remove label `step-5` (already absent — skip)
3. Post status comment: "CVE-worthy consensus reached. Moving to Step 6:
   CVE allocation."

The label housekeeping is already clean; the only outstanding action is
running CVE allocation.
