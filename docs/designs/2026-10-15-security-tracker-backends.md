<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Security tracker backends: GitHub, local files, private Jira](#security-tracker-backends-github-local-files-private-jira)
  - [What is wrong](#what-is-wrong)
  - [Decisions](#decisions)
  - [The contract](#the-contract)
  - [Local file tracker](#local-file-tracker)
  - [Private Jira](#private-jira)
  - [Setup](#setup)
  - [Alternatives considered](#alternatives-considered)
  - [Rollout](#rollout)
  - [Risks](#risks)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Security tracker backends: GitHub, local files, private Jira

**Status:** Built in one change (contract, both backends, skill wiring, setup step); evals and a first adopter run outstanding — see [Rollout](#rollout).

## What is wrong

Every `security-*` skill assumes the tracker is a private GitHub repository.
`gh issue …`, `gh search issues`, `vetted-op-tracker rollup-append` and the GitHub body-field helpers are written straight into the skill bodies.
That excludes three kinds of team:

- **Teams that already keep reports as files.**
  Many ASF projects hold security reports in a private SVN area or a private repository: one Markdown or text file per report, sometimes a folder per report, sometimes `open/` and `closed/` sub-folders.
  They will not move years of history into GitHub issues to try a skill.
- **Teams on Jira.**
  Jira supports issue-security levels, and some projects already triage there.
- **Teams that want no hosted tracker at all.**
  A folder of files can be read, grepped, diffed and reviewed with tools everyone has, and its access control is the repository's.

`contract:tracker` exists as a label, but there is no contract document behind it, and nothing in it covers what the security workflow depends on:
named body fields, the single status rollup, attachments for the CVE record, and a guard against writing embargoed text somewhere public.

## Decisions

1. **A new contract, `contract:security-tracker`**, in [`tools/security-tracker/`](../../tools/security-tracker/contract.md).
   It lists the operations the security skills perform on `<tracker>`, each with its GitHub equivalent,
   so the existing GitHub recipes stay exactly as they are and the other backends are a lookup away.
   It is separate from `contract:tracker` because it promises more: a confidentiality guard and a publish step,
   which a general issue tracker for public bugs does not need.
2. **`tracker.platform` selects the backend**: `github` (default), `local-files`, or `jira`.
   It resolves through the usual chain, and the framework baseline sets `github`, so no existing adopter changes behaviour.
3. **The two new backends share one CLI surface.**
   `magpie-local-tracker` and `magpie-jira-tracker` take the same subcommands and print the same JSON.
4. **Vetted operations are the seam.**
   Skills never call a backend CLI.
   Every tracker `gh` command in a skill maps to a [vetted operation](../../tools/security-tracker/contract.md#from-skill-commands-to-vetted-operations),
   and vetted-ops translates that operation for the backend its policy names (`[tracker] platform`).
   The translation is reviewed code: the policy supplies the backend's tool directory and pinned target, never a command,
   so the closed-shape guarantees — fixed program, unaddressable target, parameters as argv elements, bodies on stdin,
   reads unreachable from the write entry point — hold on all three backends.
   Six operations were added so every tracker shape the skills use has a vetted form:
   `issue-create`, `issue-reopen`, `issue-list-label`, `issue-search` (plain words, no `:` qualifiers),
   `tracker-pending` and `tracker-publish`.
   Tracker operations with no counterpart (boards, milestone administration, the roster, `rollup-fold`) refuse by name,
   and a test derives the tracker operations from the catalogue so a new one cannot go unmapped.
5. **Skills switch through one shared block**, `tools/dev/blocks/tracker-backend.md`,
   propagated into every tracker-touching security skill by `check-shared-blocks.py`.
   One paragraph per skill, not a rewrite of twelve skill bodies: each `gh` recipe remains the reference for *what* to do,
   and on another backend the block sends the skill to the vetted operation in the mapping table.
6. **The local tracker adapts to the files it finds.**
   `detect` infers a format descriptor from the existing reports — layout, ID pattern, metadata style and keys, state values or state folders, heading level, where comments live — and returns the evidence for each decision.
   The descriptor is committed beside the reports as `.magpie-tracker.json`, so every teammate's agent writes the same shape.
   With no reports, a documented default applies.
7. **Git and SVN, scoped to the tracker folder.**
   `pending` lists what changed under the tracker root; `publish` commits only that, and pushes on Git.
   On SVN the commit is the publish.
   Closing a report in a folder-per-state tracker uses `git mv` / `svn mv`, so history follows it.
8. **Publishing is proposed, never automatic.**
   A skill that wrote to a local tracker ends its run by showing the changes and a drafted commit message, and commits and pushes only on the user's confirmation.
9. **Every backend refuses to write to a tracker it cannot show is restricted.**
   Jira: every write checks the issue's security level, and `create` always sets one.
   Local files: writes are refused until the descriptor records `access_restricted: true`, which only an explicit flag sets, and setup passes it only on the user's answer; `doctor` fails on a public GitHub remote.
   The guard returns exit `4`, and the shared block tells the skill to stop rather than route around it.

## The contract

See [`contract.md`](../../tools/security-tracker/contract.md).
Sixteen operations: the reads (`view`, `list`, `labels`, `field-get`), the writes (`create`, `edit`, `field-set`, `comment`, `close`, `reopen`, `rollup-append`, `rollup-amend-latest`, `attach`), and three for the backend itself (`pending`, `publish`, `doctor`).
Bodies and comments enter only through files or stdin, as the GitHub recipes already require;
a title may also arrive as one validated argv element from vetted-ops, which never uses a shell.
Exit codes are fixed across backends, so a skill handles *not found* and *refused* the same way everywhere.

## Local file tracker

[`tools/local-tracker/`](../../tools/local-tracker/README.md), stdlib Python.

Detection works from evidence, in order:

| Decision | Evidence |
|---|---|
| State as folder | Sub-folders named like states (`open`, `closed`, `fixed`, `archive`, …) |
| Layout | More report-named folders than report-named files, or the reverse |
| Report file in a folder | `<folder>.md` in most folders, else the most common file name |
| ID format | The most common prefix before the number, zero-padding, and whether a title slug follows |
| Metadata | `---` front matter or `**Key:** value` lines, by majority; key names matched to roles through synonyms (`Status` → state, `Tags` → labels, …) |
| State values | Values sorted into open and closed by vocabulary; the not-planned value picked from `rejected`, `invalid`, `wontfix`, … |
| Title | A title key, or the first `# ` heading |
| Field sections | The most common heading level |
| Comments | A comments file beside the report, or a `## Comments` / `## Notes` / `## Timeline` section |

Roles the security skills cannot work without (labels, milestone, assignees) are added in the team's own key casing when the reports never had them, and the output says so.
Anything else that does not fit is reported in `notes`, and setup shows it before writing.

Hand-written comments are read back from their headings, so a trail that mixes the team's old comments with new tool-written ones reads in order.
The rollup keeps the GitHub entry shape, so the skills' rollup rules and action labels carry over unchanged.

## Private Jira

`magpie-jira-tracker` in [`tools/jira/`](../../tools/jira/README.md#security-tracker-magpie-jira-tracker) (`jira_bridge.security_tracker`), stdlib Python over REST v2 (Server, Data Center and Cloud).
Body fields are `h3.` wiki-markup sections in the description; the rollup is one comment carrying an invisible anchor marker.
It lives in the same package as `jira_bridge.rest`, the read client the contributor-growth skills already use, and every request goes through it:
the token stays bound to a host the user confirmed, is sent only to that host, follows no redirect,
and `send()` refuses any write when the token was withheld, so a security-tracker write can never go out anonymously or to a re-pointed URL.
It is Python rather than more subcommands on the Groovy bridge because the security-level guard has to run before every write and must be testable without a Groovy toolchain;
the Groovy bridge stays the general `contract:tracker` write path for the `issue-*` skills.

## Setup

`/magpie-setup config` gains [Step 3a](../../plugins/magpie-setup/skills/setup/config.md#step-3a--security-tracker-backend):
one question in the existing batch picks the backend.
For local files it finds the folder, runs `detect`, shows the decisions and notes, asks who can read the repository, and writes the descriptor only after that answer.
The descriptor is the one file this step writes outside the personal layer. It is left uncommitted, and the first publish proposal includes it.
For both non-GitHub backends the step also shows the vetted-ops `[tracker]` table and the six new caller grants, and writes them only on confirmation.

## Alternatives considered

- **Extend `contract:tracker` instead of adding a contract.**
  Rejected: the guard and the publish step would then bind every general issue-tracker adapter, and the forge bridges (GitLab, Forgejo, SourceHut) would all become "partial" against requirements that only the security workflow has.
- **A separate Jira tool for the security tracker.**
  The first cut shipped `tools/jira-security-tracker/` with its own HTTP client.
  Rejected once `jira_bridge.rest` landed upstream: two clients meant two credential rules,
  and only the shared one binds the token to a confirmed host and refuses redirects.
  Merging put the security tracker behind those rules and left one Jira tool.
- **A GitHub backend inside the shared CLI.**
  Rejected: it would duplicate `vetted-ops`, which exists precisely so `gh` can run outside the sandbox under a vetted command surface.
- **Skills call the backend CLIs directly.**
  The first cut did this, with a contract table keyed by the GitHub equivalent.
  Rejected: it gave the new backends a second, unvetted command surface beside vetted-ops,
  so an injected instruction could reach a free-form `magpie-local-tracker` argv that no policy bounds.
  Routing through vetted operations keeps one surface, one policy and one set of entry points for all three backends.
- **Rewrite every skill body backend-neutrally.**
  Rejected: twelve large skills, each with an eval suite, for no behaviour change on the default backend.
  The shared block plus the contract's skill-command table delivers the switch with one paragraph per skill.
  A later pass can move individual recipes onto the contract as skills are optimised.
- **Store the local format in `project.md`.**
  Rejected: the format belongs to the folder, not to one contributor's configuration.
  A personal-layer copy would let two teammates write two shapes into the same tracker.
- **Commit after every operation.**
  Rejected: a sync pass makes many small writes, and one reviewed commit per session is what a human would make.
  It also keeps the push — the one step that needs the user's credentials — to a single confirmation.

## Rollout

1. Land the contract, both backends, the shared block and setup Step 3a (this change).
2. Run the security skills' eval suites; the block changes each skill's prompt material.
3. Pilot `local-files` with one project that keeps reports in SVN, and `jira` with one project that triages in Jira; fold what they hit back into detection and the contract.
4. Move the heaviest skills' recipes onto the contract directly when they are next optimised, so the GitHub column becomes one backend among three rather than the reference.

## Risks

- **ID collisions.** Two teammates who create reports offline both get the next number.
  The second push or commit fails, and the fix is a rename and a republish; the README says so.
  A reservation scheme was judged not worth its complexity before a pilot shows it matters.
- **Detection guesses wrong.** Mitigated by showing every decision and note before writing, and by the descriptor being a plain JSON file a human can correct.
- **The installed vetted-ops copy lags the repository.** It installs as a copy under `~/.claude/magpie/vetted-ops`;
  until `setup-isolated-setup-update` refreshes it, the new operations and the `[tracker]` table are unknown there and refuse.
- **The access check is a human statement.** The tool cannot prove an SVN path or a non-GitHub remote is private.
  The flag records who said so and when, and setup asks in a way that makes the question impossible to skip.
