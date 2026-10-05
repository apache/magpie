<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [TODO: `<Project Name>` — contributor-nomination configuration](#todo-project-name--contributor-nomination-configuration)
  - [Assessment window](#assessment-window)
  - [Thresholds *(optional — leave blank if not configured)*](#thresholds-optional--leave-blank-if-not-configured)
    - [Committer thresholds](#committer-thresholds)
    - [PMC thresholds](#pmc-thresholds)
  - [Required areas by target *(optional)*](#required-areas-by-target-optional)
  - [Automated and low-signal contributions](#automated-and-low-signal-contributions)
    - [Project expectations for AI-assisted contributions](#project-expectations-for-ai-assisted-contributions)
  - [Project-specific notes *(optional)*](#project-specific-notes-optional)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# TODO: `<Project Name>` — contributor-nomination configuration

> **Personal configuration — keep it in your personal layer, never commit it to `.apache-magpie-overrides/`.**
> Committed, these values become a public checklist contributors can point at to demand a nomination, and every edit to them becomes a negotiation.
> The personal layer is `<git-common-dir>/apache-magpie/` when Magpie is only installed, `.apache-magpie-local/` when the project has adopted it.
> See [Why the configuration is personal](../../../docs/contributor-growth/README.md#why-the-configuration-is-personal).

Per-project configuration for the
[`contributor-nomination`](../../../skills/contributor-nomination/SKILL.md)
skill. Copy into your personal layer and replace
every TODO.

**Thresholds are optional.** If this file does not declare
thresholds, the skill asks the maintainer for the project's
typical bar at run time and reports raw numbers for the PMC to
judge. Only declare thresholds here if your PMC has agreed on
explicit criteria — thresholds vary enormously across projects
and there are no meaningful framework defaults.

---

## Assessment window

| Key | Value | Notes |
|---|---|---|
| `nomination_window_months` | TODO: e.g. `6` | How many months of activity to assess. 6 is a common starting point; slower-moving projects may prefer 12. |
| `area_label_prefix` | TODO or leave blank (default `area:`) | Label prefix that marks a PR's area; used for area breadth and the per-area table in the brief. |
| `calibrated_on` | leave blank | Written by `calibrate` when it sets the thresholds below from past nominations; other skills suggest recalibrating after 12 months. |
| `calibration_recency_halflife_years` | `2` | How fast `calibrate` down-weights older nominations. |
| `calibrated_window_months` | leave blank | Written by `calibrate`: the activity window the floors were derived for. The skills warn when it differs from the assessment window. |
| `community_negative_weight` | `1` | How much each unconstructive community item subtracts from the community indicator; the indicator never feeds a threshold. |
| `report_repo` | TODO: `owner/name` of a **private** repository | Where `candidate-screen` commits its report. The skill refuses unless the GitHub API reports the repository as private; restrict it to `<governance-body>` members. |
| `report_path` | `reports/` | Directory inside `report_repo` for the reports. |
| `screen_prefilter_ratio` | `0.5` | `candidate-screen` keeps a contributor for full measurement when merged PRs or reviews reach this share of the floor. |
| `shortlist_max_missing` | `2` | `candidate-screen` shortlists a contributor who misses at most this many floors (evidence-only metrics excluded). |

---

## Thresholds *(optional — leave blank if not configured)*

Declare only if your PMC has agreed on explicit criteria for
what counts as sufficient activity on this project. These
replace the run-time question to the maintainer about the
project bar. Calibrate against your project's own contribution
history — recent successful nominations are the best reference.

### Committer thresholds

The values below are a reasonable low bar for a mid-size active
project, not a universal standard. Calibrate in either direction:

- **Raise them** if your project is large or high-velocity and
  recent successful nominations reflect significantly more activity.
- **Lower them** if your project is small, early-stage, or
  deliberately gives committership freely as a welcoming gesture.
  That is a valid project culture — these defaults should not
  imply otherwise.

| Area | Default (low bar) | Project value | Notes |
|---|---|---|---|
| PRs merged | 5 | TODO or leave as default | Reasonable floor for a mid-size project; set lower if your project is small or welcomes contributors freely |
| Reviews given | 3 | TODO or leave as default | Shows engagement with others' work |
| Substantive reviews | 2 | TODO or leave as default | A review body over 100 characters or at least one line comment |
| Issues filed | 0 | TODO or leave as default | Not required — many valid tracks don't involve filing issues |
| Comments | 5 | TODO or leave as default | Basic community presence |
| Issues triaged | 0 | TODO or leave as default | Other people's issues the contributor commented on; 0 = advisory |
| Mailing list presence | 0 | TODO or leave as default | Threads started plus replies on the development list, from a confirmed address; 0 = advisory |

### PMC thresholds

| Area | Default (low bar) | Project value | Notes |
|---|---|---|---|
| PRs merged | 10 | TODO or leave as default | |
| Reviews given | 8 | TODO or leave as default | PMC members are expected to help evaluate others' work |
| Substantive reviews | 4 | TODO or leave as default | |
| Issues filed | 0 | TODO or leave as default | |
| Comments | 10 | TODO or leave as default | |
| Area breadth | 2 | TODO or leave as default | Distinct area labels across merged PRs |
| Issues triaged | 0 | TODO or leave as default | |
| Mailing list presence | 0 | TODO or leave as default | Threads started plus replies on the development list, from a confirmed address; 0 = advisory |
| Community leadership signal | "present" | TODO or leave as default | Qualitative — some evidence of guiding others or shaping direction |

---

## Required areas by target *(optional)*

Only declare if your project's PMC has a formal policy.
Leaving this blank means the skill treats all contribution
tracks (code, docs, testing, community) as equally valid paths.

| Target | Required areas | Notes |
|---|---|---|
| `committer` | TODO or leave blank | e.g. `none` — many projects accept doc/community committers |
| `pmc` | TODO or leave blank | e.g. `review or community` |

---

## Automated and low-signal contributions

How the nomination brief discounts visibly automated or low-signal GitHub activity.
The full definition — detection heuristics, aggregation, and how the brief reports raw and adjusted counts — is [`automated-contributions.md`](../../../skills/contributor-nomination/automated-contributions.md).

The discount is a signal for the humans reading the brief, never an automatic disqualification.
Using AI tools, and disclosing that use, is not penalised; only restatement, content maintainers pushed back on, and work closed after that pushback are discounted.

Each key is resolved from this file, then from the default below.
The readiness tracker falls back to these values when `committer-readiness.md` does not set its own.

| Key | Default | Project value | Notes |
|---|---|---|---|
| `automated_contribution_weight` | `0.25` | TODO or leave blank | Weight (0–1) of a merged or open PR, issue, review or comment that drew maintainer pushback as looking generated, unreviewed, restating, fabricated, or unwanted |
| `restatement_comment_weight` | `0` | TODO or leave blank | Weight (0–1) of a comment or review body that only restates the description, earlier comments, or the diff |
| `closed_after_pushback_weight` | `0` | TODO or leave blank | Weight (0–1) of a PR or issue closed unmerged after that pushback; `0` removes it from every metric |
| `automated_pushback_penalty` | `0.25` | TODO or leave blank | Subtracted (0–1) once per pushed-back or closed-after-pushback thread, after the weights; `0` turns it off |
| `automated_pushback_phrases` | empty | TODO or leave blank | Extra phrases your maintainers use when pushing back, added to the generic list |

Set all three weights to `1` and the penalty to `0` to turn the arithmetic off; flagged items are still listed in the brief.

### Project expectations for AI-assisted contributions

List the documents in which your project states what it expects from AI-assisted and automated contributions — a generative-AI contribution policy, PR guidelines, a review or triage guide.
Use paths relative to the repository root, or `https://` URLs, optionally with a `#section` anchor.

```yaml
automated_contribution_expectations:
  - TODO: e.g. CONTRIBUTING.md#generative-ai-contributions
  - TODO: e.g. https://example.org/docs/pr-guidelines#ai-assisted-changes
```

When the list is present, the skill reads each document, judges contributions against it first, and cites the document and section each flagged item conflicts with.
When it is empty or none of the documents can be read, the skill falls back to the framework's generic heuristics and says so in the brief.
The skill does not go looking for policy documents this list does not name.

---

## Project-specific notes *(optional)*

Free text surfaced at the top of every brief. Use for project
norms the nominator should know — e.g. "This project has
multiple active repositories; ask the maintainer to check
contributor activity across all of them, not just `<upstream>`."

```text
TODO: leave blank or add guidance here.
```
