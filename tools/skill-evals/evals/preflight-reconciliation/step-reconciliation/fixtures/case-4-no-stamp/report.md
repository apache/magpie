<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

This skill is `magpie-issue/triage`.

cat skills/triage/SKILL.md (frontmatter, this skill's own file):
  surface_hash: sha256:2edc90a1b7f3440d

cat .apache-magpie.lock:
  method: marketplace
  url: apache/magpie
  floor:
    magpie-issue: 0.8.0
  (no `reconciled:` block — this project adopted before the stamp
  existed)

cat .apache-magpie-local/reconciled.json:
  (file does not exist)

Result: there is no `reconciled:` block anywhere — neither in the
committed lock nor in a local file — so there is no stamped hash to
compare `magpie-issue/triage` against.
