<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Security model — calibration

Read the source section the adopter's `Section anchors` table links for this category (`section_anchors` in the `context` output) and quote the rule **verbatim** in the finding — never paraphrase. If the category has no anchor row, use a plain reference and surface the missing anchor once at the top of the review.

> This category also includes a **public-disclosure signal scan**
> that runs in Step 3 (PR title, body, and commit messages),
> before the diff is examined. See
> [`review-flow.md` § Security-disclosure signal scan](../classifications/security-disclosure.md).

Before flagging anything that looks security-flavoured in the
diff, read the documented security model at the path declared in
`<project-config>/pr-management-code-review-criteria.md` →
`security_model_calibration.file`. The framework's reference
threat model lives at
[`docs/security/threat-model.md`](../../../../../docs/security/threat-model.md);
read both before deciding. Use the calibration to distinguish:

1. an **actual vulnerability** that violates the documented
   model — flag as blocking,
2. a **known limitation** that's already documented as
   intentional — do not flag,
3. a **deployment-hardening opportunity** — belongs in
   deployment guidance, not as a code finding.

When the skill downgrades what looked like a finding because
the documented model permits it, the review body **quotes the
relevant model paragraph** so the contributor sees the
calibration explicitly. Don't paraphrase.

---
