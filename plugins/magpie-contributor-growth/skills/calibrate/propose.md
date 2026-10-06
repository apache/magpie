<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Propose

How the measured rows become proposed floors, and how the floors map onto the two config files.
`contributor-metrics floors` does the arithmetic below; this file states what it computes, so the maintainer can check the result, and how to present it.

## Weighting

Weight each row by recency: `w = 0.5 ** (age_years / halflife)`, where `age_years` is the time from the vote date to today and `halflife` is `calibration_recency_halflife_years` (default `2`).

## Weighted percentiles

Sort the rows by the metric's value.
The weighted *q*-th percentile is the smallest value whose cumulative weight reaches *q* × the total weight — for example, with five equally weighted rows the 25th percentile is the second-smallest value and the median the third.

## Floors

For each metric and each target, over the configured assessment window:

1. Compute the weighted 25th percentile and the weighted median of the **elected** rows, and the weighted median of the **deferred** rows.
   Show them split into the last three years and older, so the maintainer can see whether the bar has moved.
2. **Proposed floor** = the weighted 25th percentile of elected rows × `calibration_relaxation` (default `0.75`), rounded down to an integer.
   The relaxation is deliberate: the floors sit well below what the project has elected, so the lists built on them show more people than the `<governance-body>` would consider, and the decision stays with its members.
3. If the unrelaxed weighted 25th percentile, rounded down, is at or below the weighted median of deferred rows, the metric does **not separate** elected from deferred nominees.
   Propose it as **evidence only**: floor `0`, advisory, shown in briefs but never required.
   Say plainly that it does not separate.
4. A target with fewer than five elected rows gets no proposed floors; say so and leave its thresholds unchanged.
5. A value that was capped is left out of that metric's distribution; with no deferred rows, separation cannot be tested and the note says so.

## Mapping to configuration

| Metric (`contributor-metrics`) | `committer-readiness.md` key | `contributor-nomination-config.md` row |
|---|---|---|
| `prs_merged` | `prs_merged` | PRs merged |
| `reviews_total` | `reviews_total` | Reviews given |
| `reviews_substantive` | `reviews_substantive` | Substantive reviews |
| `issues_filed` | `issues_filed` | Issues filed |
| `issues_triaged` | `issues_triaged` | Issues triaged |
| `threads_commented` | `threads_commented` | Comments |
| `area_breadth` (adjusted) | `area_breadth` | (Required areas by target — count only) |
| dev-list threads + replies | `mailing_list_posts` | Mailing list presence |

## Output

A diff to both files that sets, for each target, the proposed (relaxed) floors (evidence-only metrics at `0` with the note *"evidence only — does not separate elected from deferred"*), `calibrated_on: <today>`, and `calibrated_window_months: <the configured window>`, so the floors are never read against a different window.
The diff contains no name, no handle, no count of nominees, and no description of how the numbers were derived.
