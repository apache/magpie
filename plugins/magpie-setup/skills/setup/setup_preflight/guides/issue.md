<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# 🐦 Magpie here — your issue-management sidekick

A one-minute tour, then straight back to what you asked for.

## 🔄 The typical flow

1. 🏷️ **Triage** incoming issues and draft tracker replies — *"triage the open issues"*
2. 🔁 **Deduplicate** related reports and propose which to keep — *"find duplicate issues"*
3. 🧪 **Reproduce** a reported bug from its code — *"reproduce issue ABC-123"*
4. 🔍 **Reassess** resolved or end-of-life issues against today's code — *"re-assess old issues"*
5. 🛠️ **Draft a fix** with tests and a hand-back — *"draft a fix for ABC-123"*
6. 🧹 **Sweep stale issues** and review proposed actions — *"find stale issues"*
7. 📊 **Report** backlog and reassessment statistics — *"show backlog statistics"*

`reassess-stats` reports on reassessment results; `backlog-stats` reports on the backlog.
Tracker comments and issue closures require confirmation.
Stale closures need a second confirmation.
The fix workflow opens a draft PR only with `--draft-pr` and explicit approval.

## ⚙️ Configure it

Different skills need different project settings:

- 🗂️ **Tracker** — `issue-tracker-config.md` for triage, deduplication, reproduction, stale sweep, reassessment and statistics
- 📖 **Project** — `project.md` additionally for triage and stale sweep
- 🧪 **Investigation** — `reproducer-conventions.md` and `runtime-invocation.md` for reproduction; `reassess-pool-defaults.md` for reassessment
- 🛠️ **Fixes** — `fix-workflow.md` and `runtime-invocation.md` for drafting fixes

Configure personally with `/magpie-setup:setup config`.
Shared adoption with `/magpie-setup:setup adopt` is a maintainer decision.

## 💬 Just ask

Talk to Magpie in plain language:

- *"triage these incoming bugs and show me draft replies"*
- *"find duplicates without closing anything"*
- *"reproduce this issue and explain what you found"*
- *"reassess the issue backlog and summarize the results"*
- *"draft a fix for this confirmed bug"*
- *"review stale issues before posting or closing"*
- *"show backlog and reassessment statistics"*

## 🎨 Make it yours

Describe how you want the issue workflow to behave:

- *"use our tracker conventions when drafting triage replies"*
- *"adjust the stale-issue thresholds for this project"*

Review configuration or override proposals before applying them.
Useful elsewhere? Ask *"upstream this change to Magpie"* to prepare a contribution for review.

<!-- welcome footer: generated from guides/_footer.md -->
