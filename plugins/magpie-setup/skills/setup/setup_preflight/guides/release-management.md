<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# 🐦 Magpie here — your release-management sidekick

A one-minute tour, then straight back to what you asked for.

## 🔄 The typical flow

1. 📋 **Prepare** the release plan and version bump — *"plan our next release"*
2. 🔑 **Check KEYS** before RC signing — *"sync the release signing key"*
3. 📦 **Cut an RC** and prepare signing/staging commands — *"cut rc1 for this version"*
4. ✅ **Verify the RC** before a vote — *"verify the staged release candidate"*
5. 🗳️ **Draft the vote**, then tally results — *"draft the vote email"* / *"tally the votes"*
6. 🚀 **Promote** a release only after approval — *"prepare promotion commands"*
7. 📣 **Draft the announcement**, then review archive cleanup — *"draft the announcement"*
8. 📊 **Audit** the completed release evidence — *"prepare the release audit report"*

These steps are guided workflows, not autonomous publishing.
The Release Manager keeps the signing key and runs signing and publication commands.
Vote and announcement emails are drafts, never automatically sent.
Review and explicitly approve proposed external or repository changes.

## ⚙️ Configure it

Release skills use project-specific configuration:

- ⚙️ **Release policy** — `release-management-config.md` for planning, votes, announcements, archives, audit reports and KEYS
- 📦 **Build and staging** — `release-build.md` for `rc-cut` and `verify-rc`
- 🗳️ **Approval roster** — `pmc-roster.md` for `vote-tally` and `promote`
- 🚆 **Release trains** — `release-trains.md` for `prepare` and `archive-sweep`

The distribution, approval and announcement backends are set in `release-management-config.md`.
Configure personally with `/magpie-setup:setup config`.
Team adoption with `/magpie-setup:setup adopt` is a maintainer decision.

## 💬 Just ask

Talk to Magpie in plain language:

- *"prepare the release plan for our next version"*
- *"check that my public signing key is in KEYS"*
- *"give me the commands to cut and verify rc1"*
- *"draft a vote email for this verified RC"*
- *"tally the release vote and prepare the result draft"*
- *"prepare promotion and announcement after the vote passes"*
- *"review old release archives and generate an audit report"*

## 🎨 Make it yours

Describe your release policy and preferred backend:

- *"use a 96-hour vote window instead of 72"*
- *"always run the KEYS check before cutting an RC"*

Review proposed configuration or override changes before applying them.
Useful elsewhere? Ask *"upstream this change to Magpie"* to prepare a contribution for review.

<!-- welcome footer: generated from guides/_footer.md -->
