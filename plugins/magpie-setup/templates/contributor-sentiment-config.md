<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Contributor-sentiment thresholds](#contributor-sentiment-thresholds)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Contributor-sentiment thresholds

> **Personal configuration — keep it in your personal layer, never commit it to `.apache-magpie-overrides/`.**
> Committed, these values become a public checklist contributors can point at to demand a nomination, and every edit to them becomes a negotiation.
> The personal layer is `<git-common-dir>/apache-magpie/` when Magpie is only installed, `.apache-magpie-local/` when the project has adopted it.
> See [Why the configuration is personal](../../../docs/contributor-growth/README.md#why-the-configuration-is-personal).

Signal thresholds for `contributor-sentiment`, which measures whether the
project got healthier to contribute to. Copy this file into your
personal layer and change only the values you disagree with —
**every key below is optional, and the default applies when it is absent or
when the whole file is.**

The skill compares a measurement window against a pre-adoption baseline and
reports each signal as pass or fail. These caps decide where "fail" starts, so
they are a statement about what the project considers a regression, not a
tuning knob for making the report look better.

---

```yaml
contributor_sentiment:

  # Maximum allowed rise, in percentage points, in the fraction of first
  # responses classified as dismissive.
  tone_regression_cap_pp: 5

  # Maximum allowed rise, as a percentage, in median time to first reply.
  reply_increase_cap_pct: 50

  # Maximum allowed drop, in percentage points, in the share of first-time
  # contributors who opened a second PR.
  retention_decline_cap_pp: 10

  # Maximum allowed rise in the Gini coefficient of review load. Rising means
  # review work concentrating on fewer people.
  gini_increase_cap: 0.10

  # Default measurement window, in months, when the invocation names none.
  window_months: 6
```
