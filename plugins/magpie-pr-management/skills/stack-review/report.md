<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Report and summary comment (Steps 5–6)

## Terminal report

```markdown
## Stack #120 — 4 layers onto `<trunk>` — verdict: <coherent | mergeable bottom-up; merge layers a–b together | needs attention before the bottom merges | not mergeable as a stack>

<headline from `stack-review resolve`>

### Stack findings
- **blocking · chain** — layers 2→3: layer 3 does not contain layer 2's head (`0a1b2c3d`). Cascade rebase needed (`gh stack rebase`, then `gh stack push`).
- **major · ordering** — layers 1–3: layer 1 calls `pathlib.Path.walk()` at its own head while every manifest still declares the older runtime floor until layer 3 (`src/pkg/config.py:12`, `floors.json`). Merge layers 1–3 together or hold releases in between.
- **minor · wrong-layer** — layer 2 → 3: `src/pkg/cli.py:88` collapses a version-marker branch that layer 3's floor bump owns; mechanical spillover, end state unchanged.
- (or) *No stack-level findings.*

### Per-layer notes
#### Layer 1 — https://github.com/<repo>/pull/1001 — read in full [B]
- `src/pkg/loader.py:40` — the docstring still describes the legacy loader this hunk removes.
#### Layer 2 — https://github.com/<repo>/pull/1002 — read by exemplar [C sampled]
- noticed while reading 10 of 24 hunks: `scripts/check_versions.py:17` keeps a comment describing the branch this hunk deletes.

### Coverage
<table from `stack_ledger.py render`, then one sentence per cut>

### Hand-off
Layers that deserve a line-by-line review, highest risk first:
1. `pr-management-code-review pr:1003` — the only layer that changes packaging; 12 files, 108 hand-written lines, 3 outlier hunks.
2. `pr-management-code-review pr:1001` — removes 2 definitions; seams clean, semantics worth a human read.

This is a stack-level review; no layer has been approved by it.
```

Order findings `blocking` → `major` → `minor`; inside a severity, bottom layer first.
Every PR appears with its full URL at least once.
Rank the hand-off by risk: packaging and release changes, then layers removing definitions, then large semantic layers, then mechanical ones; say in one clause why each is where it is.

## Summary comment

Posted on the lowest open layer; the marker is the first line, the footer the last.

```markdown
<!-- magpie-stack-review stack=<S> heads=<heads_digest from chain.json> -->
## Stack review — stack #<S>, <size> layers onto `<trunk>`

**Verdict:** <verdict>. <One sentence naming the deciding finding, or "the chain is linear and current, every layer contains the one below, and no removed definition is used across a layer boundary.">

| Layer | PR | CI | Unresolved threads | Review | Read |
|---|---|---|---|---|---|
| 1 | https://github.com/<repo>/pull/1001 | green | 0 | approved | in full (33 hunks) |
| 2 | https://github.com/<repo>/pull/1002 | cancelled (Tests) | 0 | approved | by exemplar (10 of 24 hunks, 248 of 2,240 lines) |
| … | | | | | |

### Stack findings
<same list as the report, or "None.">

### Noticed while reading
<per-layer notes, each with `file:line` and its tier tag; omit the section when empty>

### Coverage
<coverage table and the one-sentence-per-cut lines>

### Suggested line-by-line reviews
<hand-off list, as `pr-management-code-review pr:<N>` lines>

This is a stack-level review; no layer has been approved by it.
<self-authored note when it applies: "The stack author ran this review; no review event was proposed.">

<AI-attribution footer — the `COMMENT` variant from ../code-review/posting.md, verbatim except that *"the findings below"* reads *"the findings above"*, because in this comment the findings precede it; maintainer-confirmed or role-neutral per Step 0; `<PROJECT>` is `project.md → project_name`>
```

`heads` is the `heads_digest` `stack-review resolve` printed (equal to `chain.json → heads_digest`) (sha256 over `"<k>:<headRefOid>\n"` per layer, first 16 hex); a re-run compares it with the current heads before trusting the old comment.

Posting, re-targeting and the foreign-marker check: `stack-review post`, read through [`classifications/post.md`](classifications/post.md).
The verdict's wording: the verdict document `stack-review verdict` names under [`classifications/`](classifications/).
