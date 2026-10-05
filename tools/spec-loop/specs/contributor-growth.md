<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

---
title: Contributor-growth family
status: experimental
kind: feature
mode: Triage
source: >
  MISSION.md § Rationale ("Project health depends on a growing contributor
  base"). triage-mode.md § Known gaps (contributor-growth skills span
  Agentic Triage and Agentic Mentoring but are not yet a named family).
  mentoring-mode.md § Known gaps. Implemented by contributor-nomination,
  contributor-activity-sweep, contributor-calibrate,
  contributor-candidate-screen, committer-onboarding,
  contributor-identity-map, contributor-sentiment, onboarding-concierge,
  contributor-to-committer (plugins/magpie-contributor-growth/), and
  good-first-issue-author, mentoring-welcome, good-first-issue-sweep
  (plugins/magpie-mentoring/). Deterministic counting in
  tools/contributor-metrics; chat evidence through tools/chat
  (contract:chat), tools/chat-slack, and tools/chat-discord.
acceptance:
  - Every family skill is read-only or propose-before-post; none
    transitions, promotes, or announces without explicit maintainer
    confirmation.
  - The contributor-to-committer path has at least one skill per stage:
    first contact, activity tracking, nomination brief, post-vote onboarding.
  - All family skills validate under skill-and-tool-validate with no
    errors.
---

# Contributor-growth family

## What it does

Groups the skills that span the contributor-to-committer (and
committer-to-PMC) path into a named family. Each skill covers one
stage a maintainer or nominator cares about:

1. **First contact** — welcoming a first-time contributor to lower
   onboarding latency.
2. **Activity tracking** — surfacing a contributor's sustained
   work in a form useful to the nomination thread.
3. **Nomination brief** — assembling the evidence prose a PMC uses
   to open a committer or PMC vote thread.
4. **Good first issue authoring** — keeping the on-ramp stocked with
   newcomer-ready issues so contributors can find self-contained tasks.
5. **Calibration and screening** — deriving the committer and PMC
   threshold floors from the project's own past nomination decisions,
   then screening every recent contributor against them so candidates
   are noticed rather than waiting to be named.
6. **Identity mapping** — linking a contributor's GitHub handle to
   their chat, mailing-list, and social-media identities, recording
   only what a maintainer confirms.
7. **Post-vote onboarding** — walking the nominator through the
   ICLA check, account provisioning, permissions, and welcome
   announcement once a vote passes.

Each skill is read-only on governance artefacts (GitHub collaborator
list, `author_association` field, ICLA records) and proposes every
state change for human sign-off.

## Where it lives

Skills ship in two plugins, each reachable through a `skills/<dir>`
symlink:
`plugins/magpie-contributor-growth/skills/<alias>/SKILL.md`
(`activity-sweep`, `calibrate`, `candidate-screen`,
`committer-onboarding`, `contributor-to-committer`, `identity-map`,
`nomination`, `onboarding-concierge`, `sentiment`) and
`plugins/magpie-mentoring/skills/<alias>/SKILL.md` (`welcome`,
`good-first-issue-author`, `good-first-issue-sweep`).
Family overview: `docs/contributor-growth/README.md`.
Design record:
`docs/designs/2026-09-27-contributor-growth-calibration-and-screening.md`.
Adopter config scaffolds live in `plugins/magpie-setup/templates/`
(`projects/_template` is a symlink to it): `committer-readiness.md`,
`contributor-nomination-config.md`, `committer-onboarding-config.md`,
`contributor-identities.md`, `contributor-sentiment-config.md`,
`onboarding-concierge-config.md`.

- Skill: `mentoring-welcome` — drafts a first-contact orientation
  comment for a first-time contributor on a newly opened issue or PR.
  Detects first-time authorship via the GitHub `author_association`
  field; skips repeat contributors; proposes the comment and does not
  post without maintainer confirmation. Ships `mode: Mentoring`
  + `experimental`, eval suite under
  `tools/skill-evals/evals/mentoring-welcome/`.
- Skill: `contributor-activity-sweep` — read-only GitHub activity
  card for a named contributor: PR authorship, code-review
  participation, issues, and comments over a configurable window,
  counted by `tools/contributor-metrics` (raw counts only, its own
  substantive-review thresholds, timeline without issues triaged).
  Ships `mode: Triage` + `experimental`, eval suite under
  `tools/skill-evals/evals/contributor-activity-sweep/`.
