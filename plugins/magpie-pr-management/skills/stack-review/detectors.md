<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Detectors (Steps 2–3)

Two scripts answer every question that scales with the number of files.
Both are standard library only and live in [`scripts/`](scripts/); their tests in [`tests/`](tests/).

## Fetching the heads

```bash
python3 <skill-dir>/scripts/stack_chain.py fetch-command \
  --repo-url https://github.com/<repo>.git --prefix magpie-stack/<S> --trunk <stack baseRefName> \
  --pr 1=<N1> --pr 2=<N2> …
```

Every other `stack_chain.py` subcommand takes `--repo <clone>` before the subcommand name, so the working directory does not matter.

It prints one `git fetch --no-tags … +refs/pull/<N>/head:refs/magpie-stack/<S>/<k> +refs/heads/<trunk>:refs/magpie-stack/<S>/trunk` line, where the trunk is the stack's `baseRefName` (usually `<default-branch>`, but a stack may be cut from a feature branch).
Propose it; run it on confirmation, from the clone's root.
It writes refs under `refs/magpie-stack/` only — no branch, no checkout, no working-tree change.
`cleanup-command --prefix magpie-stack/<S> --size <size>` prints the matching `git update-ref -d` sequence for Step 7.

Layer diffs are three-dot diffs between adjacent heads, which is what GitHub shows for the layer (`gh pr diff` gives byte-different but ledger-identical input):

```bash
git -C <clone> diff refs/magpie-stack/<S>/trunk...refs/magpie-stack/<S>/1 > 1.diff
git -C <clone> diff refs/magpie-stack/<S>/1...refs/magpie-stack/<S>/2 > 2.diff
```

## `stack_ledger.py ledger`

```bash
python3 <skill-dir>/scripts/stack_ledger.py ledger --layer 1=1.diff --layer 2=2.diff … \
  [--gitattributes <clone>/.gitattributes] [--generated-globs 'docs/**/*.svg,build/*'] \
  [--read-budget 4000] [--full-read-max-lines 1500] > ledger.json
python3 <skill-dir>/scripts/stack_ledger.py render ledger.json          # coverage table, overlap, detectors, per-layer plan
python3 <skill-dir>/scripts/stack_ledger.py hunks ledger.json --layer 2=2.diff   # planned hunks, new-side line numbers
```

`hunks` prints each planned hunk as `### <k>:<path>:<start>-<end> (<tags>)` — the first tag describes the hunk's shape class in its layer (`exemplar`: first of a repeated shape; `outlier`: a shape seen once; `full`: a repeated shape that is not the exemplar), then `overlap` and `off-theme` when they apply; a deleted file shows `:0-0` — followed by its lines, each prefixed with its new-side line number (removed lines carry `-`); notes and findings anchor to those numbers. One invocation per layer.
`--all` prints every hand-written hunk of the layer instead.

`layers` is a list of per-layer objects carrying `position` (1 = bottom); `classes` and `dir_histogram` hold counts; `touched_files` is the union of every file any layer changes.

| Field | Meaning |
|---|---|
| `layers[].changed_lines` / `generated_lines`, `hunks` / `generated_hunks`, `generated_files` | hand-written changed lines and hunks (what sizing, the budget and the coverage table count) versus lines, hunks and files that are generated or binary (counted, never read) |
| `layers[].classes` | file counts per class: `source`, `test`, `docs`, `config`, `generated`, `release-note` |
| `layers[].dir_histogram` / `dir_outliers` | top directories of the layer; files in directories with ≤2 files when three directories hold ≥70% — *off-theme candidates* |
| `layers[].mechanical` | repeated line shapes cover ≥80% of the hand-written changed lines (≥20 lines): a formatter, codemod or sed pass produced the layer |
| `layers[].exemplars` / `outliers` / `outliers_planned` / `outlier_share` | one hunk per repeated hunk shape; every hunk whose shape occurs once in the layer, smallest first; how many outliers the plan reads — all of them in a mechanical layer, in a hand-written layer every one that fits the layer's `outlier_share` (its equal part of the budget the full reads left over), ranked source > config > test > docs then smallest first; Tier A and exemplars never count against the share |
| `layers[].plan` | `full`, `exemplar` or `skip`, with `plan_reason`, `planned_hunks`, `planned_lines` and `planned_hunk_refs` (for `exemplar`: the de-duplicated union of overlap-file hunks, exemplars, planned outliers and off-theme files) |
| `overlap` | file → layers that touch it; all of these are Tier A |
| `detectors.release_note_in_several_layers` | the same newsfragment / changelog path edited in two layers |
| `detectors.generated_in_several_layers` | a generated or lock file regenerated in two layers — regenerate once, in the layer that changes its source |
| `detectors.lock_without_manifest` | a lock file changed in a layer whose manifest changed only elsewhere |

