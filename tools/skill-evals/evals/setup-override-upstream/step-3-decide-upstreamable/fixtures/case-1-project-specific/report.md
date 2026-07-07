<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Override file: `.apache-magpie-overrides/security-issue-import.md`
Override content summary:
  # Override 1 — Customise the acknowledgement reply
  This override replaces the default acknowledgement message body
  with the Apache Airflow project's standard canned response
  text, which includes specific references to our security@
  alias, our internal tracking ticket prefix (AIRFLOW-SEC-XXXX),
  and a disclaimer required by our PMC's legal policy.

Framework skill: `security-issue-import`
Relevant section: "Step 4 — Draft acknowledgement reply"
The framework's step generates a generic acknowledgement; the override
replaces the wording wholesale with Airflow-specific text.