- Skill: `contributor-nomination` — nomination evidence brief for a
  named contributor: activity breadth, consistency, vendor-neutrality
  context, and factual evidence prose for a committer or PMC thread;
  never rates the contributor or says whether they are ready.
  Read-only; never posts to any list. Ships `mode: Triage`
  + `experimental`, eval suite under
  `tools/skill-evals/evals/contributor-nomination/`.
- Skill: `contributor-calibrate` — derives committer and PMC
  reference floors, deliberately relaxed (default 0.75 of the elected
  25th percentile, `calibration_relaxation`), from the project's past
  nomination decisions on
  the private list (behind the privacy-LLM gate), honouring a holdout
  date and excluded threads; proposes a numbers-only config diff and
  keeps per-nominee data in the session scratch directory. Ships
  `mode: Triage` + `experimental`, eval suite under
  `tools/skill-evals/evals/contributor-calibrate/`.
- Skill: `contributor-candidate-screen` — screens every recent
  contributor against the floors (deterministic pre-filter, every drop
  logged), lists likely committer and PMC candidates — deliberately
  more than the PMC would consider, alphabetically by handle, never
  ranked or judged — and writes a report (the list linked to details,
  plus a one-or-two-paragraph summary of findings) with areas, floors, community signals and verified
  real names; commits it only to a repository the GitHub API reports as
  private, checked twice, after the maintainer confirms; no
  `@`-mentions. Ships `mode: Triage` + `experimental`, eval suite under
  `tools/skill-evals/evals/contributor-candidate-screen/`.
- Skill: `good-first-issue-author` — drafts one net-new good first
  issue from a supplied gap or small task; suitability gate plus
  R1–R9 readiness checklist; waits for maintainer confirmation
  before filing via `gh`. Ships `mode: Mentoring` + `experimental`,
  eval suite under `tools/skill-evals/evals/good-first-issue-author/`.
- Skill: `committer-onboarding` — post-vote ICLA check, account
  provisioning, permissions, and welcome-announcement checklist for
  committer and PMC promotions at ASF TLPs and podlings.
  Propose-before-post at every state-changing step. Ships
  `mode: Meta` + `experimental` (catalogued in the Meta table of
  `docs/modes.md`), eval suite under
  `tools/skill-evals/evals/committer-onboarding/`. Step 2 maps the
  new committer's channel identities through
  `contributor-identity-map`; the former Steps 2 and 3 are now
  Steps 3 and 4.
- Skill: `contributor-identity-map` — maps any contributor's GitHub
  handle to their Slack, Discord, Matrix, mailing-list, and
  social-media handles. Infers from the sources the session can
  reach (GitHub profile and social accounts, organization directory,
  connected chat tools, mail archives, the contributor's own text),
  grades each match `verified` / `self-declared` / `name-match` /
  `unknown`, and records into `<project-config>/contributor-identities.md`
  only what the maintainer confirms. In `nomination` context it never
  contacts the contributor and never edits the committed file.
  Consumed by `committer-onboarding` (Step 2) and
  `contributor-nomination` (Step 3). Ships `mode: Triage` +
  `experimental`, eval suite under
  `tools/skill-evals/evals/contributor-identity-map/`.
- Skill: `contributor-to-committer` — read-only activity brief that
  shows a contributor's GitHub activity next to the adopter's committer
  or PMC reference levels as plain numbers with the difference; no
  status, band, ranking, or readiness verdict, and several contributors
  are listed alphabetically by handle with a short summary. Ships `mode: Mentoring` + `experimental`.
- Skill: `contributor-sentiment` — measures contributor-sentiment
  signals over a window (thread tone, time-to-first-reply, first-PR
  retention, reviewer-load Gini), compares them with a pre-adoption
  baseline, and produces the structured gate report used to decide
  whether a family advances from `experimental` to `stable`. Read-only.
  Ships `mode: Triage` + `experimental`, eval suite under
  `tools/skill-evals/evals/contributor-sentiment/`.
- Skill: `onboarding-concierge` — answers a newcomer's "how do I
  contribute here" question grounded in `CONTRIBUTING.md` and the
  project's docs; classifies the question (setup / workflow /
  first-issue / out-of-scope) and hands design, security, and
  deprecation questions to a human. Draft only. Ships
  `mode: Mentoring` + `experimental`, eval suite under
  `tools/skill-evals/evals/onboarding-concierge/`.
