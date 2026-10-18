<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# `narrative` — minor, or major

For each layer compare four things: the title and body (what the author says), the commit messages in `chain.json` (what the commits say, bodies included — capped at 4,000 characters each; read them all, they are the cheapest evidence in the run), the ledger's class histogram and directory histogram (what the files say), and the hunks you read.

- A layer titled *"ruff fixes"* whose histogram is 140 `config` files makes a claim its content contradicts — `minor`.
- A body that omits what a commit explains — `minor`; a body that describes a **different layer** than its PR — `major`.
- Stack maps repeated across bodies must list the same titles in the same order; a map listing more PRs than the GitHub stack describes a larger unit — `minor`, naming the PRs outside the stack.
- Two layers' commits contradicting each other on the same fact (one says the change ships in release X, another that X still supports the old behaviour) — `minor`, naming both commits.
- An empty layer is reported by the tool as a `minor` narrative finding already.

`layers` names only the layer whose title or body misdescribes it, not the layer whose commit explains it.
