<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

PR #3002
Author: tirkarthi
IsDraft: true
Base: v3-3-test
Title: [v3-3-test] Link calendar cell to filter dagruns by start_date and state (#2611)
Commits:
  96295bdd71 [v3-3-test] Link calendar cell to filter dagruns by start_date and state (#2611)
SourceCommits:
  96295bdd71 -> 5ddea25c9c (on default branch)
GitCherry:
  + 96295bdd71
PatchIdU0Match:
  96295bdd71: no
    source:   +import { RouterLink, Tooltip } from "src/system-components";
    backport: +import { Link as RouterLink } from "react-router-dom";
    source:   +  const startDate = Boolean(cellData?.runs[0]?.date);
    backport: +  const startDate = cellData?.runs[0]?.date;
SourcePR:
  Title: Link calendar cell to filter dagruns by the respective start_date and state.
  Labels: [area:UI, backport-to-v3-3-test]
  Description: Clicking a calendar cell now opens the Dag runs list filtered to that day and state.
  Files: ui/src/pages/Dag/Calendar/CalendarCell.tsx
