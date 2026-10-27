<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [`security-management`](#security-management)
  - [Prerequisites](#prerequisites)
  - [How to use](#how-to-use)
  - [Shared rules](#shared-rules)
  - [Commands](#commands)
    - [`issue-import`](#issue-import)
    - [`issue-import-from-pr`](#issue-import-from-pr)
    - [`issue-import-from-md`](#issue-import-from-md)
    - [`issue-import-via-forwarder`](#issue-import-via-forwarder)
    - [`issue-import-from-scan`](#issue-import-from-scan)
    - [`issue-triage`](#issue-triage)
    - [`issue-invalidate`](#issue-invalidate)
    - [`cve-allocate`](#cve-allocate)
    - [`issue-deduplicate`](#issue-deduplicate)
    - [`issue-sync`](#issue-sync)
    - [`issue-fix`](#issue-fix)
  - [Tests](#tests)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# `security-management`

**Capability:** substrate:analytics

**Harness:** agnostic

The deterministic core of the `security-*` skills.
Each skill family is a subcommand: [`security-issue-import`](https://github.com/apache/magpie/blob/main/plugins/magpie-security/skills/issue-import/SKILL.md) (`issue-import`),
[`security-issue-import-from-pr`](https://github.com/apache/magpie/blob/main/plugins/magpie-security/skills/issue-import-from-pr/SKILL.md) (`issue-import-from-pr`)
[`security-issue-import-from-md`](https://github.com/apache/magpie/blob/main/plugins/magpie-security/skills/issue-import-from-md/SKILL.md) (`issue-import-from-md`)
[`security-issue-import-via-forwarder`](https://github.com/apache/magpie/blob/main/plugins/magpie-security/skills/issue-import-via-forwarder/SKILL.md) (`issue-import-via-forwarder`)
[`security-issue-import-from-scan`](https://github.com/apache/magpie/blob/main/plugins/magpie-security/skills/issue-import-from-scan/SKILL.md) (`issue-import-from-scan`)
[`security-issue-triage`](https://github.com/apache/magpie/blob/main/plugins/magpie-security/skills/issue-triage/SKILL.md) (`issue-triage`),
[`security-issue-invalidate`](https://github.com/apache/magpie/blob/main/plugins/magpie-security/skills/issue-invalidate/SKILL.md) (`issue-invalidate`),
[`security-cve-allocate`](https://github.com/apache/magpie/blob/main/plugins/magpie-security/skills/cve-allocate/SKILL.md) (`cve-allocate`),
[`security-issue-deduplicate`](https://github.com/apache/magpie/blob/main/plugins/magpie-security/skills/issue-deduplicate/SKILL.md) (`issue-deduplicate`),
[`security-issue-sync`](https://github.com/apache/magpie/blob/main/plugins/magpie-security/skills/issue-sync/SKILL.md) (`issue-sync`)
and [`security-issue-fix`](https://github.com/apache/magpie/blob/main/plugins/magpie-security/skills/issue-fix/SKILL.md) (`issue-fix`).
The tool takes what the agent saved — search results, the redacted report text, the confirmed plan — and decides or renders everything rule-shaped:
the Step 1 pre-filter, the batched `threadId` dedup, the forwarder pre-screen, the tracker body and its inert report block, the rollup entry, the rejections-ledger record,
the fix-already-public reply, the receipt-draft matrix, the confirmation-reply grammar and the recap.
The agent keeps the judgement: classification, field extraction, third-party PII identification, fuzzy duplicates, prior rejections, canned-response choice and injection flagging.

**It runs nothing.**
No command invokes `gh`, a mail backend, `pii-redact` or `pii-reveal`, posts, drafts or touches the network.
Report text arrives already redacted, and redaction tokens (`N-…`, `E-…`) pass through unchanged.
A render that would emit something the skill must refuse (a malformed report body, a rollup label holding `<`, `>` or `·`, a ledger record missing a key)
exits `2` with `{"ok": false, "refused": "<why>"}`.

## Prerequisites

- **Runtime:** Python 3.11+, stdlib only; run with `uv run --project <framework>/tools/security-management`.
  It imports three stdlib-only workspace members instead of copying their rules:
  [`github-body-field`](../github-body-field/README.md) (what a `### Field` section is) and
  [`generate-cve-json`](../cve-tool-vulnogram/generate-cve-json/README.md) (the bot/AI credit policy) and
  [`magpie-vcs`](../vcs/README.md) (the embargo scrub of public text).
- **CLIs:** None.
- **Credentials / auth:** None.
- **Network:** None.

## How to use

Untrusted text reaches the tool only through a file the agent wrote with its Write tool, never through argv:

```bash
uv run --project <framework>/tools/security-management security-management issue-import render-body \
  --input <scratch>/body-<threadId>.json
```

Every command prints one JSON object; rendered text is in its `text` field.

## Shared rules

`security_management.shared` holds what every import skill applies; it has no CLI of its own.

| Module | Rule |
|---|---|
| `body` | `inert_block`: the report text, line breaks normalised (other `splitlines` breaks refused), byte-exact inside a fence (except a line that would end a field under the body-field contract — `###` then a space, a tab or nothing, at column 0 or behind `>`, list markers or indent, whatever the name — or that starts with `<!--`, which gains a leading `\\` and is listed in `escaped_lines`) with info string `text` one backtick longer than its longest backtick run (at least three), so nothing in it renders and no line of it can close the block. `short_field`: a short field with headings demoted, every HTML opener escaped, images and active HTML defused, fence lines escaped. `verify`: the rendered body through github-body-field's `normalise` — exactly the template fields once each, nothing to decide, nothing to rewrite. `render`: one `### <heading>` per field role, headings from `tracker.body_fields`, empty fields `_No response_`, `Severity` `Unknown`, the injection callout only when the model sets it. |
| `rollup` | Entry bodies at column 0, one-line values, the action label refused when it holds `<`, `>` or `·`, and handed back shell-quoted. |
| `refs` | `bare_refs` / `linkify` for `#NNN` and `owner/repo#NNN` outside code spans (any backtick run), fences, links, autolinks and URLs, ported from `pr-management`'s `_BARE_REF`; `tracker_link` for a GitHub, Jira or local-files reference. |
| `titles` | `strip_mail_prefixes`, `strip_pr_title`, `md_title`. |
| `recipients` | `security_cc`: the security CC of every draft, each key from the first layer that declares it. |
| `drafting` | `choose`: Gmail or Maildir (the person over the project), then `backend`: `maildir` when configured, else `oauth_curl`, and `claude_ai_mcp` only without OAuth credentials and with no link in the body; `anchor`: what each backend attaches the draft by; `scan`: tracker references, the CVE-tool URL, bare references, re-opening phrases, CVSS and other ASF projects in a composed reporter draft. |
| `grammar` | `parse_reply`: the confirmation grammar; anything unplaceable goes to `ambiguous_tokens` for the agent to ask back, conflicting dispositions hold their candidate out of every list, unscoped free text holds everything, and a negation confirms nothing. |
| `keyword` | The `tr -cd` allowlist for search keywords, read from a file, never starting with `-`. |
| `fields` | `read`: template fields of an existing tracker body through github-body-field (`normalise`, then `extract_field`); a field it will not decide on is `undecided`, never guessed or read as empty. |
| `threads` | `classify`: the *Security mailing list thread* field as an import path (archive URL, Gmail-only, PR or markdown sentinel, indeterminate), the primary thread by the `tools/gmail/threading.md` relay signals, and the root `Message-ID`. |
| `dispositions` | The six triage classes, the two proposal markers (`**Triage proposal**`, `**Proposed disposition: `) and `parse_time`. |
| `numbered` | `parse`: the numbered-proposal reply of `cve-allocate` and `issue-deduplicate` — `all`, a list (with a comment after a dash only when it names other items to hold them back), `cancel`; anything else is an edit, and nothing applies by default. |
| `rollup.notification_line` | The *Reporter notification* line (`notified`, `team_member`, `draft_pending` only once the draft is checked to be in Drafts, `omitted`). |
| `selectors` | `issue_numbers`: `N`, `#N, #M`, `#N-#M`, `owner/repo#N`, an issue URL, refusing another repository; the CVE token rule. |
| `shell` | `dq` / `w`, a copy of `release-management`'s. |

## Commands

### `issue-import`

| Command | Prints |
|---|---|
| `governance --config <security-intake-config.md>` | `reporter_acknowledgement_model`, `window_days`, `config_file_found`; `manual` / `90` when the file or the `disclosure_governance` block is absent, a `warnings` entry for a value outside the vocabulary. |
| `prefilter --threads F` | Per thread: `decision` (`keep` / `drop`), `rule` (1 GHSA relay, 2 CVE-tool bookkeeping, 3 anything else), `class`, `pretag`; `dropped` and `counts`. Every message must match rule 2 to drop; a missing subject or sender keeps; `named_thread_id` is never dropped. |
| `dedup-queries --thread-ids F [--tracker T]` | `batches` of at most six ids, each a quoted phrase OR'd into `query`, and the shell-quoted `command`; ids are Gmail / PonyMail ids, maildir names or root `Message-ID`s, and any other id exits `2` with `rejected_ids`. |
| `dedup-attribute --thread-ids F --hits F` | `tracked` (id → hits), `untracked`; at 100 hits `truncated`, no `untracked`, and `rerun` batches; exit `2` with `rejected_ids` as above. |
| `relay-prescreen --message F --forwarders F` | `invoke_subskill`: true only when one enabled adapter's `sender_pattern` AND `preamble_match` (first 400 characters) both match, or an adapter's pattern is unresolved or invalid; `partial` lists adapters where only one signal matched (not a relay, shown to the user). |
| `keyword --file F [--kind keywords\|email-local]` | `cleaned`, `empty`. |
| `title --input F` | `title`: the subject without its mail prefixes. |
| `linkify --input F` | `text` with every bare reference linked into `repo`, and the `bare_refs` found. |
| `render-body --input F` | The body `text`, `sanitised_fields`, `fields` as github-body-field parses them, `fields_ok`, `extra_fields`, `reporter_credit_is_bot`, `bare_refs`; exit `2` with `malformed_indicator` for a stray line break, or when `verify` refuses the rendered body. |
| `render-rollup --input F` | `label`, `label_shell`, `text`: the import entry, with the receipt line for a draft, a bundle, a converged disposition or a suppression, and the malformed-body note. |
| `render-ledger --input F` | The `<!-- rejection v1 -->` record; values on one line, `archive` `unresolved (archive lag)` when not given. |
| `render-fix-public-reply --input F` | The thank-without-credit reply, `merged on` / `opened on` per PR, one PR or a list. |
| `ack-decision --input F` | `draft_created`, `draft_auto_ack_tagged`, `suppressed_reason`, `rollup_note`, `rollup_receipt`, `proposal_note`, `route`, `window_days` — the Step 7 item 4 matrix. |
| `render-recap --state F` | `issues_created` (`{number, url}` on GitHub, `{id, url}` on Jira and local-files, per `platform`), `drafts_waiting` (a shared draft once), `skipped` (full `owner/repo#NNN`), `cve_tool_bookkeeping_dropped` (pre-filtered included), `text`. |
| `parse-reply --input F` | `action`, `import_items`, `skip_items`, `reject_with_canned`, `reject_with_public_fix`, `edits`, `overrides`, `keep`, `non_import_confirmed`, `ambiguous_tokens`, `ambiguous_items`. |

### `issue-import-from-pr`

| Command | Prints |
|---|---|
| `parse-ref --ref R --upstream U` | `number` from `N`, `owner/repo#N` or the PR URL (trailing path ignored); exit `2` for another repository or free text. |
| `scope --files F --scope-config F` | `scope` (or `mixed_scope_blocker`), `stop`, `detection` (`matched`, `mixed`, `unresolved`, `disabled`), `overlapping`, `mixed_scopes`, `sub_packages` (also as `affected_providers`), `packages`, `files_counted`, `test_files_stripped` (any `tests/` segment), `unmatched`, `matched`. |
| `milestone-check --input F` | `exists` (exact match only), `near_matches`, `blocker`. |
| `title --input F` | `title` without conventional-commit prefix, skip-ci markers and trailing `(#N)`; `too_short` under 25 characters. |
| `render-body --input F` | The body `text`: imported-from note over the PR body as an inert block (its references stay unlinked text), the mailing-thread sentinel, *PR with the fix*, *Remediation developer* (`_No response_` for a bot, `remediation_developer_is_bot`); `sanitised_fields`, `fields_ok`, `bare_refs`; exit `2` with `malformed_indicator` for a PR body that does not pair. |
| `labels --input F` | `labels`: scope, `pr_open` / `pr_merged`, `security_marker` from `tracker.labels`; never `needs_triage`; `warnings` for a closed PR. |
| `render-rollup --input F` | `label`, `label_shell`, `text`: the first rollup entry, column 0. |
| `dup-query --pr N --tracker T [--hits F]` | The search `query` and `command`; with `--hits`, `hits` with links, `duplicate`, `truncated` at 30 and its `warning`. |
| `render-recap --input F` | The recap `text` and hand-off, `bare_refs`. |

### `issue-import-from-md`

| Command | Prints |
|---|---|
| `parse <file> --upstream U` | `findings[]` (`index`, `title`, `tracker_title`, `severity`, `category`, `repository`, `branch`, `date_created`, the section payloads, `has_*`, `warnings`), `warnings`, `total_findings`; exit `2` with `not-a-findings-file` without a `# ` heading, a `**Severity:**` line or a pair. |
| `keyword --file F [--tracker T]` | `cleaned`, `empty` and the single-quoted `search_command`. |
| `render-body --input F` | The body `text`: each section an inert block (exit `2` on a stray line break or a body `verify` refuses), the field mapping, the Recommended-fix `<details>`; `sanitised_fields`, `fields_ok`, `reporter_credit_is_bot`, `bare_refs`. |
| `render-rollup --input F --k K --n N` | `label`, `label_shell`, `text`. |
| `render-proposal --input F` | The proposal table, default disposition and reply forms, duplicates linked. |
| `render-recap --input F` | The recap `text` and hand-off. |

### `issue-import-via-forwarder`

| Command | Prints |
|---|---|
| `preflight --forwarders F --message F --framework D` | `outcome` (`proceed`, `no-forwarder-config`, `abort` with exit `2`), `preflight_passed`, `error`, `note`; installed means a `tools/forwarder-relay/<name>/` directory or a `shipping` README row whose doc exists. |
| `detect --message F --forwarders F [--collaborators F]` | The first enabled adapter whose sender pattern AND preamble regex (first 400 characters) both match: `match`, `sub_skill_applied`, `preamble_snippet`, `sender_matched`, `collaborator_warning`, `adapters`, `partial_matches` (adapters where only one signal matched — not a relay); exit `2` on an unresolved pattern. |
| `credit-kind --input F` | `kind` (`tool` under the bot/AI policy, else the adapter's `kind_hints`, else `human`), `is_bot`, `credit_unknown`. |
| `first-name --input F` | `first_name` of a handle or display name; `null` (generic salutation) for an address. |
| `route --mode M [--milestone K] --adapter F` | `to_recipients` (first handle) and `fallback_recipients`, `addressing_block_emitted`, `question_mode`, `negative_space_suppressed` (a do-not-relay milestone in sync mode). |

### `issue-import-from-scan`

| Command | Prints |
|---|---|
| `bucket-action --bucket B` | `creates_tracker` (true only for `import-as-tracker`: Golden rule 3), `action` (`tracker`, `pr-or-skip`, `none`), `route`. |
| `render-report --findings F --buckets F [--title T]` | The report `text` (distribution line, a section per bucket, a row per finding; for several scans the outcome table, percentages and severity vs disposition), `distribution`, `trackers_possible`; a by-design, duplicate or already-fixed row without grounding is refused. |
| `parse-decision --input F` | `action` (`apply`, `skip`, `cancel`, `ambiguous`), `confirmed` (each with its bucket's `creates_tracker` and `action`), `skipped`, `ambiguous_tokens`; an ambiguous reply holds everything. |
| `scrub --text F --tracker T [--allowed-cves F]` | `clean` and `hits` (`private-tracker-ref`, `cve-id`, `embargo-term`, `bare-ref`, with line); the text is never rewritten. |

### `issue-triage`

Every command takes `--input F`, a JSON file.

| Command | Prints |
|---|---|
| `selector` | `action` (`list_query`, `verbatim`, `cve_search`; `error` exits `2`), `issue_numbers`, `scope_label`, `cve_token`, `retriage`, `no_preflight`, `explicit`, and the plain `gh` `command` (`--limit 1000`; `--retriage` drops the `needs triage` filter). |
| `queue` | `stop` (`empty`, `limit` at 1000, `ask` for a CVE on several trackers, `confirm` for `--retriage` over 50 unless `confirmed`), `echo`, `numbers`, and `batches` of at most 20 aliased issues (`query`, `file`, `command` as `-F query=@file`). |
| `preflight` | The four-rule skip over `trackers` or raw `responses`: `kept`, `skipped` (date, class, rule), `mail_checks` (rule 4 still to read), `explicit_notes`, `missing_numbers`, `all_skipped`, `disabled`. |
| `precedent-signal` | `disposition_signal` from the rated precedents, `budget_exhausted`, `trust_boundary_load_bearing`, the *Direct precedent* `citations`. |
| `mentions` | `handles` (PR author, reviewer, topic owners, scope default only as fallback; cap 3; roster only; never the viewer), `dropped`, `routing_fallback`, `fallback_note`. |
| `render-proposal` | The comment `text` (markers, class line, severity, fix shape, class additions incl. the FIX-ALREADY-PUBLIC reply draft, action items, mention line, names scrubbed, references linked), `file`, `command`, `unlinked_cves`; refuses an unknown class, a CVSS severity, more than 3 handles or one off the roster, an INFO-ONLY heading not in the list, a PROBABLE-DUP without kept tracker. |
| `scrub` | `text` with bare display names as `@`-handles (outside code and URLs) and references linked, `replacements_made`, `linked_refs`. |
| `parse-reply` | `action` (`post`, `cancel`, `ambiguous`), `post_items`, `post_now`, `skip_items`, `edits`, `reclassifications`, `redraft_items`, `force_triage`, `ambiguous_tokens`, `ambiguous_items`; nothing posts by default. |
| `render-recap` | `distribution` (six keys), `trackers`, `next_steps` by class, `next_step_notes`, `skipped`, `sync_note`, `text`, `bare_refs`. |

### `issue-invalidate`

Every command takes `--input F`, a JSON file.

| Command | Prints |
|---|---|
| `selector` | `mode` (`single`, `bulk`, `proposed`), `numbers`, the `gh issue view` / `invalidate proposed` list `command`, and for bulk the aliased `batches` with thumbs-up reactions; another repository exits `2`. |
| `consensus` | `agreed` (a roster member's INVALID proposal with a thumbs-up or acknowledgement from another roster member), `awaiting` with the recap note, `stop` at the 1000 cap. |
| `hard-stops` | `verdict` (`proceed`, `noop`, `stop`, `escalate`, `probe`, `ask`), `cve_id`, `message` from state, labels, the *CVE tool link* field and the generic CVE state. |
| `import-path` | `import_path`, `email_draft_step`, `thread_id` (field, else the rollup provenance), `thread_source`, `secondary_threads`, `root_message_id`, `reporter_credit`; an ambiguous field exits `2`. |
| `labels` | `labels_to_add` (`invalid`), `labels_to_remove` (needs triage, scope, `pr created` / `pr merged` when set), `security_issue_stays`, the `gh issue edit` `command`. |
| `board` | The introspection query `file` and `command`; given `items`, the `archiveProjectV2Item` mutation or the *not on the board* note. |
| `draft-plan` | `action` (`skip`, `ask`, `surface_existing`, `blocked`, `create`), `notification_case`, and for a draft `to`, `cc`, `subject` (`Re: <root subject>`), `backend`, `anchor`; links without OAuth credentials exit `2`. |
| `check-draft` | `clean` and `hits`: tracker reference, CVE-tool URL, bare reference, re-opening phrase, CVSS, other ASF projects, a duplicate's missing canonical CVE. |
| `render-close` | The brief closing comment `text`. |
| `render-rollup` | `label`, `label_shell`, `text` (at most 5 quotes, the canned link, exactly one Reporter-notification line), `quotes_dropped`, `needs_amend`, `bare_refs`; no notification case exits `2`. |
| `parse-reply` | `action` (`apply`, `apply_silent`, `replace_email_body`, `repick_canned`, `cancel`, `ambiguous`), `email_body_override`, `canned_section_override`. |
| `apply-plan` | The 6a-6g `steps` in order, with file paths and commands, and the label plan. |
| `render-recap` | The recap `text` with the hand-off line, `bare_refs`. |

### `cve-allocate`

Every command takes `--input F`, a JSON file.

| Command | Prints |
|---|---|
| `selector` | `issue`, `cve_override`, `resume_step` (`4` with an override) and the Step 1 `commands`; a malformed CVE token, two CVE IDs, two trackers or another repository exits `2`. |
| `blockers` | `verdict` (`proceed`, `blocked`), `blockers`, `warnings` (`needs triage`, only when no hard blocker fired), `existing_cve`, `already_wired`, `scope_label`; empty `scope_labels` exits `2`. |
| `preflight` | `path` (`api`, `recipe`, or `null` with the next check `command`), `reason`, `offer_setup`, `setup_command`. |
| `title` | `original_title`, `normalized_title`, `word_count`, `changed`, `over_strip_warning` (fewer than 3 words). |
| `recipe` | `path` (`api`, `recipe`, `relay`), `text`, the `vulnogram-api-allocate` `command` with the title shell-quoted, `bare_refs`; an unanswered authorisation question exits `2`. |
| `allocate-result` | `next` (`step-4`, `stop`, `setup`, `check-records`, `recipe`), `cve_id`, `message`, `rerun_allocate` (true only after an expired token). |
| `cve` | `cve_id` and `record_url` from the user's paste-back; none, a malformed token or two IDs exit `2`. |
| `draft-plan` | `action` (`skip`, `ask`, `surface_existing`, `blocked`, `create`), `notification` (`omitted`, `team_member`, `notified`, `draft_pending`) and for a draft `to`, `cc`, `subject`, `backend`, `anchor`, `secondary_threads`. |
| `check-draft` | `clean` and `hits`: a missing CVE ID, the CVE-tool URL, a tracker reference, a bare reference, CVSS, other ASF projects. |
| `proposal` | The numbered `items` (5 only when a draft is created), `proposal_items_count`, the `cve_tool_link_value`, `notes`, `text`. |
| `render-rollup` | `label` (`CVE allocated (<CVE-ID>)`), `label_shell`, `text`, `needs_amend`, `bare_refs`; a draft id not checked against Drafts exits `2`. |
| `parse-reply` | `action` (`apply`, `cancel`, `edit`, `ambiguous`), `items_applied`, `items_skipped`. |
| `apply-plan` | The confirmed items' `steps` in order, with file paths and commands, per backend. |
| `render-recap` | The recap `text`, `bare_refs`. |

### `issue-deduplicate`

Every command takes `--input F`, a JSON file.

| Command | Prints |
|---|---|
| `selector` | `keep`, `drop` (kept first) and the two Step 1 reads; one tracker, three, a range or another repository exits `2`. |
| `classify` | `verdict` (`proceed`, `blocked`, `probe`), `blockers` (`scope_unclear`, `scope_mismatch`, `closed_tracker`, `already_duplicate`, `cve_on_drop`, `cve_public`, `drop_further_along`), `keep_cve`, `retract`. |
| `fields` | Both sides' template fields (the CVE JSON attachment cut off), `has_cve_json_attachment`, labels, milestone, `cwe_conflict`, `severity_propagation_risk`; an undecided field exits `2`. |
| `merge-body` | The kept body rewritten field by field (`replace_field`), `changed_fields`, `blockers` (a CWE conflict), `scores_removed`, `severity_note`, `tool_credits`, `skipped_credits`; a missing headline, analysis or needed merged value exits `2`. |
| `render-rollup-kept`, `render-rollup-dropped` | `label`, `label_shell`, `text`, `needs_amend`, `bare_refs`. |
| `proposal` | The numbered `items` (7 only with two CVEs), `blocked`, `text`. |
| `parse-reply` | `action` (`apply`, `cancel`, `edit`, `ambiguous`), `items_applied`, `items_skipped`, `note`. |
| `apply-plan` | The confirmed items' `steps` in order, per backend; an open blocker or the same tracker twice exits `2`. |
| `render-recap` | The recap `text`, `blockers`, `bare_refs`. |

### `issue-sync`

Every command takes `--input F`, a JSON file.

| Command | Prints |
|---|---|
| `selector` | `queries` (each with `id`, `kind`, `command`, `limit`), explicit `numbers`, `searched_cve_ids`, `no_preflight`; a malformed `CVE-…` token sets `error: invalid_cve_token` and searches nothing. |
| `resolve` | `resolved` (ascending; `rejections-ledger` dropped, closed `announced` cut to 90 days, a CVE kept only where its *CVE tool link* names it), `explicit`, `title_matches` to confirm, `warnings` for a capped list, the `echo`. |
| `preflight-query` | One aliased GraphQL read per 50 trackers: `file`, `query`, `command`. |
| `preflight` | Per tracker `decision` and `rule`, `dispatched`, `urgent`, `skipped`, the *Pre-flight skipped* text; explicit trackers and `--no-preflight` are never skipped. |
| `bucket` | `cve_affecting`, `non_cve_affecting`, `walk_order`, `review_ready_push` and its bucket. |
| `parse-bulk-reply` | `action` (`apply`, `force_sync`, `cancel`, `none`, `ambiguous`), `apply` per tracker, `edits`, `force_sync`, `skip`. |
| `parse-reply` | The single-tracker form through `shared.numbered`. |
| `check` | `clean` and `violations` (`surface`, `guardrail`, `evidence`) for reporter CVSS, other ASF projects, bare CVE IDs or the CVE-tool URL in an email, and bare `#NNN`. |
| `security-cc` | `security_cc`, `cc_fallback`, `warning` and `warning_text`, `draft_blocked`, `cc`, `search_list`, through the project / organization / framework layers. |
| `draft-backend` | `backend` (`maildir`, `oauth_curl`, `claude_ai_mcp`), `decided_by` (`user.md`, `project.md`, `default`); no credential with links in the body exits `2`. |
| `ghsa-route` | `access_tier`, `action`, `channel`, and for an admin hand-off the draft tool, addressee, thread, rollup marker and three parts. |
| `push-decision` | `action` (`skip`, `block`, `hand-off`, `push`, `pending` with the `next` command or gate), `gate_failed`, `handoff_variant`, `state_advance`, `recap_blocker`. |
| `disclosure` | `issue_age_days`, `overdue_for_disclosure`, `approaching_window_end`, `grace_period_expired`, `distributor_notify_pending`, `expected_disclosure_by`. |
| `staleness` | `stale` and `days`: the team's latest message older than the timeout with no reporter reply since. |
| `closed-announced` | `cve_org` (`notify`, `already_notified`, `wait`, `blocker`, `retry`, `skip`), `security_pages_reminder_pending`, `advisory_records` and its next step, `blockers`. |
| `release-vote` | `release_vote_in_progress` and `release_vote_thread_url` for an open `[VOTE]` matching the fix-PR milestone. |
| `advisory-archive` | `accepted` and `reasons` for a candidate *Public advisory URL*: the thread must be on `advisory_list`, its root subject `<CVE-ID>: <description>` (no `Re:` / `Fwd:`), its root sender (`thread.from`) in `authorized_senders`, the URL under `mail_archive_url`; a missing `mail_archive_url` or `authorized_senders` rejects; `requires_confirmation` is always true, since the sender is the archived `From:` header and is not verified. |
| `render-recap` | The recap `text`, `bare_refs`. |

### `issue-fix`

Every command takes `--input F`, a JSON file.

| Command | Prints |
|---|---|
| `flow` | `flow` (`pull-request`, `patch-then-commit`, `stop`), `follow_subversion_flow`, `open_pr`, from `magpie-vcs fix-flow`'s exit and JSON. |
| `scrub` | Per surface (`branch`, `title`, `body`, `commit_message`, `newsfragment`, `comment`) `valid`, `terms` and `hits`; `clean`, `forbidden_terms_found`; for a newsfragment `include_newsfragment` (false) and `security_framing_violation`. |
| `backport` | `backport_needed` and `backport_labels` for the milestone against the next main release, plus confirmed extra lines. |
| `parse-reply` | The plan confirmation (items 1–7) through `shared.numbered`. |
| `review-plan` | `run`, `skip_notice` (`silent`, `one-line`), the title and body file passed, and the `adversarial-review` command. |
| `svn-share` | The three private proposals, `attach_via`, `public_surface_used` (false), `next` (`stop-await-review`). |
| `svn-gate` | `action` (`ask`, `stop`, `run-propose-commit`, `revise`, `await-confirmation`), the prefixed commands; a `commit` / `new-branch` without `--scrub` exits `2`. |
| `render-recap` | The recap `text`, `bare_refs`. |

## Tests

```bash
uv run --directory tools/security-management pytest -q
```

The cases of the retired model-graded `security-issue-import` suites `step-0-preflight`, `step-6-confirm` and `step-7-apply`
are pytest cases named after each former case, in `tests/test_issue_import.py` and `tests/test_grammar.py`.
The cases of `security-issue-import-from-pr/step-2-scope-detection` are in `tests/test_issue_import_from_pr.py`,
those of `security-issue-import-from-md/step-1-parse-findings` (cases 1–3) and `step-2-duplicate-guard` (case 1) in `tests/test_issue_import_from_md.py`,
and those of `security-issue-import-via-forwarder/step-0-preflight`, `step-1-detect-adapter` (cases 1, 2, 3, 6) and `step-3-route-drafts` in `tests/test_issue_import_via_forwarder.py`.
`tests/test_issue_import_from_scan.py` pins the `security-issue-import-from-scan` bucket rule the `step-c-bucket` model eval grades.
`tests/test_issue_triage.py` holds the cases of the retired `security-issue-triage` suites `step-1-selector`, `step-5-confirm` and `step-7-recap`, and cases 1–2 of `step-6-body-scrub`;
it pins the `step-26-precedent-search` signal rule, which stays a model eval.
`tests/test_issue_invalidate.py` holds the cases of the retired `security-issue-invalidate` suites `step-2-import-path`, `step-5a-labels`, `step-5b-closing-comment`, `step-5d-email-draft`, `step-5e-rollup-entry`, `step-5f-confirm` and `step-7-recap`.
`tests/test_cve_allocate.py` holds the cases of the retired `security-cve-allocate` suites `step-1-blocker-checks`, `step-2-title-normalize`, `step-3-allocation-recipe`, `step-4-propose-updates`, `step-5-confirm` and `step-7-recap`.
`tests/test_issue_deduplicate.py` holds the cases of the retired `security-issue-deduplicate` suites `step-1-classify`, `step-2-extract-fields`, `step-3-merge-body`, `step-4-rollup-entries`, `step-5-confirm` and `step-6-recap`.
`tests/test_issue_sync_state.py` pins the `security-issue-sync` Step 1 observations;
`tests/test_issue_sync.py` and `tests/test_issue_sync_rules.py` hold the cases of its retired suites `step-bulk-selectors`, `step-bulk-orchestration`, `step-3-confirm`, `step-6-recap`, `step-guardrails`, `step-security-cc`, `step-draft-backend`, `step-ghsa-access-tier` and `step-5b-push-decision`.
`tests/test_issue_fix.py` holds the cases of the retired `security-issue-fix` suites `step-0-fix-flow`, `step-5a-branch-name`, `step-5c-title-check`, `step-5e-backport`, `step-5f-newsfragment`, `step-6-confirm` and `step-11-recap`, and pins the deterministic parts of steps 7, 8 and 9.
`tests/test_body.py` checks that the `tracker-body-template.md` files of the sibling import skills carry exactly the rendered headings.
