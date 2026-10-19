<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# 🐦 Magpie here — your PR-management sidekick

A one-minute tour, then straight back to what you asked for.

## ⚙️ Configure it

Start with `<upstream>`, the project's review criteria and its area labels.
`pr-management-code-review-criteria.md` names the criteria sources;
`pr-management-config.md` carries the labels and queue rules.
`reviewer-roster.md` tells reviewer routing who covers each area.

- **Configure it for yourself** — personal configuration, nothing committed — `/magpie-setup:setup config`
- **Adopted** — for your project: shared configuration committed to the repo — `/magpie-setup:setup adopt` (a maintainers' decision)

On a pinned-snapshot install, use `/magpie-setup config` or `/magpie-setup adopt`.

Optional companion: roborev reviews your own branch before it becomes a PR;
this family helps you review and manage other people's PRs.
Neither requires the other.

## 🔄 The typical flow

1. **Triage the queue** — propose a disposition for each PR — *"triage the open PRs"*
2. **Route reviewers** — use the roster to suggest the right people — *"who should review this PR?"*
3. **Review** — inspect the diff and draft inline feedback — *"review this PR against our criteria"*
4. **Quick-merge** — screen easy candidates and propose the command for you to run — *"which PRs are ready for quick-merge?"*
5. **Mentor** — help a contributor through the next step — *"draft helpful feedback for this contributor"*
6. **Stale sweep** — propose follow-ups for inactive PRs — *"show me the stale PRs"*
7. **Stats** — see where the queue needs attention — *"summarise the PR backlog by area"*

Nothing is written, posted, labelled or closed without your explicit confirmation.
Quick-merge never merges for you: it hands you the command.

## 💬 Just ask

- *"check my branch before I open my first PR"*
- *"triage the PRs waiting for review"*
- *"who should review this PR?"*
- *"review this PR against our criteria"*
- *"review this PR stack in dependency order"*
- *"which PRs are ready for quick-merge?"*
- *"help this contributor understand the requested change"*
- *"what changed in the queue since the last sweep?"*
- *"summarise the PR backlog by area"*

## 🎨 Make it yours

Change a workflow by describing the change:

- *"from now on, group the backlog by our area labels"*
- *"use our review criteria when drafting feedback"*

Each becomes an override for the PR-management skill it changes.
Useful to other maintainers? *"Upstream this change to Magpie"* prepares a generic PR for you to review before it opens.

<!-- welcome footer: generated from guides/_footer.md -->
