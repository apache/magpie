<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Promotion backend — `self-hosted`

The render's `command_block` is `release_publish_command_template` from `<project-config>/release-management-config.md`,
with `<version>` and `<rcN>` substituted.

If the template is absent, it is a hard blocker: Step 0's `release-config preflight` reports it, and the render refuses.
Surface it and stop; the remediation is adding `release_publish_command_template` to `release-management-config.md`.
Never compose a publish command the config does not declare.

A held convenience artefact staged alongside the source is also a refusal: the template cannot be told to leave it out,
so remove it from the staging location by hand (or fix the build and re-run `release-verify-rc`), then re-run the skill.

The promotion event is whatever the template publishes; the mirror note's one-hour clock starts there.
