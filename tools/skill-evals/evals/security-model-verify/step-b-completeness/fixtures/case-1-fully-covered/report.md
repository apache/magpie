<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Model at https://github.com/example/widget/blob/main/THREAT_MODEL.md

- §1.2 Scope and intended use — 40 lines, component-family table naming
  four families with in/out markers.
- §1.3 Out of scope — 20 lines, names `examples/`, `contrib/`, and the
  vendored copy of a third-party parser.
- §1.7 Assumptions about inputs — per-operand trust table, 18 rows.
- §1.10 Adversary model — 25 lines, three included and two excluded
  attacker capabilities.
- §1.11 Security properties provided — 12 claims, each with a violation
  symptom and severity.
- §1.12 Security properties not provided — 9 disclaimers with false-friends.
- §1.13 Downstream responsibilities — 15 lines.
- §1.15 Known non-findings — 6 entries with IDs, conditions, and a
  Discharged-by column.
- §1.17 Triage dispositions — the full closed set with a precedence list.
