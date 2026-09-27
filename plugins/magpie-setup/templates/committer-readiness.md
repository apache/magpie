<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [TODO: `<Project Name>` — committer-readiness configuration](#todo-project-name--committer-readiness-configuration)
  - [Assessment window](#assessment-window)
  - [Committer thresholds](#committer-thresholds)
  - [PMC thresholds](#pmc-thresholds)
  - [Automated and low-signal contributions](#automated-and-low-signal-contributions)
    - [Project expectations for AI-assisted contributions](#project-expectations-for-ai-assisted-contributions)
  - [Project-specific notes *(optional)*](#project-specific-notes-optional)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# TODO: `<Project Name>` — committer-readiness configuration

Per-project thresholds for the
[`contributor-to-committer`](../../../skills/contributor-to-committer/SKILL.md)
readiness tracker. Copy into your `<project-config>/` directory and
replace every TODO.

**Thresholds are optional.** If this file does not declare thresholds,
the skill falls back to `contributor-nomination-config.md` thresholds,
or asks the maintainer at run time. Only declare thresholds here if
your PMC has agreed on explicit criteria — they vary across projects
and there are no meaningful universal defaults.

**This file is separate from `contributor-nomination-config.md`** so
that the readiness tracker and the nomination brief can be tuned
independently. If your project uses the same bar for both, you can
set this file's thresholds to the same values and keep a single place
to update them.

---

## Assessment window

| Key | Value | Notes |
|---|---|---|
| `assessment_window_months` | TODO: e.g. `6` | How many months of activity to assess. 6 is common; slower-moving projects may prefer 12. |
| `area_label_prefix` | TODO or leave blank (default `area:`) | Label prefix that marks a PR's area; used for area breadth and the per-area table in the brief. |
| `calibrated_on` | leave blank | Written by `calibrate` when it sets the thresholds below from past nominations; other skills suggest recalibrating after 12 months. |
| `calibration_recency_halflife_years` | `2` | How fast `calibrate` down-weights older nominations. |
| `calibrated_window_months` | leave blank | Written by `calibrate`: the activity window the floors were derived for. The skills warn when it differs from the assessment window. |
| `community_negative_weight` | `1` | How much each unconstructive community item subtracts from the community indicator; the indicator never feeds a threshold. |

---

## Committer thresholds

Calibrate against recent successful nominations on your project, not
against framework defaults. The numbers below are a low bar for a
mid-size active project.

| Dimension | Default (low bar) | Project value | Notes |
|---|---|---|---|
| `prs_merged` | `5` | TODO or leave blank (uses default) | Merged PRs — the clearest signal of sustained code contribution |
| `reviews_total` | `3` | TODO or leave blank | Total review acts — shows engagement with others' work |
| `reviews_substantive` | `2` | TODO or leave blank | Reviews with real feedback — a body over 100 characters or at least one line comment |
| `issues_filed` | `0` | TODO or leave blank | Set to 0 to treat as non-required; many valid tracks don't involve filing issues |
| `threads_commented` | `5` | TODO or leave blank | PR/issue comment threads — basic community presence |
| `area_breadth` | `0` | TODO or leave blank | Distinct `area:*` labels across merged PRs; 0 = no breadth requirement |
| `issues_triaged` | `0` | TODO or leave blank | Other people's issues the contributor commented on; 0 = advisory |
| `mailing_list_posts` | `0` | TODO or leave blank | Threads started plus replies on the development list; 0 = advisory |

---

## PMC thresholds

PMC membership requires demonstrated community leadership beyond code.
Raise these well above the committer bar for any project that treats
PMC as a senior track.

| Dimension | Default (low bar) | Project value | Notes |
|---|---|---|---|
| `prs_merged` | `10` | TODO or leave blank | |
| `reviews_total` | `8` | TODO or leave blank | PMC members are expected to help evaluate others' work |
| `reviews_substantive` | `4` | TODO or leave blank | |
| `issues_filed` | `0` | TODO or leave blank | |
| `threads_commented` | `10` | TODO or leave blank | |
| `area_breadth` | `2` | TODO or leave blank | PMC members typically span multiple project areas |
| `issues_triaged` | `0` | TODO or leave blank | |
| `mailing_list_posts` | `0` | TODO or leave blank | |

---

## Automated and low-signal contributions

How the readiness tracker discounts visibly automated or low-signal GitHub activity.
The full definition — detection heuristics, aggregation, and how the brief reports raw and adjusted counts — is [`automated-contributions.md`](../../../skills/contributor-nomination/automated-contributions.md).

The discount is a signal for the humans reading the brief, never an automatic disqualification.
Using AI tools, and disclosing that use, is not penalised; only restatement, content maintainers pushed back on, and work closed after that pushback are discounted.

Each key is resolved from this file first, then from `contributor-nomination-config.md`, then from the default below.

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

Free text surfaced at the top of every readiness brief. Use for norms
the maintainer should see — e.g. multi-repo projects, non-GitHub
contribution tracks that are particularly valued, or cultural notes
about how the PMC calibrates nominations.

```text
TODO: leave blank or add guidance here.
```
