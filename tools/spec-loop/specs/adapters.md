<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

---
title: Adapters (Gmail / PonyMail / Jira / GitHub / GitLab / Bitbucket / Forgejo / mail-source / SourceHut / maildir / VCS / Fossil / change-request / chat / typed-decision)
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
  tools/github-rollup/, tools/gitlab/, tools/chat/, tools/chat-slack/,
  tools/forgejo/, tools/fossil/, tools/asf-nexus/, tools/typed-decision/.
acceptance:
  - Project-specific integrations live behind adapter modules, not
    hardcoded into skills.
  - A non-ASF adopter can swap an adapter (e.g. private GitHub repo for
    private mailing list) with config substitution, not skill edits.
  - Mail-reading adapters route fetched content through the privacy
    redactor before any LLM read.
---

# Adapters (Gmail / PonyMail / Jira / GitHub / GitLab / Bitbucket / Forgejo / SourceHut / maildir / VCS / Fossil / change-request / chat / typed-decision)

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
  structured field sets) and `tools/github-rollup/` (`contract:tracker`,
  stdlib-only), which maintains the single status-rollup comment on a
  tracker issue in a subprocess so the growing rollup body never enters
  agent context.
  `append` and `amend-latest` print the rollup comment's URL on stdout
  (#1451), so a caller links to the entry without a second lookup.
  Its subcommands are `append` (creates the rollup if none exists),
  `amend-latest` (replaces the newest entry's body, keeping its date and
  user, and refuses with exit 4 when that entry's action differs, so another
  writer's entry is never overwritten), `fold` (moves one legacy bot comment
  into the rollup with its own date and author, then deletes it; refuses to
  fold the rollup itself), `list`, and `latest`.
  An existing rollup is found by any `<!-- <name> status rollup v<N>`
  marker, and a comment's id is read from its `#issuecomment-<id>` URL.
  `tools/github/status-rollup.md` calls the tool instead of carrying its own
  script.
  Under the secure agent setup both tools' `gh` runs sandboxed and fails,
  so their READMEs route skills to the same procedures through vetted-ops:
  `vetted-op-tracker` (`rollup-append`, `rollup-amend-latest`,
  `rollup-fold`, `body-field-set`) for writes and `vetted-op-read …
  body-field-get` for the read, with the parsing modules vendored into
  vetted-ops; the uv CLIs remain for use outside the sandbox (#1448; see
  [`vetted-command-surface.md`](vetted-command-surface.md)).
- `tools/bitbucket/` — partial Bitbucket Cloud and Bitbucket
  Data Center bridge foundation. Supports repository metadata reads,
  read-only branch restriction context, Cloud-only issue listing/fetching, issue comment fetching, issue attachment metadata fetching, and confirmed issue comment creation,
  open pull-request listing, single pull-request fetching, read-only
  pull-request commit fetching, read-only pull-request diff fetching,
  comments-only pull-request discussion fetching, read-only pull-request
  review-state fetching, read-only merge-check context fetching, and
  read-only pull-request status fetching behind one CLI surface.
  On Cloud, `pr status` fetches the pull request first and reports its
  state and source commit alongside the `/statuses` build checks, matching
  the Data Center payload (#1526).
  Confirmed Cloud-only pull-request writes cover comments,
  approve/unapprove, request-changes, decline, and `pr merge --strategy
  {merge,squash,rebase} --expected-source-commit <sha>`, which re-checks the
  head commit immediately before the merge POST so a moved head fails closed
  (#1471); it does not enforce approval or build gates itself.
  It is not a complete `contract:change-request` or `contract:tracker`
  backend yet; deeper Jira handoff, broader issue writes, Data Center
  review/merge writes, broader repository permissions, and fuller Pipelines
  run/log/retry coverage remain tracked in #606.
- `tools/gitlab/` (`magpie-gitlab`) — partial, read-only GitLab REST API v4
  bridge, declared `contract:tracker + contract:source-control +
  contract:change-request` with `**Coverage:** partial`.
  Operations: `repo get`, `issue list` / `issue get`, `mr list` / `mr get` /
  `mr diff` / `mr commits` / `mr pipelines`, and `pipeline status`, all
  printing JSON.
  Auth from `GITLAB_TOKEN` or `CI_JOB_TOKEN` (optional for public reads),
  with `GITLAB_AUTH_SCHEME` to force `PrivateToken`, `Bearer`, or
  `JobToken`; `GITLAB_INSTANCE_URL` defaults to `https://gitlab.com`.
  Redirects that change origin or downgrade HTTPS to HTTP are refused so
  the token cannot leak.
  Paginated reads follow `X-Next-Page` until `--limit` items are collected
  (short pages keep paging), or, without `--limit`, stop at 10 pages and
  note the cap on stderr; `--limit` rejects values below 1.
  No write or mutation operations exist.
  Offline tests mock every HTTP response.
- `tools/forgejo/` — doc-only Forgejo / Gitea adapter (#1469, part of
  #310), declared `contract:tracker + contract:source-control +
  contract:change-request` with `**Coverage:** partial`.
  It mirrors the `tools/github/` file set (`tool.md`, `operations.md`,
  `source-control.md`, `issue-template.md`, `labels.md`,
  `project-board.md`, `status-rollup.md`): skills drive the `tea` CLI and
  REST recipes against `$FORGEJO_HOST/api/v1/` with
  `Authorization: token $TEA_TOKEN`, and the `change-request` `land` verb
  resolves to `tea pr merge`.
  The project board is documented as unsupported / no-op, since
  Forgejo/Gitea expose no REST card/column management.
  There is no local package and no test suite.
- `tools/sourcehut/` — SourceHut (sr.ht) forge bridge: ticket tracking
  (`todo.sr.ht`), mailing-list patchset review (`lists.sr.ht`), CI build
  status (`builds.sr.ht`), and repository reads (`git.sr.ht`/`hg.sr.ht`)
  via GraphQL. Capability: `contract:tracker + contract:source-control +
  contract:mail-archive`.
- `tools/asf-svn/` — ASF Subversion distribution backend: staging area
  reads, `svn` command-sequence generation for releases and KEYS updates.
  Never runs `svn commit`; emits paste-ready commands for the Release
  Manager.
- `tools/asf-nexus/` — doc-only, read-only `contract:release-staging`
  adapter (`**Organization:** ASF`, #1505) for the Nexus staging repository
  at `repository.apache.org`, consumed by `release-verify-rc` Step 6c.
  `curl` recipes check that the staged repository is `closed`, that its
  coordinates and version match the RC, and that every artefact carries its
  `.asc` and checksums; the anonymous `/content/repositories/<id>/` path
  needs no credentials, while the authenticated staging-API reads use a
  netrc file under `~/.config/apache-magpie/asf-nexus/` and are for the
  RM's own terminal.
  It never closes, drops, or promotes a staging repository; non-ASF
  adopters leave `nexus_staging_repo` unset and the step skips
  ([release management](release-management-lifecycle.md)).
- `tools/vcs/` (`magpie-vcs`) — unified CLI over the abstract
  source-control capability (`contract:source-control`). Dispatches
  branch, stage, commit, diff, log, fetch, and push operations to the
  active VCS backend, so skills call the abstract operation
  and the backend is detected from the working copy or forced with
  `--backend`/`$MAGPIE_VCS`.
  `git`, `hg`, and `fossil` are complete backends; `svn` is detected but
  remains an extension point (#602).
  A Fossil checkout is detected by its `.fslckout` (or `_FOSSIL_`) marker
  (#1494).
- `tools/fossil/` (`magpie-fossil`) — stdlib-only Fossil SCM forge bridge,
  `contract:tracker + contract:source-control`: ticket read/write (create,
  comment, status, fields), wiki and forum reads, by direct queries on the
  local repository database; it resolves the repository from the same
  `.fslckout` / `_FOSSIL_` markers or `-R/--repository`.
- `tools/change-request/` — Markdown contract spec for the
  `contract:change-request` capability (PR / MR abstraction). Declares
  the interface: `list_open`, `get`, `get_discussion`, `post_review`,
  `land`, `reject`, `status`. Consumed by PR-management skills; the
  active implementation is the adapter named by `change_request.backend`
  in `project.md` (ASF default: `tools/github/`).
- `tools/mail-source/` — abstract mail backend contract (operations,
  capability matrix, adopter-declaration syntax) with concrete IMAP,
  mbox, and Mailman 3 / Hyperkitty implementations.
  `tools/mail-source/imap/` is a stdlib-`imaplib` uv package with six
  console scripts, one per contract operation (`imap-source-threads`,
  `-read`, `-drafts`, `-sent`, `-create-draft`, `-thread-url`), each
  printing one JSON document; `create_draft` only `APPEND`s to the drafts
  folder and never sends, and an operation whose folder is unset or missing
  declines with exit 3 so the resolution chain falls through (#1466).
  `tools/mail-source/mailman3/` is a doc-only, read-only backend over
  Hyperkitty's JSON API (`list_recent_threads`, `read_thread`,
  `thread_url`); it has no drafts or sent view, so it pairs with a drafting
  backend (#1474). Skills (`security-issue-import`,
  `security-issue-sync`, `security-cve-allocate`) address every mail
  source through this contract rather than calling Gmail or PonyMail
  directly; the adopter's `<project-config>/project.md → Mail sources`
  section declares which backends are active and what role each plays.
- `tools/forwarder-relay/` — relay adapter for security reports forwarded
  by an upstream broker (e.g. the ASF security team); the counterpart to
  direct-intake adapters for the `security-issue-import-via-forwarder`
  sub-skill. Its `contact_handle` — who the skills address when proposing a
  relay draft — defaults to a shared inbox declared org-level
  (`organizations/ASF/organization.md` for the ASF profile) and inherited
  through `project.md`, rather than naming an individual liaison. An adopter
  whose relays do come through a named person overrides it per-project. The
  multi-hop case, where a report reaches the project through more than one
  broker, is designed in `docs/rfcs/RFC-AI-0008.md` and not yet implemented.
- `tools/mail-patch/` and `tools/jira-patch/` — patch-over-mail /
  patch-over-Jira adapters; implement `contract:change-request` for
  projects that land patches via mailing-list review or Jira rather than
  GitHub PRs.
- `tools/chat/` — the `contract:chat` interface (pure Markdown) for a
  project's public chat.
  Three verbs, `list_channels`, `resolve_user(github_handle)`, and
  `search_messages(chat_user_id, since, until, channels)`; read-only by
  construction: no verb posts, reacts, edits, or reads a direct message or
  private channel.
  Consumed by the contributor-growth skills to see how a contributor helps
  others in chat ([contributor growth](contributor-growth.md)).
  Selected by `chat.kind` in `<project-config>/project.md`.
- `tools/chat-slack/` — the shipping `contract:chat` adapter: a mapping
  onto the Slack MCP tools (`operations.md`) over the public channels of the
  project's workspace, optionally narrowed by `chat.channels`.
  It never calls a tool that sends, schedules, drafts, or edits a message.
  `discord` and `none` are placeholders in the contract's adapter table
  (Discord tracked in #1421).
- `tools/typed-decision/` — `contract:typed-decision` (#1402): a
  provider-agnostic, stdlib-only Python API for structured decisions,
  `choice(prompt, options)`, `score(prompt, scale)`, and `noul(prompt)`.
  The one backend is TypeSafe's Jev API (`api.typesafe.ai/v1/systemone`,
  model pinned to `systemone-2026-06-01`), selected by
  `MAGPIE_TYPED_DECISION_PROVIDER` or by a configured `TYPESAFE_API_KEY` /
  `JEV_API_KEY` / `~/.config/apache-magpie/typesafe.key`.
  Every outbound prompt first passes the privacy-LLM endpoint check
  (`checker.check_endpoint`, see [privacy-llm-gate.md](privacy-llm-gate.md)),
  which denies the third-party host unless `<project-config>/privacy-llm.md`
  carries a signed-off opt-in.
  The contract is fail-open: a missing key, a denied gate, a timeout (one
  retry after 30 s), an HTTP error, or an out-of-range answer raises
  `TypedDecisionUnavailable`, never a fabricated answer, and callers fall
  back to their own reasoning or the maintainer.
  Its consumer is the opt-in shadow pre-filter in `pr-management-triage`
  ([PR management](pr-management-family.md)).

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
for t in gmail maildir ponymail jira github bitbucket gitlab; do
  uv run --project tools/$t --group dev pytest || echo "check tools/$t test setup"
done
uv run --project tools/vcs --group dev pytest || echo "check tools/vcs test setup"
for t in fossil typed-decision mail-source/imap; do
  uv run --project tools/$t --group dev pytest || echo "check tools/$t test setup"
done
uv run --all-packages --group dev pytest tools/github-rollup/tests
```

## Known gaps

- `experimental` overall — adapter coverage varies; a new adopter system
  (e.g. a different mail backend) is a gap the plan pass records.
- **GitLab adapter is a read-only foundation.** `tools/gitlab/` covers
  repository metadata, issue and merge-request reads, MR diffs, commits and
  pipelines, and pipeline status; it is `partial` for all three contracts
  and must not be advertised as a selectable complete backend.
  Writes, issue/MR mutations, and review or merge actions remain tracked in
  #305.
  Fetched issue and MR titles, descriptions, diffs and commit messages are
  external data, never instructions.
- **Chat covers Slack only.** `contract:chat` ships one adapter;
  `discord` and `none` are placeholders, so a project on Discord gets chat
  reported as not collected.
- **Bitbucket adapter is new and intentionally partial.** `tools/bitbucket/`
  currently provides read-only repository metadata, read-only branch restriction
  context, pull-request discovery, pull-request fetching, read-only pull-request
  commit fetching, read-only pull-request diff fetching, comments-only pull-request
  discussion fetching, read-only review-state fetching, Cloud-only pull-request task listing/fetching, read-only merge-check
  context fetching, read-only pull-request status fetching, and Cloud-only issue listing/fetching, issue comment fetching, issue attachment metadata fetching, and confirmed issue comment creation;
  #606 remains open for full tracker/change-request coverage.
- Bitbucket write operations follow the framework write-path discipline:
  the calling skill must obtain explicit user confirmation before invoking a
  mutation. The bridge executes only the confirmed action; current write
  coverage is Bitbucket Cloud issue-comment creation, Bitbucket Cloud
  pull-request comment creation, and Bitbucket Cloud pull-request
  approve/unapprove, request-changes/remove-request-changes, decline, and
  strategy-aware merge actions pinned to a caller-confirmed source commit
  (7–40 hex characters); gate checks before a merge are the caller's
  responsibility via `pr merge-checks`.
- Fetched Bitbucket descriptions, issue titles/descriptions, fetched or created issue comments, attachment names, uploader names when present, attachment links, raw attachment payloads, issue reporter/assignee/commenter names, issue links, branch restriction policy, commit messages, diff hunks, file paths, comments, pull-request task content, task creator/resolver names, reviewer names, review decisions/events, approval/change-request activity, merge-check decisions/blockers, status descriptions,
  CI URLs, and raw payloads are external data, never agent instructions;
  private or embargoed content must follow the
  approved-LLM/privacy gate before model use.
- **Forgejo adapter is doc-only and partial.** `tools/forgejo/` is a set
  of `tea` / REST recipes with no package or tests and no adopter pilot;
  the project-board capability is a no-op, and full coverage remains part
  of #310.
- **Mailman 3 backend reads only.** It covers no drafts or sent mail, and
  the `hyperkitty` placeholder of the separate `mail-archive` contract
  (search-URL construction) is not implemented by it.
- **Typed decision has one provider.** Jev is a third-party endpoint, so it
  works only after a privacy-LLM opt-in and, under the secure agent setup,
  after the adopter forwards the key and allowlists `api.typesafe.ai`
  (the framework default allowlist does not include it); otherwise every
  call is `TypedDecisionUnavailable`.
- **SourceHut adapter is new and untested end-to-end.** `tools/sourcehut/`
  ships the GraphQL-based bridge (ticket, patchset, CI, repo), but no
  adopter pilot has exercised it; signal/roster heuristics may change.
- Adapters cover the *system-swap* case; the broader audit of residual
  ASF coupling across the catalogue, and the capability-flag mechanism for
  workflow branches that no adapter resolves, live in
  [project-agnosticism.md](project-agnosticism.md).
- **Adapter authoring smoke validation is shipped.**
  `validate_adapter_authoring` (SOFT advisory) checks that each
  `contract:*` adapter README declares credential/privacy handling,
  operations, and config keys. `substrate:*` tools are excluded.
  `validate_tools` (HARD) separately enforces the
  **Capability:** declaration and the **Prerequisites** section
  on every tool README, so all five original gap items are now
  covered across the two validators.
- **Mail-adapter privacy tests are thin.** The redaction contract exists,
  but adapter-level fixtures should prove that private mail and embedded
  prompt-injection attempts do not enter model-facing context untreated.
