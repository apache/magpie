<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Apache Magpie — contributor-nomination configuration](#apache-magpie--contributor-nomination-configuration)
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

# Apache Magpie — contributor-nomination configuration

Per-project configuration for the
[`contributor-nomination`](../skills/contributor-nomination/SKILL.md)
skill. Copy into your `<project-config>/` directory and replace
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
| `nomination_window_months` | `6` | How many months of activity to assess. 6 is a common starting point; slower-moving projects may prefer 12. |

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
| PRs merged | 5 | (default) | Reasonable floor for a mid-size project; set lower if your project is small or welcomes contributors freely |
| Reviews given | 3 | (default) | Shows engagement with others' work |
| Substantive reviews | 2 | (default) | Reviews with real inline feedback |
| Issues filed | 0 | (default) | Not required — many valid tracks don't involve filing issues |
| Comments | 5 | (default) | Basic community presence |
| Mailing list presence | none | (default) | Qualitative — fill in if your project tracks this |

### PMC thresholds

| Area | Default (low bar) | Project value | Notes |
|---|---|---|---|
| PRs merged | 10 | (default) | |
| Reviews given | 8 | (default) | PMC members are expected to help evaluate others' work |
| Substantive reviews | 4 | (default) | |
| Community leadership signal | "present" | (default) | Qualitative — some evidence of guiding others or shaping direction |

---

## Required areas by target *(optional)*

Only declare if your project's PMC has a formal policy.
Leaving this blank means the skill treats all contribution
tracks (code, docs, testing, community) as equally valid paths.

| Target | Required areas | Notes |
|---|---|---|
| `committer` | (default) | e.g. `none` — many projects accept doc/community committers |
| `pmc` | (default) | e.g. `review or community` |

---

## Automated and low-signal contributions

How the nomination brief discounts visibly automated or low-signal GitHub activity.
The full definition — detection heuristics, aggregation, and how the brief reports raw and adjusted counts — is [`automated-contributions.md`](../skills/contributor-nomination/automated-contributions.md).

The discount is a signal for the humans reading the brief, never an automatic disqualification.
Using AI tools, and disclosing that use, is not penalised; only restatement, content maintainers pushed back on, and work closed after that pushback are discounted.

Each key is resolved from this file, then from the default below.
The readiness tracker falls back to these values when `committer-readiness.md` does not set its own.

| Key | Default | Project value | Notes |
|---|---|---|---|
| `automated_contribution_weight` | `0.25` | (default) | Weight (0–1) of a merged or open PR, issue, review or comment that drew maintainer pushback as looking generated, unreviewed, restating, fabricated, or unwanted |
| `restatement_comment_weight` | `0` | (default) | Weight (0–1) of a comment or review body that only restates the description, earlier comments, or the diff |
| `closed_after_pushback_weight` | `0` | (default) | Weight (0–1) of a PR or issue closed unmerged after that pushback; `0` removes it from every metric |
| `automated_pushback_phrases` | empty | (default) | Extra phrases your maintainers use when pushing back, added to the generic list |

Set all three weights to `1` to turn the arithmetic off; flagged items are still listed in the brief.

### Project expectations for AI-assisted contributions

List the documents in which your project states what it expects from AI-assisted and automated contributions — a generative-AI contribution policy, PR guidelines, a review or triage guide.
Use paths relative to the repository root, or `https://` URLs, optionally with a `#section` anchor.

```yaml
automated_contribution_expectations:
  - docs/ai-contribution-policy.md
  - https://www.apache.org/legal/generative-tooling.html#include-in-contributions
  - CONTRIBUTING.md#authoring-with-an-agent
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
Apache Magpie became a top-level project in June 2026, so contributor
histories are short: judge against the 6-month window, and do not read a
short history as a negative signal by itself.
All development happens in the single repository apache/magpie.
Most contributions are authored with a coding agent. That is expected and
neither a positive nor a negative signal; assess ownership and review quality
against docs/ai-contribution-policy.md.
Skill, eval and documentation work counts as code contribution here: the
framework is written in English as code (CONTRIBUTING.md#english-as-code).
Committer and PMC votes happen on private@magpie.apache.org.
```