Generated files come from the built-in globs (lock files, minified assets, snapshots, codegen suffixes, `generated/`), `--generated-globs`, and `.gitattributes` `linguist-generated` entries; they are counted, never read, and `render` lists them per layer so the tagging can be checked — a built-in never names a directory a project may use for hand-written code.
When `.gitattributes` and the override file name no pattern, say so once in Step 2 and name the tool output you can see in the diffs (rendered command help, checksums, vendored schema snapshots): it counts as hand-written and inflates its layer until the adopter adds a pattern.
Adopters widen the lists through the override file ([`adopter-config.md`](adopter-config.md)).

## `stack_chain.py chain`

```bash
python3 <skill-dir>/scripts/stack_chain.py --repo <clone> chain --prefix magpie-stack/<S> --size <size> > chain.json
```

| Field | Finding |
|---|---|
| `layers[k].contains_below: false` (k > 1) | `blocking` **chain** — layer k's branch does not contain layer k-1's head: a mid-stack amend without a cascade rebase. The author's fix is `gh stack rebase` + `gh stack push`; quote that as text, never run it. |
| `layers[k].merge_commits > 0` | `blocking` **chain** — a merge commit inside a layer; GitHub requires a linear stack to merge. |
| `layers[k].own_commits == 0` | `minor` **narrative** — an empty layer. |
| `layers[1].contains_below: false` | never happens: the bottom is measured from its merge-base; `behind_trunk_commits` carries the drift. |
| `behind_trunk_commits` | informational: how far the trunk moved since the stack was cut. |
| `trunk_touches_stack_files` | `major` **trunk-drift** when non-empty — the trunk changed files the stack also edits; the next rebase will conflict or compile differently. |
| `layers[k].commit_messages` | `[{sha, headline, body}]`, newest first, bodies capped at 4,000 characters — the input to the narrative check; read them before classifying anything as wrong-layer. |
| `heads_digest` | first 16 hex of sha256 over `"<k>:<headRefOid>\n"` for every layer in position order — the value the summary comment's marker carries. |

## `stack_chain.py seams`

```bash
python3 <skill-dir>/scripts/stack_chain.py --repo <clone> seams --prefix magpie-stack/<S> --size <size> [--layers 3,4] > seams.json
```

For each layer it extracts the definitions the layer removes or renames (column-0 `def` / `class` / `function` / `fn` / `func` / `CONSTANT =` lines, plus deleted modules) and greps each name, whole word, in text files.
Each entry of `layers` carries `position`, `removed_definitions` (a count), `removed_names` (the list, capped at 50) and `hits`: a dict keyed by name, `{}` when nothing was found, each value holding `removed_in`, `at_own_head`, `at_later_heads` (keyed by layer position) and `new_on_trunk` as lists of `path:line:text`:

| Hit location | Finding |
|---|---|
| `at_own_head` | `blocking` **ordering** — the layer removes a definition its own tree still uses; the layer is not green on its own. Verify the quoted lines are real references (not a string or a doc) before posting. |
| `at_later_heads` | a later layer j references a name removed below it. Verify at head j: when the definition is absent there the use was reintroduced after its removal — `blocking` **ordering** for layer j; when j re-adds the definition (or the hit is an unrelated symbol of the same name) it is an observation. |
| `new_on_trunk` | `major` **trunk-drift** — a reference to the removed name appeared on the trunk after the stack was cut; it breaks on the next rebase. Only references absent at the merge-base count; the trunk still holds the old definitions themselves. |

Hits are evidence, not findings by themselves: read the quoted line.
A name that lives on in a docstring, a changelog or an unrelated scope is an observation at most.
Only column-0 definitions and deleted modules are extracted: a method removed from a class is invisible to `seams`, and that is where the Step 4 reading of the layer earns its place.
The run takes a `git grep` per name per head; on a 10-layer, 800-file stack that is under a minute.

## `stack_chain.py floors`

```bash
python3 <skill-dir>/scripts/stack_chain.py --repo <clone> floors --prefix magpie-stack/<S> --size <size> > floors.json
```

