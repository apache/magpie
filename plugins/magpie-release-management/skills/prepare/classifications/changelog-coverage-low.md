<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Hand-off — changelog coverage below 90%

**Likely cause:** many merged PRs carry no label the label → section map recognises.

**Remediation:** surface the `uncategorised` PRs (number, title, labels) and ask the RM to classify each before the prep PR opens.
Rerun `prepare changelog` with one `--assign <N>=<section>` per answer; `prep-pr` refuses until `coverage_ok` is `true`.
If the project labels its PRs differently, the lasting fix is `changelog_label_categories` in `release-management-config.md`
(`LABEL=SECTION` entries, sections `Features`, `Bug fixes`, `Documentation`, `Other changes`).
