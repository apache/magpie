<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# 🐦 Hello from Magpie — your project's maintainer sidekick

One minute, then straight back to what you asked for.

## 🚀 Getting started

- 📦 **Install** from your agent's marketplace (Claude Code shown):
  `/plugin marketplace add apache/magpie`,
  then `/plugin install magpie-setup@apache-magpie` and one `/plugin install magpie-<family>@apache-magpie` per family you want
- 🙋 **Configure it for yourself** — personal settings, nothing committed — `/magpie-setup:setup config`
- 👥 **Adopt it for your project** — the configuration is committed to your repo and shared with every contributor —
  `/magpie-setup:setup adopt` (a maintainers' decision)

On a pinned-snapshot install the commands are shorter: `/magpie-setup config`, `/magpie-setup adopt`.

## 🔄 Staying current

- ✋ **By hand:** `claude plugin marketplace update apache-magpie`, then `claude plugin update <plugin>@apache-magpie`
- 🤖 **Automatically (Claude Code):** `/plugin` → **Marketplaces** → **apache-magpie** → **Enable auto-update** —
  it is off by default for third-party marketplaces like this one
- 🧩 Gemini CLI takes `--auto-update` at install time; Codex has no auto-update, so run `codex plugin marketplace upgrade`

After an update, the next skill you run checks your configuration against it and proposes any fixes;
`/magpie-setup:setup reconcile` checks everything at once
(on a pinned snapshot, `/magpie-setup upgrade` does the update).

## 💬 Just ask

Talk to Magpie in plain language — no syntax to learn.
Nothing is written, posted, or sent without your OK.
Interrupt at any time, say no, or change your mind halfway through.

## 🎨 You are the creator

Describe what you want a skill to do for you:

- *"from now on, always ask me before closing a stale issue"*
- *"when you triage PRs, leave the bot-authored ones alone"*

Magpie records it as an override for that skill (`/magpie-setup:setup override <skill>`).
Worth sharing? Say *"upstream this change to Magpie"* —
it makes the change generic and opens a PR to `apache/magpie` for you to review (`/magpie-setup:override-upstream`).

## 📚 More guides

Each family can bring its own short guide, shown the first time you use it:

<!-- family guides: generated from guides/ -->

<!-- welcome footer: generated from guides/_footer.md -->
