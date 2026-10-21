<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# 🐦 Magpie here — your setup sidekick

A one-minute tour, then straight back to what you asked for.

## 🔄 The typical flow

1. 🧭 **Check status** — *"show how Magpie is installed and adopted here"*
2. 🛠️ **Install and configure** — *"set up Magpie for me"*
3. 🔐 **Isolate the agent** — *"install the secure agent sandbox"*
4. ✅ **Verify and diagnose** — *"verify isolation"* or *"diagnose my sandbox"*
5. 🆙 **Check for drift and upgrade** — *"check my sandbox for drift"* or *"upgrade Magpie"*
6. 🏗️ **Adopt for the team** — *"adopt Magpie for this repository"*

Other skills help configure LLM privacy, synchronize shared config, upstream useful overrides, propose framework bug fixes, and replay welcome guides.

Read-only checks report findings.
Installation, adoption, upgrades, configuration writes, and repository changes follow their own approval steps.
Never edit Magpie's gitignored, read-only framework snapshot directly.

## ⚙️ Configure it

Nothing is required before using the Setup family:

- 📋 **Setup defaults** — optional `magpie-setup.md`
- 🔏 **Privacy policy** — optional `privacy-llm.md`
- 🧩 **Project identity** — optional `project.md`
- 🔗 **Trusted skill sources** — optional `skill-sources.md`

`/magpie-setup:setup config` writes personal configuration.
`/magpie-setup:setup adopt` proposes committed project-wide settings.
Review the plan and confirm before any project-wide mutation.

## 💬 Just ask

Talk to Magpie in plain language:

- *"show Magpie status in this checkout"*
- *"install Magpie and configure it just for me"*
- *"secure the agent with a sandbox and verify it"*
- *"set up privacy rules for model access"*
- *"check for configuration drift after an upgrade"*
- *"prepare a framework fix for this broken setup helper"*

## 🎨 Make it yours

Describe how your setup should behave:

- *"use our approved skill sources"*
- *"keep my personal privacy rules separate from project policy"*

Magpie records each request as an override of the setup skill it touches.
If other projects would want it too, say *"upstream this change to Magpie"* and review the generic `apache/magpie` PR it prepares.

<!-- welcome footer: generated from guides/_footer.md -->
