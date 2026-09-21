<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

This skill is `magpie-security/issue-triage`.

cat skills/issue-triage/SKILL.md (frontmatter, this skill's own file):
  requires_config:
    - project.md
    - canned-responses.md
  surface_hash: sha256:c11de8a70b4f9922

cat .apache-magpie.lock:
  method: git-tag
  ref:    v0.9.4
  reconciled:
    version: 0.9.4
    at:      2026-08-30
    skills:
      magpie-security/issue-triage: sha256:4ab70d1e88221fa0

cat .apache-magpie-local/reconciled.json:
  {}

Lookup-chain resolution for this skill's requires_config right now:
  .apache-magpie-local/project.md               -> present
  .apache-magpie-overrides/project.md           -> present
  .apache-magpie-local/canned-responses.md      -> absent
  .apache-magpie-overrides/canned-responses.md  -> present
  (every entry resolves through one layer or the other)

Skill body, current step headings (for context — the fixture is
narrating the drift, not asking the model to re-derive it):
  "## Step 3 — Read the report and classify" (renamed from
  "## Step 3 — Classify the disposition" since v0.9.4; an
  `.apache-magpie-overrides/issue-triage.md` override anchors to the
  old heading text)

Result: the stamped hash for `magpie-security/issue-triage`
(sha256:4ab70d1e88221fa0) differs from the skill's own current
`surface_hash` (sha256:c11de8a70b4f9922). Every requires_config entry
still resolves.
