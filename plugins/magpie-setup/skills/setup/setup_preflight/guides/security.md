<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# 🐦 Magpie here — your security-team sidekick

A one-minute tour, then straight back to what you asked for.

## 🔄 The typical flow

1. 📥 **Import** new reports from `<security-list>` — *"import new reports"*
2. 🧭 **Triage** — proposed dispositions for the team to agree on — *"triage the open issues"*
3. 🔁 **Sync** — keeps each tracker in step with its mail thread and fix PRs; the everyday command — *"sync 123"*
4. 🏷️ **Allocate the CVE** once the team agrees the report is valid — *"allocate a CVE for 123"*
5. 🛠️ **Fix** in a public `<upstream>` PR that never gives away the security angle — *"try to fix 123"*
6. 📣 **Publish & announce** — sync again: it walks you through the advisory and drafts the final reporter email — *"the fix for 123 is released, sync it"*

Nothing is labelled, posted, or sent without your OK.

## ⚙️ Configure it

Two ways to run Magpie:

- 🙋 **Installed** — just for you: personal configuration, nothing committed — `/magpie-setup:setup config`
- 👥 **Adopted** — for your project: the configuration is stored in your repo and shared with every contributor — `/magpie-setup:setup adopt` (a maintainers' decision)

On a pinned-snapshot install the command is the shorter `/magpie-setup config` (or `adopt`).

The first time, a skill asks for what it cannot guess —
your `<security-list>` address, the `<tracker>` repository, the CVE tool you use —
and `/magpie-setup:setup config` fills it in.

## 💬 Just ask

The most powerful thing here is the conversation.
Plain language works:

- *"import new reports from the last 30 days"*
- *"what's waiting for triage?"*
- *"sync 123 and tell me what changed"*
- *"draft the reply to the reporter for 123"*
- *"which trackers are stuck waiting for a fix?"*
- *"allocate a CVE for 123"*
- *"the advisory for 123 went out — finish it"*

## 🎨 Make it yours

Magpie ships default settings and workflows.
Change them by describing the change:

- *"from now on, always cc the release manager on reporter replies"*
- *"skip the board column for INFO-ONLY reports"*

Each one becomes an override for the security skill it changes.
Useful to every security team? *"Upstream this change to Magpie"* turns it into a generic `apache/magpie` PR, and you review it before it opens.

<!-- welcome footer: generated from guides/_footer.md -->
