<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Campaign pilot-2026-09 — 6 verdicts read from <scratch>/pilot-2026-09/<KEY>/verdict.json

PROJ-4412
  classification: still-fails-same
  nature: bug-as-advertised
  cases: []
  cross_type_probe.findings: "Same leak reproduces for the cron-triggered reload path; sibling code in scheduler/reload.py"
  notes: "Reproducer shape A, 18 lines. Thread count grows by one per SIGHUP on 3f2a9c1."

PROJ-4470
  classification: fixed-on-master
  nature: bug-as-advertised
  cases: []
  cross_type_probe.findings: ""
  notes: "Fixed by commit 9d1c0e2 (#4521); reproducer exits 0 on 3f2a9c1."

PROJ-4488
  classification: still-fails-same
  nature: feature-request-disguised-as-bug
  cases: []
  cross_type_probe.findings: ""
  notes: "Reporter wants the parser to accept a syntax the grammar never allowed; filed as Bug."

PROJ-3902
  classification: intended-behaviour
  nature: intended-and-documented
  cases: []
  cross_type_probe.findings: ""
  notes: "Maintainer citation: won't-fix per dev@ thread; behaviour documented under Override precedence."

PROJ-4501
  classification: fixed-on-master
  nature: bug-as-advertised-partial-fix
  cases: [{expr: "[1, 2,]", match_on_master: false}, {expr: "[[1,], 2]", match_on_master: true}]
  cases_summary: "Top-level trailing comma fixed; nested trailing comma still rejected."
  cross_type_probe.findings: ""
  notes: "Partial fix in 2.9; nested case still fails on 3f2a9c1."

PROJ-4533
  classification: duplicate-of-resolved
  nature: bug-as-advertised
  cases: []
  cross_type_probe.findings: ""
  notes: "Duplicate of PROJ-4102 (canonical), resolved in 3.2.0."
