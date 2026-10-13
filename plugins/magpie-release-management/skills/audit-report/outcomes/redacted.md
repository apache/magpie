<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Outcome — redacted fields

A `REDACTED` field renders as `_REDACTED — <reason>_` with the reason from `redaction_reasons`, and the Notes list it.
A `REDACTED` field without a reason comes back in `input_gaps`: write the one-line reason (what kind of non-public source, never its content) and re-run.

The reason must not quote the tracker, the CVE draft, the reporter or any embargoed text (Golden rule 4).
If the RM thinks the field should be public, it goes on the planning issue from a public source first; the skill never un-redacts on request.
The Step 3 PR body lists each redacted field with its reason.
