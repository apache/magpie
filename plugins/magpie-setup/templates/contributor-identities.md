<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [TODO: `<Project Name>`: contributor identities](#todo-project-name-contributor-identities)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# TODO: `<Project Name>`: contributor identities

The project's community channels, and confirmed mappings from each
contributor's GitHub handle to their handles on those channels
(Slack, Discord, Matrix, mailing lists, Mastodon, Bluesky,
LinkedIn, …).
Any contributor can have an entry, from a first-time PR author to a
PMC member.

The `contributor-identity-map` skill infers each mapping, shows it to
a maintainer, and proposes an edit to this file only for the
mappings the maintainer confirmed.
`committer-onboarding` and `contributor-nomination` run it for their
candidate and use the confirmed handles.

This file is personal data.
Record a handle here only when the contributor published it
themselves or agreed to share it; mark a channel
`status: ask-contributor` while the answer is outstanding.
Correct or remove an entry whenever the contributor asks.

The per-field format is documented in the skill's
[`sources.md`](../../../skills/contributor-identity-map/sources.md#identity-file-format).

```yaml
identity_mapping:
  # Set to false to make every skill skip identity mapping.
  enabled: true

  # Set to false to keep confirmed mappings for the current run only
  # instead of recording them under `identities` below.
  record: true

  # Sources the skill may infer handles from. Omit to allow every
  # source the session can reach; an unreachable source is reported
  # as "not searched".
  # Allowed values: github-profile, org-directory, slack, discord,
  #   matrix, zulip, mailing-lists, contributor-text, commit-metadata
  sources: [github-profile, org-directory, slack, mailing-lists, contributor-text, commit-metadata]

  # The project's community channels. Only listed channels are
  # mapped (plus whatever a contributor's GitHub profile declares).
  # `id`: slack, discord, matrix, zulip, mastodon, bluesky, x,
  #   linkedin, website, or any other short name.
  # `on_onboard` (optional): an action committer-onboarding adds to
  #   its checklist for a new committer, run only against a
  #   confirmed handle.
  channels:
    - id: slack
      label: TODO  # e.g. ASF Slack
      workspace: TODO  # e.g. the-asf.slack.com
      on_onboard: TODO  # e.g. "Invite to #<project>-committers", or null
    - id: discord
      label: TODO  # e.g. Project Discord
      workspace: TODO  # e.g. discord.gg/<invite>
      on_onboard: TODO  # e.g. "Grant the Committer role", or null
    - id: mastodon
      label: Mastodon
    - id: linkedin
      label: LinkedIn

identities: []
# Example entry:
#  - github: psharma-oss
#    name: Priya Sharma
#    org_id: psharma
#    channels:
#      slack:
#        handle: "@priya"
#        id: U012ABCDEF
#        source: slack-profile-link
#        grade: verified
#      mastodon:
#        handle: "@priya@fosstodon.org"
#        url: https://fosstodon.org/@priya
#        source: github-social-accounts
#        grade: self-declared
#    confirmed_by: jmclean
#    confirmed_on: 2026-09-28
```
