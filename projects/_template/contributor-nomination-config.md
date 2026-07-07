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
  - [Project-specific notes *(optional)*](#project-specific-notes-optional)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# TODO: `<Project Name>` — contributor-nomination configuration

Per-project configuration for the
[`contributor-nomination`](../../skills/contributor-nomination/SKILL.md)
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
| `nomination_window_months` | TODO: e.g. `6` | How many months of activity to assess. 6 is a common starting point; slower-moving projects may prefer 12. |

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
| Substantive reviews | 2 | TODO or leave as default | Reviews with real inline feedback |
| Issues filed | 0 | TODO or leave as default | Not required — many valid tracks don't involve filing issues |
| Comments | 5 | TODO or leave as default | Basic community presence |
| Mailing list presence | none | TODO or leave as default | Qualitative — fill in if your project tracks this |

### PMC thresholds

| Area | Default (low bar) | Project value | Notes |
|---|---|---|---|
| PRs merged | 10 | TODO or leave as default | |
| Reviews given | 8 | TODO or leave as default | PMC members are expected to help evaluate others' work |
| Substantive reviews | 4 | TODO or leave as default | |
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

## Project-specific notes *(optional)*

Free text surfaced at the top of every brief. Use for project
norms the nominator should know — e.g. "This project has
multiple active repositories; ask the maintainer to check
contributor activity across all of them, not just `<upstream>`."

```text
TODO: leave blank or add guidance here.
```
