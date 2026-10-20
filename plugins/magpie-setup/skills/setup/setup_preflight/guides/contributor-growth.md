<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# 🐦 Magpie here — your contributor-growth sidekick

A one-minute tour, then straight back to what you asked for.

## 🔄 The typical flow

1. 📊 **Activity sweep** across code, reviews, and issues — *"sweep activity for <handle>"*
2. 🪪 **Identity map** across GitHub, mailing lists, and chat handles — *"map identities for <handle>"*
3. 📈 **Compare activity with reference levels** as plain numbers — *"track <handle>'s path to committer"*
4. 📝 **Nomination brief** compiling evidence for a private list discussion — *"build nomination brief for <handle>"*
5. 🔍 **Candidate screen** across recent contributors without ranking — *"screen contributor candidates"*
6. 🤝 **Committer onboarding** walkthrough for ICLA and account setup — *"onboard new committer <handle>"*
7. 💬 **Sentiment check** to identify contributor friction or disengagement — *"check contributor sentiment"*

Nothing is ranked, decided, or posted without your OK.

## ⚙️ Configure it

Each skill reads `project.md`, plus the file for its own job:

- 📏 **Reference levels** — `committer-readiness.md` for the path-to-committer comparison, calibration and candidate screen; information only, never a readiness verdict
- 📝 **Nominations** — `contributor-nomination-config.md` for briefs, calibration and screening
- 🔒 **Private governance** — calibration reads past votes on `<private-list>`, so it also needs an approved model in `privacy-llm.md`; nothing from it reaches a public surface
- 🤝 **Onboarding and sentiment** — `committer-onboarding-config.md`, `onboarding-concierge-config.md` and `contributor-sentiment-config.md`

Configure it for yourself with `/magpie-setup:setup config`.
Project adoption with `/magpie-setup:setup adopt` is a maintainer decision.

## 💬 Just ask

Talk to Magpie in plain language:

- *"sweep activity for <handle> over the last 6 months"*
- *"map identities for <handle>"*
- *"how does <handle>'s activity compare with reference levels?"*
- *"assemble a nomination brief for <handle>"*
- *"calibrate committer reference levels from past nominations"*
- *"screen active contributors for mentoring candidates"*
- *"guide a newcomer through first-time contributor onboarding"*
- *"guide committer onboarding for <handle>"*
- *"are contributors encountering friction in PR reviews?"*

## 🎨 Make it yours

Every workflow, threshold, and community policy can be tailored.
Describe what your project needs:

- *"evaluate activity across 12 months rather than 6"*
- *"tune committer onboarding steps for our project"*

Your requests save as local skill overrides.
Think an adjustment benefits other projects? Asking *"Upstream this change to Magpie"* prepares a contribution PR for review.

<!-- welcome footer: generated from guides/_footer.md -->