- Skill: `good-first-issue-sweep` — sweeps the open issue backlog for
  existing issues that could be labelled as good first issues; classifies
  each candidate as READY, NEAR-MISS, or SKIP against the G1–G7 rubric;
  applies labels only after explicit maintainer confirmation. Ships
  `mode: Mentoring` + `experimental`, eval suite under
  `tools/skill-evals/evals/good-first-issue-sweep/`.
- Shared nomination references under
  `plugins/magpie-contributor-growth/skills/nomination/`:
  `automated-contributions.md` (discount and pushback-penalty rules),
  `community-signals.md` (Step 3 community evidence), and
  `real-names.md` (how people are named in briefs and reports),
  alongside the step files `fetch.md`, `assess.md`, and `render.md`.
- Tool: `tools/contributor-metrics` (`substrate:analytics`,
  stdlib-only plus the `jira-bridge` workspace client) with three
  subcommands.
  `fetch` collects five streams through a backend seam: change-request
  activity (PRs authored, reviews, PR threads) from the code host and
  issue activity (issues filed, triaged, commented) from the tracker,
  which may differ. The `github` backend serves both sides by default,
  unchanged; the `jira` backend serves the tracker side when
  `<project-config>/issue-tracker-config.md` (`--tracker-config`) names
  `tracker_type: jira`, for the contributor's `--tracker-login`, with
  triage read from issue history (status, labels, component, priority,
  assignee, resolution, fix version) as well as comments.
  It applies the substantive-review
  rule (thresholds overridable per caller), flags pushback candidates,
  and caches by repository, handle, window, phrases, roster and
  thresholds (`--refresh` bypasses the cache); `--since` sets a window
  that is not a whole number of months.
  `score` applies weights and the penalty and returns per-area shares
  (with an `(unlabelled)` row), merge rate, a monthly timeline, and
  which streams hit their search cap; `--since` scores a sub-window
  and `--timeline-kinds` limits the timeline to some item kinds.
  `floors` computes recency-weighted nearest-rank percentiles for
  calibration.
  Unit tests under `tools/contributor-metrics/tests/`.
- Contracts: the skills name contract operations, not `gh` commands —
  `contract:change-request` (`list_authored`, `list_reviews_given`,
  `list_authored_commits`), `contract:tracker` (`tools/tracker`:
  `list_filed`, `list_triaged`, `list_commented`, `list_created`,
  `first_reply`), `contract:source-control` (`repository_metadata`,
  `put_file`) and `contract:people` (`tools/people`: `get_profile`,
  `list_collaborators`, `add_team_member`). GitHub implements all of
  them (`tools/github/operations.md`); Jira the tracker queries and
  profile lookup. GitHub Discussions is the one GitHub-only signal,
  optional and marked as such.
- Tools: `tools/chat` (`contract:chat`, read-only `list_channels`,
  `resolve_user`, `search_messages`), `tools/chat-slack` (Slack MCP
  adapter, public channels only, never posts), and `tools/chat-discord`
  (Discord MCP adapter, public channels only, never posts).

## Behaviour & contract

- **Read-only or propose-then-confirm.** Skills read repository
  collaborator lists, first-time-contributor signals, and public
  activity histories through the contracts above; they never write a comment, post an
  announcement, or modify a roster without explicit maintainer
  confirmation.
- **Governance steps are paste-ready recipes, not autopilot.**
  `committer-onboarding` emits commands and draft announcements the
  nominator executes as themselves; the skill never submits an ICLA
  request, invites an account, or modifies repository permissions
  directly.
- **Evidence is curated, not fabricated.** `contributor-nomination`
  and `contributor-activity-sweep` read public GitHub activity only;
  they do not invent contributions or inflate counts. The brief and
  activity card are inputs for a PMC vote, not a pre-decided
  recommendation.
- **Automated and low-signal work counts for less.**
  `contributor-to-committer` and `contributor-nomination` apply the
  shared definition in `nomination/automated-contributions.md`:
  restatements and work maintainers pushed back on are down-weighted,
  work closed after pushback weighs `0`, and each pushed-back thread
  carries a small penalty (`automated_pushback_penalty`, default
  `0.25`) so the adjusted count can fall below the discounted one.
  Using AI tools is not penalised; the brief shows raw, discounted,
  penalty and adjusted values, and pushback is a signal to weigh,
  never a disqualification.
