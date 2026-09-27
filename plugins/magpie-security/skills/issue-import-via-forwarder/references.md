<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# security-issue-import-via-forwarder — references

## References

- [`tools/forwarder-relay/README.md`](../../../../tools/forwarder-relay/README.md)
  — the adapter contract this skill consumes (`detect`,
  `extract_credit`, `contact_handle`, `preamble_match`,
  `reporter_addressing_block`, `via_forwarder_question_mode`).
  The ASF-default adapter ships today; any further third-party
  forwarders are placeholder contract slots.
- [`tools/gmail/asf-relay.md`](../../../../tools/gmail/asf-relay.md)
  — the reference doc for the ASF Security forwarder adapter
  (the framework's default, registered as `asf-security` in
  the ASF adopter's `forwarders.enabled`). Documents the
  paste-ready block convention, the clickable external-
  reference URL rule, and the threading semantics for relay
  drafts.
- [`projects/_template/project.md → forwarders`](../../../magpie-setup/templates/project.md#forwarders)
  — the YAML config schema each adopter declares to register
  enabled adapters and their per-adapter overrides
  (`contact_handle`, `preamble_match`, `credit_extraction_rule`).
- [`docs/security/forwarder-routing-policy.md`](../../../../docs/security/forwarder-routing-policy.md)
  — the policy that decides *when* via-forwarder mode applies to
  a tracker, *which* milestones get relayed, and *what* falls
  into the do-not-relay negative space. The adapter contract is
  the mechanism; this doc is the policy that drives it.
- [`tools/cve-tool-vulnogram/bot-credits-policy.md`](../../../../tools/cve-tool-vulnogram/bot-credits-policy.md)
  — the bot / AI credit policy applied to the extracted credit
  string at Step 2. Drives whether the CVE record lists the
  credit as a tool vs an individual, and whether the parent
  skill folds the *"if a human was behind the tool, please pass
  back their preferred attribution"* line into its receipt-of-
  confirmation draft.
- [`tools/mail-source/contract.md`](../../../../tools/mail-source/contract.md)
  — the mail-source layer this skill sits on top of. The
  sub-skill consumes a message returned by the mail-source
  layer; it does not itself fetch or send mail.
- Parent skills:
  - [`security-issue-import`](../issue-import/SKILL.md)
    — invokes this sub-skill at Step 3 (classification) and
    Step 4 (credit extraction); folds the routing decision into
    its Step 7 *Apply confirmed imports*.
  - [`security-issue-invalidate`](../issue-invalidate/SKILL.md)
    — invokes this sub-skill at Step 5 to route the reporter-
    facing invalidation notice through the matched forwarder.
  - [`security-issue-sync`](../issue-sync/SKILL.md) —
    invokes this sub-skill at Step 2b to route reporter-facing
    milestone drafts (CVE allocated, advisory shipped, etc.) on
    via-forwarder-mode trackers.
- [`AGENTS.md`](../../../../AGENTS.md) — placeholder convention,
  prompt-injection absolute rule, *"Confidentiality of
  `<tracker>`"* rule, link-form rules. The skill body relies on
  every one of these.
- [`docs/labels-and-capabilities.md`](../../../../docs/labels-and-capabilities.md)
  — capability taxonomy; this skill carries
  `capability:intake` because every operation it performs sits
  inside the parent's intake pipeline (classification, credit
  extraction, draft routing — all phases of bringing an inbound
  report into the tracker).
