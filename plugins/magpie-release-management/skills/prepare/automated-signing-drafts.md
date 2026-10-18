<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Step A2–A3 — the Infra ticket and the Security Team notification (🪶 ASF-specific)

Loaded from [`automated-signing.md`](automated-signing.md) once A1 is `eligible`.
Both are drafts: the skill never files the ticket, never sends the mail, and never adds key material anywhere.

## A2 — Draft the Infra Jira ticket

Draft (never file) an `INFRA` ticket titled *"CI release signing key for Apache <PROJECT>"* that:
- requests the key per the policy (4096-bit RSA, signing-only, private half held by infra-root, public block to `KEYS`, encrypted revocation certificate to the project's private repo);
- names the workflow (`ci_release_workflow`) and the staging target (ATR via `apache/tooling-actions/upload-to-atr`, pinned by commit SHA);
- **highlights the trusted-hardware validation step** — `release-verify-rc` Step 9 with `--trusted-hardware`,
  `repro-archive compare --require-identical` for every artefact, recorded on the planning issue, gating `release-promote`;
- references the background ticket in `release_process.automated_signing.key_request_background`.

## A3 — Draft the Security Team notification

Draft (never send — [spec § Boundary 3](../../../../docs/release-management/spec.md#boundary-3-agent-never-sends-mail-to-dev-users-announce))
a mail to `release_process.automated_signing.approval_body` (`security@apache.org`) from the RM,
pointing at the ticket, the workflow PR and the validation step, asking for the approval the policy requires before the workflow is used.
Plain text, real links, per the repository's email rules.