- **Counting is deterministic.** Both skills collect activity with
  `tools/contributor-metrics`: five streams (PRs authored,
  issues filed, reviews with one shared substantive rule, threads
  commented, issues triaged on other people's issues), per-area shares
  from `area_label_prefix` labels, and the weights and penalty above.
  The tool flags pushback candidates; the skill confirms each one on
  meaning before the tool scores it.
- **Community signals are evidence, not a score.** Step 3 of both
  skills collects `nomination/community-signals.md`: dev/users-list
  presence and release testing, chat answers through `contract:chat`
  (Slack or Discord adapter; public channels only), GitHub Discussions answers,
  and project-related posts on accounts the contributor linked
  themselves. Identities count only when confirmed: a chat or social
  profile that merely names the GitHub handle is a possible match, not
  an identity, and a self-linked account counts only when it links back
  to the GitHub profile. Reasoned criticism is constructive. The
  community indicator never changes counts, thresholds or the band,
  though any confirmed collected row means an off-GitHub signal is
  present; in `contributor-to-committer` that signal is always
  mandatory and never treated as met by default.
- **Thresholds come from the project's own history.**
  `contributor-calibrate` reads past `[DISCUSS]` / `[VOTE]` / `[RESULT]`
  nomination threads on the private list behind the privacy-LLM gate.
  It keeps one structured row per nomination (target, vote date,
  outcome, coarse deferral category), never votes, opinions or quotes.
  It bounds the archive query at the holdout date and never opens an
  excluded thread.
  `contributor-metrics floors` computes the floors; a metric that does
  not separate elected from deferred nominees is evidence-only, and
  capped counts are left out of a metric's distribution.
  The config diff carries numbers, `calibrated_on` and
  `calibrated_window_months` only, and is written to the personal
  layer (`setup_preflight.layers` → `personal_dir`); calibration never
  offers `.apache-magpie-overrides/`.
  `contributor-to-committer` warns on a mismatched window and suggests
  recalibrating after a year; `contributor-nomination` flags stale or
  mismatched calibration; `/magpie-setup config` offers calibration
  when thresholds are blank.
- **Screening reports go only to a verified-private repository.**
  `contributor-candidate-screen` builds its pool from merged PRs,
  sliced by month and then week so GitHub's 1000-result search limit
  never truncates it (it stops if a single day exceeds the limit).
  It maps roster ids to GitHub handles through the directory or the
  maintainer, never by guessing, and stops without a roster.
  It logs every pre-filter drop, ignores evidence-only floors, does not
  pre-filter the PMC pool, and treats a capped count below its floor as
  unknown (written `>= N`), never missing.
  The report is committed to `report_repo` only after the maintainer
  confirms, and only when the code host reports the repository private
  (`contract:source-control` → `repository_metadata`),
  checked before showing and again before writing; a gist is never
  offered. The report uses plain profile links, never `@`-mentions.
- **Real names are verified, never inferred.** Briefs and reports name
  people per `nomination/real-names.md`: the people directory first,
  then the code-host profile name (`contract:people` → `get_profile`),
  then a consistent commit author name.
  A name is never inferred from an email address or a handle.
- **Personal-recommended, not adoptable by default.**
  Committer thresholds, nomination criteria, calibration floors,
  sentiment caps and the identity map, committed to the repository,
  become a public checklist contributors can point at to demand
  promotion, and every edit to them a negotiation.
  `/magpie-setup adopt` therefore leaves `magpie-contributor-growth`
  out of the floor and recommends a personal install; it adds the
  family only when the maintainer insists and explicitly accepts the
  quoted risk, recording the acceptance as a comment above the entry
  in `.apache-magpie.lock`.
  Even then the five configuration files
  (`committer-onboarding-config.md`, `committer-readiness.md`,
  `contributor-identities.md`, `contributor-nomination-config.md`,
  `contributor-sentiment-config.md`) live only in the personal layer:
  `adopt` never promotes or scaffolds them into
  `.apache-magpie-overrides/`, the skills write them only to the
  personal layer and read the committed copy only as a fallback, and
  `skill-and-tool-validate` warns (SOFT) when one is found there.
- **Teaching register for first-contact.** `mentoring-welcome` and
  `good-first-issue-author` follow the Agentic Mentoring mode's tone
  contract (polite, never gatekeeping) and hand off to a human
  reviewer on anything that exceeds the agent's scope.

## Out of scope

- **PMC-member nomination** (distinct from committer-to-PMC path):
  not yet specced; the vote mechanics, quorum rules, and post-vote
  steps differ enough to warrant a separate spec-RFC pass that
  enumerates the option set and per-project policy knobs.
- **Emeritus / inactive-committer handling and contributor
  offboarding**: intentionally deferred pending scope agreement —
  these involve project-level governance decisions (roster policy,
  communication norms) that no skill can safely generalise without
  per-project configuration.
- Auto-promoting a contributor: all promotion decisions stay with the
  PMC; the skills prepare evidence and checklists, never act on the
  vote outcome without the nominator's explicit direction.

## Acceptance criteria

1. `mentoring-welcome` does not draft or post for repeat contributors
   (the `author_association` gate fires before any draft is produced).
2. `contributor-nomination` and `contributor-activity-sweep` are
   read-only — neither posts, labels, nor modifies any issue or PR.
3. `committer-onboarding` emits paste-ready command recipes; no step
   submits ICLA forms or changes repository permissions without the
   nominator's direct action.
4. All family skills pass `skill-and-tool-validate` with no errors.
5. `/magpie-setup adopt` does not add `magpie-contributor-growth` to the
   floor without an explicit, recorded acceptance of the gaming risk,
   and never writes the family's configuration files to
   `.apache-magpie-overrides/`.
6. `contributor-calibrate` writes its floors to the personal layer
   (the git-directory home on an unadopted repository) and never offers
   `.apache-magpie-overrides/`
   (`tools/skill-evals/evals/contributor-calibrate/step-6-write-configuration/`).

## Validation

```bash
uv run --project tools/skill-and-tool-validator --group dev skill-and-tool-validate
```

## Known gaps

- **PMC-member nomination is not yet specced.** The committer-to-PMC
  promotion has different vote mechanics (full-PMC vote, different
  quorum) and post-vote steps from committer promotion. Defining it as
  a capability-flag variant of `committer-onboarding` or as a
  standalone skill requires a spec-RFC pass that enumerates the option
  set and documents defaults. Candidate work item for a future plan
  pass.
- **Emeritus / inactive-committer handling and contributor offboarding
  are intentionally deferred.** Both involve project-level policy
  (when to move to emeritus, how to handle access removal, whether to
  send a farewell announcement) that needs per-project configuration
  before a skill can safely propose anything. These are candidate work
  items once the active-path skills stabilise and an adopter pilot
  surfaces the concrete policy knobs needed.
- **Mode boundary with Agentic Mentoring is intentionally fuzzy.** Five
  family skills (`mentoring-welcome`, `good-first-issue-author`,
  `contributor-to-committer`, `good-first-issue-sweep`,
  `onboarding-concierge`) carry `mode: Mentoring` and are documented in
  [mentoring-mode.md](mentoring-mode.md).
  Six carry `mode: Triage` (`contributor-activity-sweep`,
  `contributor-nomination`, `contributor-calibrate`,
  `contributor-candidate-screen`, `contributor-identity-map`,
  `contributor-sentiment`), and `committer-onboarding` carries
  `mode: Meta`.
  The plugin split does not follow the mode split either:
  `onboarding-concierge` and `contributor-to-committer` ship in
  `magpie-contributor-growth`, the other three Mentoring skills in
  `magpie-mentoring`.
  A later family-maturity review may formalise the boundary or merge the
  families; for now, both specs cross-reference each other.
- **Chat evidence covers Slack and Discord.** `contract:chat` has two shipping adapters
  (`tools/chat-slack`, `tools/chat-discord`); Matrix and Zulip answers are not collected
  until an adapter lands.
- **`experimental` — no adopter pilot has run.** All twelve skills exist
  but no maintainer has run the full contributor-to-committer path
  end-to-end through the family, and calibration has not yet run against
  a real project's nomination history. Shape may change as adopter
  pilots surface real-world usage patterns.