Lists, per head, the runtime floor every manifest declares — `requires-python` (in `pyproject.toml` and in PEP 723 `# /// script` headers), `python_requires`, `rust-version`, `go`, `engines.node` — and `floor_changes`: the layers where any floor moves (`moved`, with `from` and `to`), plus `added_manifests` and `removed_manifests` for manifests that appear or disappear (a new module is not a floor move).
A stack that drops a runtime version moves its distribution-manifest floors in one layer, which defines the merge unit; script-header floors (PEP 723) may move in an earlier layer on their own.
Every layer below the manifest move is still released under the old floor; a construct the old floor does not provide, used at that layer's own head, is the inferred `ordering` finding of Step 3 — verify it with `git grep` at the head and quote the line, then name the merge unit (*layers a–b together*).
Grep for constructs the new floor introduced and the old one lacks — for a language-version bump, read the release notes of the versions in between for the list; for a dependency floor, the APIs the stack starts calling.

## Narrative check (Step 3, class `narrative`)

For each layer compare four things: the title and body (what the author says the layer does), `commit_messages` (what the commits say, including the bodies), the ledger's `classes` + `dir_histogram` (what the files say), and the read hunks.
A layer titled *"ruff fixes"* whose histogram has 140 `config` files is making a claim its content contradicts.
A hunk the commit body explains — *"four modules are left out; their fixes land with the removal of the fallback in the next layer"* — is placed on purpose: at most a `minor` *body omits what the commit says*, never `wrong-layer`.
Stack maps repeated across bodies must list the same titles in the same order; a map that lists more PRs than the GitHub stack holds describes a larger unit than the stack and is `minor` narrative (name the PRs outside the stack); a body that describes a different layer than its PR is `major`.
Claims about the same fact must agree across layers — a commit in one layer saying the change ships in release X and a commit in another saying release X still supports the old behaviour is a `minor` narrative finding naming both commits.
Commit bodies are capped at 4,000 characters each in `chain.json`; read them all, they are the cheapest evidence in the run.

## Residue check (Step 3, class `residue`)

Collect the tokens the stack retires from the bodies and commit messages (a version string, a removed option, a deleted module, a renamed flag) and grep them at the top head, case-insensitively, in every spelling the token takes — prose (`<Lang> X.Y`), interpreter or tool (`<tool>X.Y`), image tag (`<image>:X.Y`), identifier (`<lang>XY`), file name (`<name>-X.Y`) — excluding generated output, lock files, dependency manifests and release notes, where the same digits mean something else:

```bash
git -C <clone> grep -n -I -i -E '<token-variants>' refs/magpie-stack/<S>/<size> -- . \
  ':(glob,exclude)**/*.lock' ':(glob,exclude)**/*.svg' ':(glob,exclude)**/generated/**' \
  ':(glob,exclude)**/*.json' ':(glob,exclude)**/*.yaml' ':(glob,exclude)**/*.yml' ':(glob,exclude)**/pyproject.toml' \
  ':(glob,exclude)**/newsfragments/**' ':(glob,exclude)**/CHANGELOG*' ':(glob,exclude)**/changelog.*' ':(glob,exclude)**/RELEASE_NOTES*'
```

`:(glob,exclude)**/X` excludes root-level files too; a plain `:!**/X` does not.
Add the project's own manifest and release-note globs when they differ, and drop hits that are release-version or `__version__` lines.
Report hits in files no layer touches (`ledger.json → touched_files` is the complement) as `minor` *residue* and hits in a touched file as `minor` *partial update*, both prefixed *noticed, not exhaustive* — the token list is the model's guess, not a census.
A bare version token (`X.Y`) matches package versions and must not be used alone; drop hits that are dependency versions, release numbers, deliberately kept historical lists or test fixtures, and say how many were dropped.

## `no-fetch` mode

Without local refs, build each layer's diff with `gh pr diff <N> --repo <repo>` and the file lists with `gh pr diff <N> --name-only`.
The ledger and the narrative check run unchanged (commit messages come from `gh pr view <N> --json commits`); `chain`, `seams`, `floors` and the residue check are skipped and the coverage table says *chain: skipped (no-fetch)*, *seams: skipped (no-fetch)*, *floors: skipped (no-fetch)*.
A `blocking` verdict is still possible from the ledger alone only for `duplicate` findings; ordering and chain problems are *unknown*, and the report says so.
