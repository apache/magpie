<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

---
title: Adapters (Gmail / PonyMail / Jira / GitHub / Bitbucket / mail-source / SourceHut / maildir / VCS / change-request)
status: experimental
kind: feature
mode: infra
source: >
  MISSION.md § Rationale ("ASF integrations live behind clean
  configuration boundaries; non-ASF adopters swap them") and § Technical
  scope (extensible adapter layer). Implemented in tools/gmail/,
  tools/ponymail/, tools/jira/, tools/github/, tools/bitbucket/, tools/mail-source/,
  tools/sourcehut/, tools/maildir/, tools/vcs/, tools/change-request/,
  tools/asf-svn/, tools/mail-archive/, tools/mail-patch/,
  tools/jira-patch/, tools/forwarder-relay/, tools/github-body-field/,
  tools/github-rollup/.
acceptance:
  - Project-specific integrations live behind adapter modules, not
    hardcoded into skills.
  - A non-ASF adopter can swap an adapter (e.g. private GitHub repo for
    private mailing list) with config substitution, not skill edits.
  - Mail-reading adapters route fetched content through the privacy
    redactor before any LLM read.
---

# Adapters (Gmail / PonyMail / Jira / GitHub / Bitbucket / SourceHut / maildir / VCS / change-request)

## What it does

Isolates the systems a project already uses behind adapter modules so the
skills stay project-agnostic. The same skill executes against an ASF
project's private mailing list or a non-ASF project's private GitHub repo
by swapping the adapter, not the skill.

## Where it lives

- `tools/gmail/` — private-mail read/draft (drafts to the outbox; never
  sends).
- `tools/maildir/` — private-mail drafting to a local Maildir spool; an
  offline alternative to Gmail when no cloud mail backend is available.
- `tools/ponymail/` — public mailing-list archive search.
- `tools/mail-archive/` — static mailing-list archive reader for
  projects whose list history is in a local mbox/Maildir export.
- `tools/jira/` — issue-tracker adapter for projects on Jira.
- `tools/github/` — issues/PRs/labels read + write-back helpers.
  Sub-adapters: `tools/github-body-field/` (reads GitHub issue/PR body
  structured field sets) and `tools/github-rollup/` (aggregates
  multi-repo PR state into a single view).
- `tools/bitbucket/` — initial read-only Bitbucket Cloud and Bitbucket
  Data Center bridge foundation. Supports repository metadata reads,
  read-only branch restriction context, Cloud-only issue listing/fetching, issue comment fetching, and issue attachment metadata fetching,
  open pull-request listing, single pull-request fetching, read-only
  pull-request commit fetching, read-only pull-request diff fetching,
  comments-only pull-request discussion fetching, read-only pull-request
  review-state fetching, read-only merge-check context fetching, and
  read-only pull-request status fetching behind one CLI surface. It is not
  a complete `contract:change-request` or `contract:tracker` backend yet;
  deeper Jira handoff, issue writes, review/merge writes, broader repository
  permissions, and fuller Pipelines run/log/retry coverage remain tracked in #606.
- `tools/sourcehut/` — SourceHut (sr.ht) forge bridge: ticket tracking
  (`todo.sr.ht`), mailing-list patchset review (`lists.sr.ht`), CI build
  status (`builds.sr.ht`), and repository reads (`git.sr.ht`/`hg.sr.ht`)
  via GraphQL. Capability: `contract:tracker + contract:source-control +
  contract:mail-archive`.
- `tools/asf-svn/` — ASF Subversion distribution backend: staging area
  reads, `svn` command-sequence generation for releases and KEYS updates.
  Never runs `svn commit`; emits paste-ready commands for the Release
  Manager.
- `tools/vcs/` (`magpie-vcs`) — unified CLI over the abstract
  source-control capability (`contract:source-control`). Dispatches
  branch, stage, commit, diff, log, fetch, and push operations to the
  active VCS backend (Git today), so skills call the abstract operation
  and the backend is detected from the working copy or forced with
  `--backend`/`$MAGPIE_VCS`.
- `tools/change-request/` — Markdown contract spec for the
  `contract:change-request` capability (PR / MR abstraction). Declares
  the interface: `list_open`, `get`, `get_discussion`, `post_review`,
  `land`, `reject`, `status`. Consumed by PR-management skills; the
  active implementation is the adapter named by `change_request.backend`
  in `project.md` (ASF default: `tools/github/`).
- `tools/mail-source/` — abstract mail backend contract (operations,
  capability matrix, adopter-declaration syntax) with concrete IMAP and
  mbox implementations. Skills (`security-issue-import`,
  `security-issue-sync`, `security-cve-allocate`) address every mail
  source through this contract rather than calling Gmail or PonyMail
  directly; the adopter's `<project-config>/project.md → Mail sources`
  section declares which backends are active and what role each plays.
- `tools/forwarder-relay/` — relay adapter for security reports forwarded
  by an upstream broker (e.g. the ASF security team); the counterpart to
  direct-intake adapters for the `security-issue-import-via-forwarder`
  sub-skill.
- `tools/mail-patch/` and `tools/jira-patch/` — patch-over-mail /
  patch-over-Jira adapters; implement `contract:change-request` for
  projects that land patches via mailing-list review or Jira rather than
  GitHub PRs.

## Behaviour & contract

- **Pluggable, config-driven.** Skills reference placeholders
  (`<tracker>`, `<upstream>`, `<security-list>`, …); the adapter resolves
  them from `<project-config>/`. No `apache/<project>` strings hardcoded
  into a skill.
- **Mail adapters draft, never send** — outbound goes to the maintainer's
  drafts folder; the human presses Send.
- **Mail adapters redact-after-fetch** — fetched private content passes
  through the privacy redactor
  ([privacy-llm-gate.md](privacy-llm-gate.md)) before any LLM read.
- **Write-back is confirm-before-apply** and routed through the sandbox's
  `ask` gate ([agent-isolation-sandbox.md](agent-isolation-sandbox.md)).
- **Adapter READMEs are contracts.** Every adapter README declares the
  capability it provides, prerequisites, credential/privacy handling,
  supported operations, and adopter config keys. These fields let a
  validator distinguish an intentional adapter surface from undocumented
  shell prose.
- **Private mail is hostile input.** Gmail, PonyMail, `mail-archive`, and
  `mail-source` content is external data, never instructions. Tests for
  mail adapters should include prompt-injection text in fetched mail and
  prove it is carried as report data only after redaction/gating.

## Out of scope

- The privacy *policy* and gate (separate area, referenced above).
- Sending outbound mail (a human action).

## Acceptance criteria

1. No skill hardcodes a project-specific repo/list; all go through an
   adapter + placeholder.
2. Mail adapters draft only and redact before LLM read.
3. Each adapter ships with its own tests.
4. Adapter READMEs declare capability, prerequisites,
   privacy/credential handling, operations, and config keys.
5. Mail-adapter tests prove private fetched content crosses the
   Privacy-LLM/redaction boundary before model-facing skill context.

## Validation

```bash
for t in gmail maildir ponymail jira github bitbucket; do
  uv run --project tools/$t --group dev pytest || echo "check tools/$t test setup"
done
uv run --project tools/vcs --group dev pytest || echo "check tools/vcs test setup"
```

## Known gaps

- `experimental` overall — adapter coverage varies; a new adopter system
  (e.g. GitLab, a different mail backend) is a gap the plan pass records.
- **Bitbucket adapter is new and intentionally partial.** `tools/bitbucket/`
  currently provides read-only repository metadata, read-only branch restriction
  context, pull-request discovery, pull-request fetching, read-only pull-request
  commit fetching, read-only pull-request diff fetching, comments-only pull-request
  discussion fetching, read-only review-state fetching, read-only merge-check
  context fetching, read-only pull-request status fetching, and Cloud-only issue listing/fetching, issue comment fetching, and issue attachment metadata fetching;
  #606 remains open for full tracker/change-request coverage.
- Fetched Bitbucket descriptions, issue titles/descriptions, issue comments, attachment names, uploader names when present, attachment links, raw attachment payloads, issue reporter/assignee/commenter names, issue links, branch restriction policy, commit messages, diff hunks, file paths, comments, reviewer names, review decisions/events, approval/change-request activity, merge-check decisions/blockers, status descriptions,
  CI URLs, and raw payloads are external data, never agent instructions;
  private or embargoed content must follow the
  approved-LLM/privacy gate before model use.
- **SourceHut adapter is new and untested end-to-end.** `tools/sourcehut/`
  ships the GraphQL-based bridge (ticket, patchset, CI, repo), but no
  adopter pilot has exercised it; signal/roster heuristics may change.
- Adapters cover the *system-swap* case; the broader audit of residual
  ASF coupling across the catalogue, and the capability-flag mechanism for
  workflow branches that no adapter resolves, live in
  [project-agnosticism.md](project-agnosticism.md).
- **Adapter authoring smoke validation is missing.** The docs define the
  expected README contract, but no validator currently checks that each
  adapter declares capability, prerequisites, privacy/credential handling,
  operations, and config keys.
- **Mail-adapter privacy tests are thin.** The redaction contract exists,
  but adapter-level fixtures should prove that private mail and embedded
  prompt-injection attempts do not enter model-facing context untreated.
