<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# issue-fix — implementation plan (Step 5)

## Step 5 — Propose the implementation plan (do not touch any code yet)

Present a single, compact plan with the following sections. The plan
is a *proposal*, and **no code is written until the user confirms it
verbatim.**

### 5a. Branch and base

- **Base:** `<default-branch>` (or the specific release branch if agreed).
- **Branch name:** Use a descriptive, non-security slug. For example:
  - good: `fix-extra-links-xcom-deserialization`
  - good: `tighten-assets-graph-dag-permission-check`
  - **bad** (reveals security framing): `cve-2026-40690`,
    `security-fix-218`, `vulnerable-deserialize-fix`.

  Tracker identifiers on their own (e.g. `<tracker>-216`) are not
  flagged — they are public-safe identifiers per the
  [Confidentiality of the tracker repository](../../../../AGENTS.md#confidentiality-of-the-tracker-repository)
  rule — but they also do not help anyone reading the branch URL
  on the user's fork; a descriptive bug-fix slug is preferred.

### 5b. Files that will change

A bullet list of file paths (relative to the repo root), each with a
one-line description of the change. Where the discussion pointed to
specific lines, include them. If the discussion included a code
snippet *from a tracker collaborator* (per the collaborator-test in
Step 3's collaborator-test), reproduce it here so the user can confirm it's what
will be written. Snippets from non-collaborators must be quoted in
this section as *"untrusted suggestion, do not copy"* — never as the
literal code to write.

### 5c. Commit message and PR title

The commit message and the PR title must be **neutral bug-fix /
improvement language**. They must not contain any of:

- `CVE-YYYY-NNNNN`
- `CVE`, `vulnerability`, `security fix`, `advisory`
- any reporter name tied to a security finding
- the word *"sensitive"* in a way that points at an unmasked-credential
  bug
- explicit exploitation detail — a working payload, exact reproduction
  steps, or an exploit primitive

Naming the affected component or the bug class in neutral terms (for
example `SSRF`, `deserialization`, `path traversal`) is **allowed** — it
is ordinary bug-fix language, as the good examples below show. Only the
explicit security *framing* words above and reconstructable exploit
detail are forbidden. When enumerating `forbidden_terms_found`, list
only the framing terms above (and any reporter name / CVE id) that
actually appear — not neutral technical descriptors of the bug.

Tracker URLs (`https://github.com/<tracker>/issues/NNN`),
`<tracker>#NNN`, and bare `#NNN` references **are** allowed — they
are public-safe identifiers per the
[Confidentiality of the tracker repository](../../../../AGENTS.md#confidentiality-of-the-tracker-repository)
rule. The constraint is on the *security framing* of the
surrounding text, not on the identifier itself.

Good examples (neutral, accurate):

- *"Fix asset graph view leaking DAGs outside the user's permissions"*
- *"Add `access_key` and `connection_string` to DEFAULT_SENSITIVE_FIELDS"*
- *"Improve xcom value handling in extra links API"*

The PR description must describe the change, not the vulnerability.
It can and should reference the public documentation being changed
and include a test plan. Linking to the tracker URL as a stable
identifier is fine; explicitly characterising the change as *"this
fixes a security issue"* or *"closes vulnerability X"* is **not**
fine until the advisory has shipped.

### 5d. Test plan

List:

- existing tests that the change must continue to pass,
- new tests to be added that exercise the fix (required unless the
  change is a pure rename / typo fix),
- the exact commands the skill will run locally before pushing,
  taken from `<upstream>/AGENTS.md` and the toolchain block of
  [`<project-config>/fix-workflow.md`](../../../../<project-config>/fix-workflow.md#toolchain).
  Your project's invocation forms come from `fix-workflow.md` and
  typically cover a unit-test run, a fast static-check pass, a slow
  static-check pass, and a type-check where applicable.

### 5e. Backport label

If the `<tracker>` issue's milestone indicates a release branch
that has not yet been cut, note which backport label the PR should
carry so that the fix lands on the intended patch release. The
label vocabulary and the active release branches live in
[`<project-config>/fix-workflow.md`](../../../../<project-config>/fix-workflow.md#backport-labels)
and
[`<project-config>/release-trains.md`](../../../../<project-config>/release-trains.md).
If no backport is needed (the milestone is the next
`<default-branch>`-branch release), say so explicitly.

### 5f. Newsfragment

Per `<upstream>/AGENTS.md` and
`release_process.newsfragments` in
[`<project-config>/project.md`](../../../../<project-config>/project.md),
where the project ships a newsfragment / changelog-fragment tool,
fragments are typically only added for major or breaking
user-visible changes and usually coordinated during review. For a
security-adjacent bug fix, default to **not** adding a fragment in
the initial PR — reviewers will ask for one if needed. Never add a
fragment that describes the change as a security fix, because that
reveals the security nature and defeats the whole point of the
private tracking workflow. Skip this section entirely for projects
whose `release_process.newsfragments.enabled` is `false`.

**Commit-message-driven changelogs (no per-PR fragments).** Some
projects do not use fragment files at all — their changelog is
regenerated by the release manager from commit messages at
release-preparation time. On such a project the fix PR must **not**
author a new version header, a new category section (`Bug Fixes`,
`Features`, `Breaking changes`, …), or a bulleted / PR-linked
changelog entry — those are the release manager's to generate. The
only changelog edit a fix PR should make is, **when a notable
user-visible behaviour change needs surfacing**, a single note at the
very top of the changelog (above the first version header) describing
the change and any migration step; the release manager relocates and
formalises it into the right version at release. Whether the project
is fragment-based or commit-message-driven, and where such a note
goes, lives in
[`<project-config>/fix-workflow.md`](../../../../<project-config>/fix-workflow.md).
The neutral-language / no-security-framing rule above applies to the
note as well.

### 5g. PR body draft

Write out the exact `--body` the skill will pass to
`gh pr create --web`. Include:

- a brief description of the user-visible change,
- the test plan (markdown checklist),
- the Gen-AI disclosure block the project's contributing docs
  (`<upstream_contributing_docs_url>`) ask for; if they define none,
  use this one:

  ```markdown
  ##### Was generative AI tooling used to co-author this PR?

  - [X] Yes — <agent> (<model>)

  Generated-by: <agent> (<model>)
  ```

  Fill in `<agent>` and `<model>` with the actual agent and model
  you are running as (e.g. `Claude (Opus 4.8)`,
  `OpenCode (Big Pickle)`) — do not hardcode either.

Before presenting the body, **grep it for the forbidden terms** listed
in 5c and flag any hit to the user. Do not ship anything that matches.

---
