<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Step 2c — CI-signed flow (🪶 ASF-specific, `signing_mode: ci-automated`)

Only for a project whose organization offers automated signing
(`release_process.automated_signing`, resolved `project.md` → organization manifest → framework default; only the ASF sets it)
and whose `release-management-config.md` sets `automated_release_signing: enabled` after the one-time setup in `release-prepare automated-signing`
(Infra-provisioned key, Security Team approval, workflow merged).
For every other project this step does not exist and is never mentioned.

Under
[Infra § Automated release signing](https://infra.apache.org/release-signing.html#automated-release-signing)
CI builds, signs and **stages** the artefacts;
a committer re-validates them bit-by-bit on trusted hardware before anything is published.
The RM still signs the **tag** with their own key (Section 1).
Instead of Sections 3–4 and Step 3, emit:

```text
# 1. Push the signed tag — this triggers <ci_release_workflow>
git push <git-upstream-remote> <version>-<rcN>
# 2. Watch the run; it builds reproducibly (repro-archive), self-compares,
#    checksums, and uploads to ATR (OIDC trusted publishing). It publishes nothing.
gh run list --repo <upstream> --workflow <ci_release_workflow> --branch <version>-<rcN>
gh run watch --repo <upstream> <run-id>
# 3. Confirm the staged candidate and its checks in ATR
atr check status <project> <version> --verbose
# 4. Record the run URL and the SOURCE_DATE_EPOCH from the run log for Step 4
```

Then hand off:
*"Before this RC can be promoted, a committer must run `release-verify-rc <version>-<rcN>` on their own hardware;
its Step 9 rebuilds every artefact and requires `identical`.
`release-promote` refuses to promote without that attestation on the planning issue."*

Return ONLY valid JSON with this structure:

```json
{
  "signing_mode": "ci-automated",
  "organization": "ASF",
  "ci_release_workflow": "<path>",
  "trigger_commands": ["git push <remote> <version>-<rcN>", "gh run list …", "gh run watch …"],
  "local_sign_commands_omitted": true,
  "trusted_hardware_validation_required": true,
  "proposed": true
}
```

`local_sign_commands_omitted` and `trusted_hardware_validation_required` are always `true` in this mode.
