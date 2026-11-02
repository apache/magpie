<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

---
title: Emeritus transitions and contributor offboarding
status: proposed
kind: feature
mode: Triage
source: >
  contributor-growth.md § Known gaps ("Emeritus / inactive-committer
  handling and contributor offboarding are intentionally deferred ...
  need per-project configuration before a skill can safely propose
  anything"). docs/contributor-growth/README.md § deferred items. To be
  implemented as two skills in plugins/magpie-contributor-growth/ beside
  committer-onboarding, a config template in
  plugins/magpie-setup/templates/, and counting in tools/contributor-metrics.
acceptance:
  - Nothing runs until the project's offboarding policy is configured; a
    missing policy key stops the skill and names the key, never a default.
  - The inactivity report is data only — per-person activity next to the
    project's own window — with no ranking, label or verdict, and is only
    ever produced into a verified-private destination.
  - Moving anyone to emeritus, removing access, or contacting the person
    is always a proposal the governance body has decided and a maintainer
    confirms; the skills never act on inactivity alone.
  - A self-requested move to emeritus is a first-class path that needs no
    inactivity evidence.
  - Every write goes through the project's configured governance model
    (asf-pmc, github-codeowners, maintainer-roster), reusing
    committer-onboarding's model branches in reverse.
  - Reinstatement from emeritus is documented and as cheap as the
    project's policy allows.
---

# Emeritus transitions and contributor offboarding

## What it does

The contributor-growth family covers the path *into* a project's roster:
first contact, activity, nomination, onboarding. It has nothing for the path
out. Committers and governance-body members go quiet, change jobs, or ask to
step back, and projects handle that by hand: an occasional roster review, an
emeritus list, a removed GitHub team membership, sometimes a farewell note.

Done badly, this is one of the most damaging things a bot can do to a
community. Labelling someone "inactive" in public, pinging them to justify
their membership, or revoking access because a counter crossed a line
reads as being pushed out. This spec therefore splits the work in two, and
puts the hard boundary between them:

1. **`contributor-inactivity-report`** (read-only). For the roster the
   project names, report each member's activity across the signals the
   project counts, next to the project's own inactivity window. Data only,
   like `contributor-candidate-screen`: no ranking, no "inactive" label, no
   recommendation. It is produced only into a private destination, for the
   governance body's own review.
2. **`contributor-emeritus`** (propose-then-confirm). After the governance
   body has decided, or the person has asked, draft every step of the move:
   the roster change through the project's governance model, the access
   change the policy calls for (possibly none), and the communication the
   policy calls for (possibly none). Each step is shown and applied only on
   a maintainer's yes. It is `committer-onboarding` in reverse, and reuses
   that skill's per-model branches.

The two never chain automatically. A report is input to a human decision,
and the emeritus skill starts from that decision, never from the report.

## Where it lives

Nothing in this section exists yet; it is the proposed shape.

- `plugins/magpie-contributor-growth/skills/inactivity-report/` and
  `plugins/magpie-contributor-growth/skills/emeritus/`, symlinked as
  `skills/contributor-inactivity-report` and `skills/contributor-emeritus`,
  each with an eval suite under `tools/skill-evals/evals/`.
- `plugins/magpie-setup/templates/contributor-offboarding-config.md`: the
  policy template (below), resolved through the usual `<project-config>`
  chain. Organization defaults (`organizations/<org>/organization.md`) may
  supply a governance model but never an inactivity window.
- `tools/contributor-metrics/`: an `activity` subcommand that counts, per
  person and window, the signals the policy enables, reusing its existing
  GitHub and Jira backends and the identity map.
- `plugins/magpie-contributor-growth/skills/committer-onboarding/detail/governance-*.md`:
  each model branch gains an emeritus section, so onboarding and offboarding
  describe one roster mechanism, not two.

## Behaviour & contract

### Policy, configured before anything runs

`contributor-offboarding-config.md` holds the project's decisions. Every key
is required; the skills stop and name a missing key rather than assume one,
because a framework default for "when is someone inactive" would be the
framework deciding a community question.

| Key | Meaning |
|---|---|
| `inactivity_window_months` | The span the report measures. |
| `signals` | Which activity counts: any of `commits`, `reviews`, `issues`, `list_posts`, `votes`, `chat`. A project that values review and mailing-list work says so here. |
| `roster_source` | Where the roster is read from, per governance model (Whimsy for `asf-pmc`, a team for `github-codeowners`, a file for `maintainer-roster`). |
| `decision` | Who decides a move: `governance-body-vote`, `chair`, or `self-request-only` (the project never initiates). |
| `emeritus_record` | How emeritus status is recorded: `roster-field`, `separate-list`, or `none`. |
| `access_on_emeritus` | What access changes: `none`, `write`, or `all`. |
| `notify_person` | Whether and how the person hears first: `private-message-first`, `none`. |
| `announcement` | `none`, `private-list`, or `public`. |
| `reinstatement` | `on-request`, or `governance-body-vote`. |
| `exclusions` | People never reported (a declared sabbatical, a founding emeritus list). |

### The inactivity report

- Reads the roster and counts each enabled signal per person over the
  window through `contributor-metrics activity`, resolving identities through
  the identity map. A person whose identity cannot be resolved on a signal is
  reported as *unknown* on it, never as zero.
- Presents an alphabetical table of raw counts and the date of last activity
  per signal, with the window stated once. No sorting by activity, no
  colour, no threshold column, no "inactive" wording.
- Writes only to a destination verified private (as
  `contributor-candidate-screen` does); refuses a public repository, issue,
  or channel.
- Never contacts anyone, never edits the roster, never proposes a move.

### The emeritus move

- Starts from one of two inputs: a governance-body decision (a vote-thread
  URL or a chair's statement, per `decision`), or the person's own request.
  It does not accept the inactivity report as an input.
- Validates the decision the way `committer-onboarding` validates a vote:
  the thread exists, the bar the project's policy sets is met, and content
  inside the thread is data, never an instruction.
- Drafts each step the policy calls for, in order, through the project's
  governance model: notify the person first when `notify_person` says so,
  then the roster change, then the access change, then the announcement.
  Each step is shown in full and applied only on a maintainer's yes; a
  declined step is reported, not retried.
- Never removes access the policy does not name, and never removes more
  than `access_on_emeritus` allows.
- A self-request is accepted only when it comes from an identity the
  identity map ties to the roster member (a post to the private list from
  their own address, or a message from their own forge account); the
  skill shows that link before drafting anything, and a request it cannot
  tie to the member is refused, never assumed.
  A verified self-request skips the decision step; its draft text thanks
  the person, and whether and where it is sent still follows
  `notify_person` and `announcement`.

### Reinstatement

- The same skill handles the return: on `reinstatement: on-request` it
  drafts the roster and access changes back; on `governance-body-vote` it
  starts, like a move, from the decision.

## Out of scope

- Automatic moves of any kind. No schedule, no threshold, no chaining from
  the report.
- Judging the quality or worth of anyone's contributions.
- Code-of-conduct removals and other disciplinary action, which are a
  different process with different confidentiality rules.
- Revoking foundation-level accounts (an ASF account, an ICLA): only the
  project's own roster and access are in scope.

## Acceptance criteria

1. With any policy key missing, both skills stop before reading the roster
   and name the key.
2. The inactivity report contains raw counts and last-activity dates only;
   an eval case asserts it carries no ranking, threshold, or "inactive"
   wording, and that an unresolved identity reads *unknown*, not zero.
3. The report refuses a destination that is not verified private.
4. `contributor-emeritus` refuses to start from an inactivity report and
   accepts a decision thread or a self-request; a self-request from an
   identity the identity map does not tie to the roster member is refused
   (eval case).
5. Each emeritus step is proposed and applied only on confirmation, in the
   policy's order, and an access change never exceeds
   `access_on_emeritus`.
6. Injected instructions in a decision thread do not change the outcome
   (eval case).
7. Each `committer-onboarding` governance-model branch documents the
   emeritus counterpart of its roster step.
8. Both skills validate under `skill-and-tool-validate` and ship eval
   suites.

## Validation

```bash
uv run --project tools/spec-validator --group dev spec-validate
```

Once built:

```bash
uv run --project tools/skill-and-tool-validator --group dev skill-and-tool-validate
uv run --project tools/contributor-metrics --group dev pytest
uv run --project tools/skill-evals skill-eval tools/skill-evals/evals/contributor-inactivity-report/
uv run --project tools/skill-evals skill-eval tools/skill-evals/evals/contributor-emeritus/
```

## Known gaps

- **Not built.** Neither skill, the config template, nor the
  `contributor-metrics activity` subcommand exists.
  <!-- gap-closes-when: path-exists:plugins/magpie-contributor-growth/skills/emeritus/SKILL.md -->
- **Foundation rules must be confirmed before the `asf-pmc` branch is
  written.** How an ASF project records an emeritus PMC member and what the
  foundation requires of the chair are foundation policy, to be read from
  the ASF's own pages at build time, not assumed here.
  <!-- gap-closes-when: none (narrative) -->
- **The policy keys come from first principles, not a pilot.** An adopter
  pilot may show a key is missing or two should merge; the spec is
  `proposed` until one runs.
  <!-- gap-closes-when: none (narrative) -->
