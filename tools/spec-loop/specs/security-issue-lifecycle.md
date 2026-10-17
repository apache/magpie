<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

---
title: Security-issue lifecycle (end-to-end)
status: stable
kind: feature
mode: Triage
source: >
  MISSION.md § Rationale ("Security-issue handling is a load-bearing use
  case"). README.md § Skill families (security). The security skill
  family + tools/cve-tool-vulnogram + tools/gmail + tools/ponymail +
  tools/privacy-llm.
acceptance:
  - The flow runs import → triage → dedupe → CVE allocate → fix → sync →
    invalidate, each step a confirm-before-apply skill.
  - Tracker contents stay private; only stable identifiers (URLs, #NNN)
    are public-safe. Public PRs are scrubbed pre-disclosure.
  - Every applied state change is audit-logged.
---

# Security-issue lifecycle

## What it does

The framework's flagship, highest-procedure flow: handle an inbound ASF
security report end-to-end, from `security@` import through CVE
publication, with a human gate and an audit-log entry at every step.

## Where it lives

- Skills: `security-issue-import` (+ `-from-pr`, `-from-md`,
  `-from-scan`, `-via-forwarder`),
  `security-issue-triage`, `security-issue-deduplicate`,
  `security-cve-allocate`, `security-issue-fix`, `security-issue-sync`,
  `security-issue-invalidate`.
  `security-issue-import-from-scan` is the scanner on-ramp: it ingests
  multi-finding scan output through a pluggable scan-format adapter
  (`tools/scan-format/`), buckets each finding for operator review, and
  creates trackers only after per-finding confirmation.
  `security-issue-import-via-forwarder` is the relay sub-skill: handles
  reports relayed by an upstream broker (ASF security team or a
  third-party disclosure platform) by applying preamble-detect,
  credit-extract, and routing rules declared in
  `tools/forwarder-relay/`; never mutates tracker state on its own.
- Skill files live at `plugins/magpie-security/skills/<alias>/SKILL.md`
  (alias drops the `security-` prefix, e.g. `issue-import`), reached
  from `skills/security-<name>` symlinks.
  Oversized `SKILL.md` files were split (#1436): each keeps its
  orchestration (golden rules, Step 0, every step heading, gates, hard
  rules) and moves the elaboration verbatim into linked siblings one link
  away, such as `issue-import/apply.md`, `screening-and-proposal.md`,
  `duplicate-search.md`; `issue-fix/implementation-plan.md`,
  `tracker-update.md`; `issue-triage/classification.md`;
  `issue-sync/mail-preflight.md`, `next-step.md`;
  `cve-allocate/tracker-updates.md`, `title-normalize.md`.
  The tracker body templates of `issue-import-from-md` and
  `issue-import-from-pr` live in a `tracker-body-template.md` sibling of
  each (#1499).
  Moved headings keep a one-line pointer in `SKILL.md` so anchors still
  resolve, and eval `step-config.json` files point at the sibling.
- `tools/security-management` (stdlib, runs nothing) holds the
  deterministic rules of the security skills, one CLI family per skill
  over a shared library (`body`, `rollup`, `refs`, `titles`, `grammar`,
  `keyword`). For `security-issue-import` it decides the Step 0
  disclosure-governance defaults, the Step 1 pre-filter, the Step 2
  `threadId` batches and their attribution, the Step 3 forwarder
  pre-screen, the Step 6 reply grammar and the Step 7 receipt-draft
  matrix, and renders the tracker body (the report as an inert fenced
  block, `_No response_` for empty fields, headings from
  `tracker.body_fields`), the rollup entry,
  the rejections-ledger record, the fix-already-public reply and the
  Step 8 recap. Classification, field extraction, PII identification,
  fuzzy duplicates and canned-response choice stay with the model;
  report text reaches the tool only in files the Write tool created.
  For `security-issue-import-from-pr` it parses the PR reference
  (refusing other repositories), detects the scope from the changed
  files (tests stripped, mixed-scope stop, sub-packages of one scope),
  checks the milestone by exact match, builds the duplicate query (warning
  at 30 hits), and renders the title, body (sentinels, bot author left
  `_No response_`), labels, rollup entry and recap; the milestone
  choice, title paraphrase and *Affected versions* stay with the model.
  For `security-issue-import-from-md` it parses the findings file
  (`not-a-findings-file` on another shape, `UNKNOWN` severity and
  `<upstream>` fallback with warnings), cleans the search keyword, and
  renders the body (each section an inert block, the Recommended-fix
  `<details>`), rollup entry, proposal table and recap; duplicate
  judgement and the credit decision stay with the model.
  For `security-issue-import-via-forwarder` it runs the Step 0 checks,
  detects the adapter (first enabled match wins, collaborator warning),
  classifies a credit's kind under the bot/AI policy and routes the draft
  (first contact handle, question mode, negative-space suppression in
  sync); credit-line extraction and naming the milestone stay with the
  model, and it never redacts again.
  For `security-issue-import-from-scan` it enforces that only the
  import-as-tracker bucket creates a tracker, renders the per-scan and
  cross-scan triage report, parses the operator's decision and lists the
  scrub hits of a public report without rewriting it; bucketing and its
  grounding stay with the model.
- Shared recipes instead of per-skill copies (#1437): the safe-create
  recipe for a tracker with an attacker-controlled title is
  `tools/github/operations.md` § *Create* (Write-tool title file,
  `gh api -F title=@<file>`), and the import skills and
  `security-issue-invalidate` point at `tools/github/project-board.md`
  for the orphan-issue, introspection and archive board recipes.
- Status rollups are written by `tools/github-rollup/`
  (`append`, `amend-latest`, `fold`, `list`, `latest`).
  Under the secure setup that CLI's `gh` runs sandboxed and fails, so the
  same rollup and body-field procedures are reachable through the
  sandbox-exempt `vetted-op-tracker` entry point (`rollup-append`,
  `rollup-amend-latest`, `rollup-fold`, `body-field-set`) and
  `vetted-op-read … body-field-get` (#1448; see
  [`vetted-command-surface.md`](vetted-command-surface.md)).
  Since #1451 the security skills call those procedures for every rollup
  and single-field write (import, import-from-md, import-from-pr,
  invalidate, deduplicate, cve-allocate, issue-fix, sync), so the rollup
  and the issue body never enter the agent's context.
  Entry templates keep their body text; the tool writes the `<details>`
  envelope and the marker line.
  `rollup-amend-latest` fills invalidate's draft id into the entry it
  just wrote, `rollup-fold` replaces the hand-rolled fold-legacy
  sequences and deletes the legacy comment only after the append
  succeeded, and `body-field-get` / `body-field-set` replace whole-body
  rewrites that touched one field; sync keeps a whole-body write only
  where it adds sections the body lacks.
  Each skill notes once how to run the same operations without the
  secure setup, through the `github-rollup` and `github-body-field` CLIs.
- Tools: `tools/cve-tool-vulnogram/generate-cve-json` (CVE 5.x JSON),
  `tools/cve-org`, `tools/gmail` + `tools/ponymail` (mail), and the
  `tools/privacy-llm` gate/redactor ([the privacy gate](privacy-llm-gate.md)).

## Behaviour & contract

- **Confirm-before-apply at every step.** Imports create trackers only
  after confirmation; triage posts proposal comments and never decides;
  allocation is PMC-gated; fixes draft PRs the human opens.
- **Confidentiality (three layers, see `AGENTS.md`):** tracker URLs and
  `#NNN` are public-safe identifiers; tracker *contents* are private;
  the security framing of a public PR is embargoed until the advisory
  ships.
- **Report text is inert in the tracker (#1672).** The importers put
  reporter-derived long text (the mail body, the PR description, each
  findings-file section) into the body as one fenced block with info
  string `text`, its fence one backtick longer than the longest backtick
  run in the text. Nothing in it renders — no image, HTML, heading, link
  or mention — and its content is byte-exact except two escapes: a line
  that would end a field (`###` then a space, a tab or nothing, at column
  0 or behind `>`, list markers or indent, whatever the name), and a line
  starting with `<!--` (a machine marker), each get a leading `\` and are
  listed in `escaped_lines`. Short fields
  stay one-line escaped values. The rendered body must pass
  github-body-field's normaliser (exactly the template fields once each,
  nothing to decide) or the render is refused. Reporter formatting
  therefore shows as plain text.
- **Field reads and writes fail closed (#1672).** github-body-field is the
  one implementation of the body-field contract, for reading and writing;
  generate-cve-json and vetted-ops (a byte-identical copy) read through
  it. Every `###` line at column 0 (then a space, a tab or nothing) ends a
  field, code block or not, so no fence or macro can merge two fields;
  closed code blocks (CommonMark fence pairs, Jira `{code}` /
  `{noformat}` blocks) only choose which `### <name>` is the field — the
  one outside every closed block; a field quoted only inside closed blocks
  is absent — and a block left open marks nothing. A Jira macro opened
  mid-line before field headings is a `macro-ambiguous` decision. Two copies outside closed blocks with different
  values are a `duplicate` decision; a heading-shaped line that ends no
  field but names a known field is a `container-heading` decision, never
  taken and never ignored. `extract_field` / `body-field-get` refuse an
  ambiguous field and `replace_field` / `body-field-set` refuse a value
  holding a line that would end the field, a span holding a
  heading-shaped line, and a rewrite that would change another field. The
  local-files tracker and the Jira bridge read and write fields through
  byte-identical copies of the parser (the Jira bridge after reading wiki
  `h1.`–`h3.` headings outside closed blocks as `### <Heading>`), matching
  names case-insensitively; a test runs every implementation over the same
  bodies and requires the same reads and writes.
- **CVE fields come from the team or a confirmed proposal (#1672).** When
  `generate-cve-json --report-json` lists missing or ambiguous fields,
  sync, cve-allocate and deduplicate follow
  `issue-sync/outcomes/cve-json-fallback.md`: the session's own model
  proposes values (never *Severity*, never the CVE link), the user
  confirms each, and the rollup records them as AI-proposed; a duplicate
  is resolved by the user's choice through `body-field normalise --keep`
  and a confirmed whole-body rewrite.
- **Reporter PII redacted in-context; reporter *credit* preserved** in
  the CVE `credits[]` only after the reporter confirms on the thread.
- **Audit log** of every applied change (redacted identifiers only).
  The per-tracker status rollup is recognised by a first line carrying the
  canonical `<!-- apache-magpie: status-rollup v<N> -->` marker or the
  legacy `<!-- <name> status rollup v<N>` one (#1444), the canonical one
  winning when a tracker carries both, and a new rollup always gets the
  canonical marker, so the rollup works on any adopter's tracker and is
  never duplicated under a second marker (#1665).
  `amend-latest` fills in a value on the newest entry (refusing when that
  entry has a different action), and `fold` moves a legacy bot comment
  into the rollup, deleting the original only after the append succeeds.
- **One forbidden-term list for public PRs.** `security-issue-fix` 5c is
  the single list that 5g, Step 7, Step 9 and the guardrails check
  against: CVE IDs, `CVE`, `vulnerability`, `security fix`, `advisory`,
  `security@`, vulnerability-class names (for example `SSRF`,
  `path traversal`), reporter names, and exploitation detail.
  Naming the affected component and the behaviour change neutrally is
  allowed.
  A `<tracker>` link is also allowed in the public PR body, as a bare
  identifier with no security framing around it; the skill's description
  and golden rules no longer forbid linking back to the tracker (#1447).
  The agent-guard `security-language` guard is a backstop on
  `gh pr create` / `gh pr edit`, not a replacement: it covers a subset of
  the list and never sees the commit message, branch name, or
  newsfragment (#1444).
- **Subversion projects fix through a private patch, then a gated
  commit.** `security-issue-fix` picks its flow with
  `magpie-vcs fix-flow --declared <Tools enabled → Source control>`:
  Git keeps the PR flow; `svn` (`asf-svn`) takes the
  `patch-then-commit` flow in `issue-fix/subversion-flow.md`, because
  there `commit` and `new-branch` are the publication.
  The patch is attached to the tracker (or posted as a private comment
  on a GitHub tracker) and drafted to `<security-list>`; only after the
  user confirms the team cleared it does `magpie-vcs propose-commit`
  scrub the message, the diff, new files and the branch name, refuse
  paths outside the agreed file list, and print the commands, and
  `commit --scrub` / `new-branch --scrub` repeat the scrub before the
  VCS runs (exit `3` on a hit).
- **Adversarial review before a PR, on public content only.**
  `security-issue-fix`, `security-issue-import-from-pr` (over the patch it
  verifies) and `security-issue-import-from-scan` carry the shared
  pre-PR adversarial-review block (#1372).
  Unlike other families, the security family runs it whenever at least
  one reviewer is configured, whatever the configured `mode`.
  Reviewers see only the diff and the PR title and body exactly as they
  will be posted, after the skill's own forbidden-term check; never
  tracker text, an unpublished CVE ID, reporter detail, or mail.
  The review never runs against the private tracker checkout, and its
  findings are advisory data that never block the flow.
- **Attacker-controlled titles never reach a shell argument.** Tracker
  creation from a report title goes through the safe-create recipe
  (title written to a file, passed by `-F title=@<file>`), never
  `gh issue create --title '<title>'` (#1437).
- **Import dedup searches follow a provisional class.**
  `security-issue-import` Steps 2a and 2c skip their searches for a
  candidate whose provisional class, read from the root message, is
  never-a-tracker; if Step 3 then classes it as a `Report` (or
  forwarder-relayed), the skipped searches run before Step 4 (#1444).
- **Pre-flight declares what each skill cannot run without.** Every
  security skill lists its required `<project-config>` files in
  `requires_config:`, which the generated pre-flight block checks before
  the run starts (triage, invalidate, import-from-md and model-update
  gained declarations in #1444).
  Snapshot-drift detection is the generated pre-flight's job; the
  per-skill *Snapshot drift* prose sections were removed (#1435).
- **Fetch once per run, not once per item (#1443).**
  Shared reads are fetched once and reused, without changing which items
  are processed or how each is decided.
  `security-issue-import` reads each mail thread in full once (Step 2a)
  for Steps 3 and 4, keeping one fresh read at Step 7 because a draft or
  reporter reply can land between scan and apply; the semantic-sweep list
  of open trackers, the collaborator list and the rejections-ledger number
  are fetched once per run, and thread-id dedup searches carry up to 6 ids
  per query.
  `security-issue-triage` gathers body, comments and linked PRs with one
  aliased GraphQL query per chunk of up to 20 trackers, and
  `security-issue-invalidate`'s `invalidate proposed` fetches reactions
  and state the same way instead of a reactions call and an issue view
  per tracker.
  `security-issue-sync` takes linked PRs and their authors from one query
  and the hand-off comment and milestone bullet from its first issue read.
  `security-issue-import-from-scan` fetches the open-tracker list once for
  all findings, `-from-md` sets labels at creation, and `-from-pr` runs one
  duplicate search instead of two.
  Every batched list call keeps an explicit `--limit` and says what to do
  at the cap: triage and invalidate list with `--limit 1000`, and
  invalidate stops and surfaces a list that returns exactly 1000 rather
  than proceed on a possibly truncated set; a dedup search returning
  exactly its limit is treated as possibly truncated.
- **Obvious no-ops are skipped before any per-item model work (#1449).**
  A deterministic check drops items the full pass would also no-op,
  before a body read or a classification runs.
  Every skip is listed with its rule, a borderline item is kept, and
  `--no-preflight` turns the check off.
  `security-issue-triage` skips a tracker whose newest comment is its own
  triage proposal by a team member with no later tracker or mail
  activity; `--retriage` and explicitly numbered trackers are never
  skipped.
  `security-issue-import` drops CVE-tool bookkeeping mail by subject and
  sender in Step 1, before any thread body is read; the Step 3 row stays
  as the backstop for the body-line variant, pre-filtered threads are
  counted at Step 5 and listed at Step 8, and `keep <threadId>` sends one
  back through Steps 2 to 5.
  The forwarder sub-skill is invoked only when `forwarders.enabled` is set
  and a message matches an enabled adapter's sender or preamble pattern,
  a strict subset of the sub-skill's own *not a relay* outcome.
  `gh` calls that were wrapped in `$(…)` or piped are now plain commands,
  which the secure setup needs; #1453 made the last one plain too
  (`security-issue-invalidate` Step 1 no longer redirects `gh issue view`
  into a file, it reads the JSON the plain command prints).
  Keyword dedup and fix-already-public searches (`security-issue-import`
  Steps 2a–2c, `-from-md` Step 2) clean the attacker-controlled keywords
  with `tr -cd 'A-Za-z0-9._ -'` into a file as one command, then run a
  plain `gh search` with the cleaned keywords single-quoted, never a
  variable set in the same command (#1465).
  `security-issue-import-from-pr` reads the upstream PR, description
  included, through vetted-ops' `pr-view-with-body` read operation instead
  of a redirected `gh pr view`, and sets its configured labels at tracker
  creation (#1457).
- **Bulk sync pre-flight and CVE push rules (#1501).**
  In `security-issue-sync` bulk mode the 24-hour `dispatch-urgent` rule
  (a non-skill comment under a day old) is checked before the 7-day
  `updatedAt` safety override, which would otherwise always catch it
  first; `tools/preflight-audit`'s classifier uses the same order.
  Trackers named by a CVE ID selector (`sync CVE-…`), like explicit issue
  numbers, are never skipped by pre-flight.
  At Step 5b a `not-configured` CVE-tool session skips the push silently
  on ordinary runs, but on a `fix released` transition, where the record
  still needs `allocated → review-ready`, it raises the same deferral
  blocker in the Step 6 recap as an `expired` session.
- **CVE selector and push overrides (#1554, #1558).**
  A `sync CVE-…` selector matches a tracker only when the ID appears in
  its *CVE tool link* field, so a related or cross-referenced CVE elsewhere
  in the body does not select it.
  The bulk pre-flight reviews its batched GraphQL result through a `jq`
  projection of state, labels and last-comment metadata that never prints
  the last comment's body.
  The Step 5b push merges into the live record; `--replace-references`
  (to drop a reference that must no longer appear) and
  `--allow-product-change` (only while the record is still `DRAFT`) are
  used only after the user confirms.
- **Small always-on footprint (#1447).**
  Each security skill's `description` and `when_to_use`, which load in
  every session, state only its purpose, main trigger phrases and where
  to route instead; the family's always-on total dropped from about 1.6k
  to about 1.1k tokens.
- **Mandatory mail backends are a hard stop.** In `security-issue-sync`,
  a `mandatory: yes` backend that is unavailable or unauthenticated,
  PonyMail included, stops the run; only `mandatory: no` backends degrade
  quietly (#1444).
- **Project-neutral content.** Release numbers, backport labels and
  maintainer names come from `<project-config>/release-trains.md` and the
  other adopter files, not from the skills; `security-issue-fix` links the
  project's PR conventions through `upstream_contributing_docs_url` in
  `project.md` (#1407, #1444).
  Scratch files use the absolute session scratch directory (`<scratch>`),
  not literal `/tmp` paths the sandbox cannot write, so `gh` running
  outside the sandbox resolves the same file.
- **An unresponsive reporter never blocks the team.** When
  `security-issue-sync` finds the reporter thread stale — the team's last
  outbound message older than
  `security_inbox.reporter_response_timeout_days` with no reply since —
  its step 2b proposes proceeding with fix and announcement without
  further reporter sign-off, per ASF security policy, and never a
  follow-up asking the reporter to confirm they are still engaged. The
  rule is restated in the step body rather than left to
  `signals-to-actions.md`, because it carries policy (#1340).
- **The post-advisory security-pages update is tracked, not performed.**
  Both release-manager hand-off comment variants carry a
  `Project security pages updated with CVE_ID` checkbox behind a
  `security-pages-checklist` marker. The edit is a website change outside
  anything sync can write, so it never gates the close-out; instead sync's
  closed-tracker pass (Step 1g) proposes a one-line reminder comment,
  behind its own `security-pages-reminder` marker and at most once per
  tracker, when the advisory has shipped and the box is still unticked.
  A re-rendered hand-off comment keeps the release manager's tick, and a
  ticked box keeps later runs quiet. The reminder links the project's
  pages through the optional `security_pages_url` manifest key (#1355).
- **With `advisory_records` configured, sync proposes the security-pages edit.**
  The optional `advisory_records` manifest block names the site repository
  (Git or Subversion), its working copy and a layout: one CVE 5.x JSON file
  per CVE, or an entry in a per-release-line page whose path, section name
  and entry come from adopter templates. In the Step 1g closed-tracker pass,
  once cve.org reports the CVE `PUBLISHED`, the deterministic
  `advisory-records` planner (in `generate-cve-json`) computes the change and
  the `magpie-vcs` commands; sync proposes them as one item and runs them only
  on confirmation, then posts an `advisory-records` marker comment with the
  ticked checklist item. The planner refuses before publication, is
  idempotent, escapes tracker text, and refuses a page it cannot parse. The
  reminder never fires for such a project. `magpie-vcs` gains `update` and
  `checkout` for it.

## Out of scope

- Agentic Drafting beyond the security case (see [Drafting](drafting-mode.md)).
- Sending mail — replies are drafted to the maintainer's outbox.

## Acceptance criteria

1. Each lifecycle skill is confirm-before-apply and audit-logs applied
   changes.
2. No public surface produced by the flow contains tracker contents or
   pre-disclosure security framing.
3. CVE JSON is regenerated to stay in lock-step with the tracker body.
4. Security drafts resolve CC from `security_list`, or warn and record
   `cc_fallback` from `security_inbox.foundation_security_address` through
   project/organization/default precedence. Missing both blocks drafting.
   This resolution never redirects list reads or changes `<security-list>`.
   Draft recipes fail before backend invocation if the resolved CC has not
   been materialized or is blank; valid addresses reach the backend unchanged.
5. A `sync CVE-…` selector picks only trackers whose *CVE tool link*
   field carries that ID, and the bulk pre-flight never prints a private
   comment body (#1554, #1558).
6. An imported report renders as one inert block, and every body-field
   reader in the tree finds exactly the template fields once each in the
   result, whatever fences or fake `###` lines the report holds (#1672).

## Validation

```bash
uv run --project tools/skill-and-tool-validator --group dev skill-and-tool-validate
uv run --project tools/cve-tool-vulnogram/generate-cve-json --group dev pytest
uv run --project tools/gmail/oauth-draft pytest
```

## Known gaps

- The flow is `stable`; gaps surface as drift between a skill's documented
  steps and the adapters it calls — the loop's plan pass catches those.
- The generic rollup recipe in `tools/github/status-rollup.md` still
  spells only the `uv run --directory … github-rollup` CLI and does not
  mention `vetted-op-tracker`, although the security skills themselves
  switched to it in #1451.
  An adopter following that recipe under the secure setup hits the
  sandboxed-`gh` failure the entry point exists to avoid.
