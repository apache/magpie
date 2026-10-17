<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# release-vote-draft — references

- [`docs/release-management/process.md`](../../../../docs/release-management/process.md) —
  Step 7 context.
- [`docs/release-management/spec.md`](../../../../docs/release-management/spec.md) —
  `release-vote-draft` per-skill specification.
- [`<project-config>/release-management-config.md`](../../../magpie-setup/templates/release-management-config.md) —
  adopter keys this skill reads (`vote_*`, `vote_verification_doc_url`,
  `reproducibility_doc_url`, `vote_verification_skill`).
- [`docs/release-management/reproducibility.md`](../../../../docs/release-management/reproducibility.md) —
  what the reproducibility record in the body means and how a voter
  uses it.
- [`docs/release-management/manual-release-process.md` § Manual verification](../../../../docs/release-management/manual-release-process.md#manual-verification--what-a-voter-runs-before-1) —
  the longhand voter path the framework's own `[VOTE]` links to.
- `release-verify-rc` (proposed) —
  upstream step; PASS is a prerequisite, and the agentic path the body
  offers voters.
- `release-vote-tally` (proposed) —
  downstream step; runs after the vote window closes.
- [ASF release policy § release approval](https://www.apache.org/legal/release-policy.html#release-approval) —
  the 72h vote-window floor.
