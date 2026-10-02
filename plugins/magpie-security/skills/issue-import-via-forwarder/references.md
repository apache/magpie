<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# security-issue-import-via-forwarder — references

## References

- [`tools/forwarder-relay/README.md`](../../../../tools/forwarder-relay/README.md) — the adapter contract this skill consumes (`detect`, `extract_credit`, `contact_handle`, `preamble_match`, `reporter_addressing_block`, `via_forwarder_question_mode`).
  The ASF-default adapter ships today; further third-party forwarders are placeholder contract slots.
- [`tools/gmail/asf-relay.md`](../../../../tools/gmail/asf-relay.md) — the ASF Security forwarder adapter's reference doc (the framework default, registered as `asf-security`): the paste-ready block convention, the clickable external-reference URL rule, and the threading semantics for relay drafts.
- [`projects/_template/project.md → forwarders`](../../../magpie-setup/templates/project.md#forwarders) — the YAML config schema for enabled adapters and their per-adapter overrides (`contact_handle`, `preamble_match`, `credit_extraction_rule`).
- [`docs/security/forwarder-routing-policy.md`](../../../../docs/security/forwarder-routing-policy.md) — the policy deciding *when* via-forwarder mode applies to a tracker, *which* milestones get relayed, and *what* falls into the do-not-relay negative space.
- [`tools/cve-tool-vulnogram/bot-credits-policy.md`](../../../../tools/cve-tool-vulnogram/bot-credits-policy.md) — the bot / AI credit policy applied at Step 2: tool vs individual in the CVE record, and whether the parent folds the *"if a human was behind the tool, please pass back their preferred attribution"* line into its receipt draft.
- [`tools/mail-source/contract.md`](../../../../tools/mail-source/contract.md) — the mail-source layer underneath; the sub-skill consumes a message from it and never fetches or sends mail itself.
- Parent skills:
  - [`security-issue-import`](../issue-import/SKILL.md) — invokes this sub-skill at Step 3 (classification) and Step 4 (credit extraction); folds the routing decision into its Step 7 *Apply confirmed imports*.
  - [`security-issue-invalidate`](../issue-invalidate/SKILL.md) — invokes it at Step 5 to route the reporter-facing invalidation notice through the matched forwarder.
  - [`security-issue-sync`](../issue-sync/SKILL.md) — invokes it at Step 2b to route reporter-facing milestone drafts (CVE allocated, advisory shipped, etc.) on via-forwarder-mode trackers.
- [`AGENTS.md`](../../../../AGENTS.md) — placeholder convention, prompt-injection absolute rule, confidentiality rule, link-form rules.
- [`docs/labels-and-capabilities.md`](../../../../docs/labels-and-capabilities.md) — capability taxonomy; this skill carries `capability:intake` because every operation sits inside the parent's intake pipeline.
