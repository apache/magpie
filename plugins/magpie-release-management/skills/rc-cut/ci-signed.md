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
Instead of Sections 3–4 and Step 3, run

```bash
uv run --project <framework>/tools/release-management release-management rc-cut render \
  --step 2c --load <scratch>/rc-cut-load.json --upstream <upstream> --project <project> \
  --framework <framework>
```

and present `text`: push the signed tag (it triggers `ci_release_workflow`), watch the run, confirm the staged candidate in ATR, and record the run URL and `SOURCE_DATE_EPOCH` for Step 4.
End with the render's `handoff`, word for word: a committer must run `release-verify-rc <version>-<rcN>` on their own hardware, and `release-promote` refuses to promote without that attestation.

Return ONLY valid JSON with this structure (the render's fields):

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
