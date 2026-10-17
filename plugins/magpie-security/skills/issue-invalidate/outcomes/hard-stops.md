<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# security-issue-invalidate — Step 0 hard stops

Read from [`SKILL.md` Step 0 item 3](../SKILL.md#step-0--pre-flight-check); `<sm> hard-stops` decides them and prints each message.

   | Detected state | Stop reason |
   |---|---|
   | `cve allocated` label set, or *CVE tool link* body field — `cve_authority.record_url_template` substituted with the CVE ID — populated with a CVE-ID URL, **and** `<cve-tool>`'s `fetch_current_state(cve_id)` (per [`tools/cve-tool/README.md`](../../../../../tools/cve-tool/README.md#fetch_current_statecve_id-to-state-fields)) returns a state of `allocated` or `review-ready` | Closing as invalid requires the CVE record to be **retracted** at the CVE-tool first. That is a separate flow (governance-gated per `governance.cve_allocation_gate`, similar to allocation). Stop and surface the URL of the *CVE tool link* alongside a one-line ask: *"This tracker has CVE `<CVE-ID>` allocated (current state: `<state>`). Retract the CVE record at the CVE-tool first, then re-invoke this skill."* (For the Vulnogram adapter, that's the State dropdown moving from `DRAFT` or `REVIEW` to `REJECTED` — see [`tools/cve-tool-vulnogram/README.md`](../../../../../tools/cve-tool-vulnogram/README.md).) |
   | `fix released`, `announced - emails sent`, or `announced` label set | The advisory has already shipped (or is mid-flight). Closing as invalid retroactively is a retraction with public consequences. Stop and surface a one-line ask: *"This tracker is past `pr merged` (label: `<label>`). Closing as invalid here would retract a published advisory; escalate to the team before re-invoking."* |
   | Tracker is already `closed` | No-op; surface the existing close reason and stop. |

   Both hard stops are deliberate: the skill never papers over a CVE allocation or a published advisory by silently labelling and closing.

   The CVE-state probe speaks the four generic pre-public verbs (`allocated`, `review-ready`, `publish-ready`, `public`) of
   [`tools/cve-tool/README.md` § *Generic state verbs*](../../../../../tools/cve-tool/README.md#generic-state-verbs),
   onto which the `cve_authority.tool` adapter maps its own states.
   By returned state:

   - `allocated` or `review-ready` — hard stop per the table above: the CVE record can still be retracted cleanly, and it MUST be retracted before the tracker is closed as invalid.
   - `publish-ready` or `public` — escalate to `governance.escalation_contact`: an invalid close here would be a post-publication retraction with public consequences.
   - `retracted` — proceed; the CVE record is already in its terminal failure state.
   - `unknown` (the `none` adapter, or the adapter cannot reach the tool) — fall back to the label / body-field check alone;
     if either signal is present, surface the gap and ask the user to confirm before proceeding.
