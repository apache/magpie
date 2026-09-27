<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# security-issue-triage — Security Model and precedents

## Step 2.5 — Apply the Security Model verbatim

For each tracker, before proposing a class, identify the most
directly applicable Security Model section(s) by code-path /
attacker-model / data-flow. Fetch the section verbatim (cache for
the run) from the URL declared in
[`<project-config>/security-model.md`](../../../../<project-config>/security-model.md).
The proposal body **must quote the relevant 2-3 sentences** and
explain how this tracker maps to (or escapes) that wording.

### Trust-boundary cheat-sheet

Apply mechanically before VALID / DEFENSE-IN-DEPTH /
INVALID. The table below is a **worked example** — each row maps
an actor-and-effect pair to a Security Model section the project
considers authoritative. Adopters maintain their own per-project
trust-boundary cheat-sheet at the top of
[`<project-config>/security-model.md`](../../../../<project-config>/security-model.md);
the section names quoted in the *Default class* column are the
literal `§` anchors declared there. The *positive precedent* search
in Step 2.6 reads the precedent-tracker label name from
`tracker.labels.cve_allocated` in
[`<project-config>/project.md`](../../../../<project-config>/project.md).

| If the attacker is… | …and the target / effect is… | Default class |
|---|---|---|
| DAG author | code execution in worker / DAG processor / Triggerer | INVALID (cite §"DAG Authors executing arbitrary code") |
| DAG author | cross-DAG effect within shared parser / triggerer / worker pool | INVALID (cite §"Limiting DAG Author access to subset of Dags") |
| Worker holding Execution JWT | read or write of another task's data via Execution API | INVALID (cite the *"Cross-DAG access via the Task Execution API or Task SDK"* canned: `ti:self` is mutation-only, not per-DAG access control) |
| Authenticated UI / REST user with restricted DAG-scoped perms | reads other DAGs' data via UI / REST | **VALID** (precedent: prior CVEs on this shape — search closed `tracker.labels.cve_allocated` trackers in Step 2.6) |
| Operator / Deployment Manager | misconfigures something with side-effects | INVALID (cite §"Connection configuration users" / operator-trust framing) |
| Authenticated user | DoS or self-XSS | INVALID (cite §"DoS by authenticated users" / §"Self-XSS by authenticated users") |
| External actor (email sender, request poster) | exploit via parser on attacker-controlled input that reaches a supported platform | **VALID** |
| External actor | exploit only manifests on a non-supported platform | INVALID (cite the project's supported-platforms section of the Security Model) |
| DAG author who deliberately routes user input | injection in operator / hook / SQL / shell | INVALID (cite §"DAG Author code passing unsanitized input") |

**If the answer is not in the cheat-sheet, stop and ask the
user** rather than guessing. The classifier flags `UNCERTAIN`
internally per the existing Step 3 contract; the new sub-step is
to ask the user before proposing rather than emitting a
low-confidence proposal.

**Verbatim quote requirement.** The proposal body posted in
Step 4 must include a direct quote (2-3 sentences) from the
matched Security Model section, with the section anchor as a
clickable link. Paraphrases are forbidden — the model wording is
the authoritative grounding for the disposition, and paraphrasing
introduces drift the team will catch in review and bounce the
proposal for.

**Cache the fetched Security Model for the run.** A bulk-mode
sweep over N trackers fetches the model once, not N times.
Subagents in bulk mode receive the fetched copy as a
serialized-string parameter rather than re-fetching.

## Step 2.6 — Search closed-as-invalid / not-CVE-worthy precedents

Step 2's fuzzy-dup search looks for open-tracker duplicates. This
step adds **rejection-precedent search** — same fuzzy keys (GHSA
IDs, code pointers, subject keywords from Step 2a of
[`security-issue-import`](../issue-import/duplicate-search.md#step-2a--search-for-related-potentially-duplicate-existing-trackers)),
but against **closed trackers labelled with the project's closing-
disposition labels** — resolve the literal label names from
`tracker.labels.not_cve_worthy` and the generic closing-disposition
labels (`invalid`, `duplicate`) declared in
[`<project-config>/project.md`](../../../../<project-config>/project.md)
and
[`<project-config>/scope-labels.md`](../../../../<project-config>/scope-labels.md)
(*Closing dispositions* section):

```bash
# Per orthogonal key (code pointer, GHSA, subject keyword) — example
# labels only; substitute from the adopter's
# tracker.labels and scope-labels.md closing dispositions:
gh search issues "<key>" --repo <tracker> --state closed \
  --label "invalid" --json number,title,closedAt --jq '.[]'
gh search issues "<key>" --repo <tracker> --state closed \
  --label "not CVE worthy" --json number,title,closedAt --jq '.[]'
```

Each hit is a **rejection precedent** — surface in the Step 4
proposal body with a one-line shape summary so the team sees the
prior call without scrolling the closed list. A STRONG
precedent (same code surface + same vulnerability class) lowers
the proposal's confidence and may swing the disposition from
VALID → INVALID. Include the citation in the proposal:

> Direct precedent: [`<tracker>#NNN`](https://github.com/<tracker>/issues/NNN)
> (closed YYYY-MM-DD as INVALID, same shape: <one-line>).

Also search for **positive precedents** — CVE-allocated trackers
with similar shape — via (substitute the literal label from
`tracker.labels.cve_allocated` in
[`<project-config>/project.md`](../../../../<project-config>/project.md)):

```bash
# `gh search` has no `--state all` (that is `gh issue list`); omitting
# the flag searches open and closed alike.
gh search issues "<key>" --repo <tracker> \
  --label "cve allocated" --json number,title,labels --jq '.[]'
```

A positive precedent on the same shape supports VALID. A
positive precedent in one trust-boundary (UI/REST per-DAG
bypass) and a negative precedent in another trust-boundary
(Execution-API-via-worker-JWT) for the same code surface is the
signal that the trust-boundary analysis in Step 2.5 is the
load-bearing dimension, not the surface itself.

**Budget**: ≤ 3 additional `gh search issues` calls per tracker
on top of Step 2a's existing 5-call budget. If Step 2a already
spent its budget on STRONG dedup matches, Step 2.6 can skip the
search for that orthogonal key (the dedup STRONG match
supersedes; the proposal routes to
[`security-issue-deduplicate`](../issue-deduplicate/SKILL.md)
instead).

**Hard rule**: a rejection precedent in Step 2.6 does **not**
auto-classify INVALID — the human team reads the precedent
and the new report side-by-side. The skill's job is to surface
the precedent, not to vote for it.
