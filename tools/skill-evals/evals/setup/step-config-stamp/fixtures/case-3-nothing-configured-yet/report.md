<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Install method: `marketplace`, not adopted — no `.apache-magpie.lock`
anywhere in the tree.

This repo has never run `config`, `adopt`, or any override:
  `.apache-magpie-local/`      -> absent
  `.apache-magpie-overrides/`  -> absent

Scope: `config issue-triage` narrowed this run to one skill,
`magpie-issue-triage`, whose `requires_config:` list is empty — it needs
no configuration files at all, so Step 1 found nothing missing and Step
3 wrote nothing.

Today: 2026-09-21
