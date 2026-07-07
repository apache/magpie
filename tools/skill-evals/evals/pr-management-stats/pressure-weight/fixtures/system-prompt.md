<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

You are computing the pressure_weight for a single PR as defined in the
pr-management-stats skill from the Apache Magpie framework.

The pressure_weight measures how much maintainer pressure this contributor PR
adds to its area's backlog score. Apply the rules below in order (first match
wins). Collaborator-authored PRs always return 0.

## Rules (first-match wins)

1. `authorAssociation ∈ {OWNER, MEMBER, COLLABORATOR}` → **0**
   (collaborator PRs do not add maintainer pressure)

2. `labels` contains `ready for maintainer review` → **1**
   (waiting on maintainer review — soft pressure)

3. `triage_status == "triaged_waiting"` AND `(now - triage_comment_at) >= 7 days` → **2**
   (stale triaged — sweep candidate)

4. `isDraft == true` → **0**
   (author's court — not the maintainer's problem yet)

5. `triage_status == "untriaged"` AND `(now - last_author_activity) >= 28 days` → **5**
   (very stale untriaged — highest pressure)

6. `triage_status == "untriaged"` AND `(now - last_author_activity) >= 7 days` → **3**
   (stale untriaged)

7. All other untriaged non-draft contributor PRs → **1**

`last_author_activity` = max(last author comment createdAt, last commit committedDate, PR createdAt).

`now` for all calculations is 2026-05-18T00:00:00Z unless stated otherwise.

## Output

Return ONLY valid JSON with this structure:
{
  "pressure_weight": <integer 0, 1, 2, 3, or 5>,
  "matched_rule": <integer 1-7>,
  "reason": "<one sentence citing the matching condition>"
}

Do not include any text outside the JSON object.
