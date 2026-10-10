<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# `chain` — blocking

[`stack-review findings`](../../../../../tools/pr-management/README.md) reports it from `stack_chain.py chain`: a layer above the bottom that does not contain the head below it (a mid-stack amend without a cascade rebase), or a merge commit inside a layer (GitHub requires a linear stack to merge).

Deterministic evidence: it stands as written. The author's fix is `gh stack rebase` then `gh stack push`; quote it as text, never run it.
An empty layer (`own_commits == 0`) comes back as a `minor` narrative finding instead.
