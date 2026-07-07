<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [TODO: `<Project Name>` — committer-readiness configuration](#todo-project-name--committer-readiness-configuration)
  - [Assessment window](#assessment-window)
  - [Committer thresholds](#committer-thresholds)
  - [PMC thresholds](#pmc-thresholds)
  - [Project-specific notes *(optional)*](#project-specific-notes-optional)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# TODO: `<Project Name>` — committer-readiness configuration

Per-project thresholds for the
[`contributor-to-committer`](../../skills/contributor-to-committer/SKILL.md)
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

---

## Committer thresholds

Calibrate against recent successful nominations on your project, not
against framework defaults. The numbers below are a low bar for a
mid-size active project.

| Dimension | Default (low bar) | Project value | Notes |
|---|---|---|---|
| `prs_merged` | `5` | TODO or leave blank (uses default) | Merged PRs — the clearest signal of sustained code contribution |
| `reviews_total` | `3` | TODO or leave blank | Total review acts — shows engagement with others' work |
| `reviews_substantive` | `2` | TODO or leave blank | Reviews with real inline feedback (≥ 3 comments or > 50 char body) |
| `issues_filed` | `0` | TODO or leave blank | Set to 0 to treat as non-required; many valid tracks don't involve filing issues |
| `threads_commented` | `5` | TODO or leave blank | PR/issue comment threads — basic community presence |
| `area_breadth` | `0` | TODO or leave blank | Distinct `area:*` labels across merged PRs; 0 = no breadth requirement |

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

---

## Project-specific notes *(optional)*

Free text surfaced at the top of every readiness brief. Use for norms
the maintainer should see — e.g. multi-repo projects, non-GitHub
contribution tracks that are particularly valued, or cultural notes
about how the PMC calibrates nominations.

```text
TODO: leave blank or add guidance here.
```
