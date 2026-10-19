<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# 🐦 Magpie here — your pre-PR review sidekick

A one-minute tour, then straight back to what you asked for.

## 🔄 The typical flow

1. 🔍 **Self-review** your local diff before pushing — *"review my diff before I push"*
2. 🛡️ **Multi-agent review** the diff with independent correctness, security, and conventions passes — *"run independent reviews of my branch"*

Both skills return review reports. They never edit files, post comments, open PRs, push, or merge.

## ⚙️ Configure it

Nothing is required before your first review:

- 📖 **Project context** — optionally use `project.md` for project-scoped references; otherwise the skills use their defaults
- 🎯 **Review scope** — choose a base ref, staged changes, or a path filter when needed

Configure it for yourself with `/magpie-setup:setup config`.
Adopting shared configuration with `/magpie-setup:setup adopt` is a project maintainer decision.

## 💬 Just ask

Talk to Magpie in plain language:

- *"review my diff before I push"*
- *"check my staged changes for correctness and security"*
- *"review only the files under this directory"*
- *"run three independent review passes on my branch"*
- *"compare the correctness, security, and conventions findings"*

For an already-open PR, use the PR-management code-review workflow instead.

## 🎨 Make it yours

Describe how you want the review workflow to behave:

- *"focus my self-review on error handling and security risks"*
- *"make the conventions review check our project's documented style"*

Review the proposed skill override before applying it.
Useful to others? Ask *"upstream this change to Magpie"* to prepare a reusable contribution for your review.

<!-- welcome footer: generated from guides/_footer.md -->
