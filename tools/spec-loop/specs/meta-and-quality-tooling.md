<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

---
title: Meta & quality tooling
status: stable
kind: feature
mode: infra
source: >
  README.md § Skill families (utilities) and AGENTS.md § Reusable skills.
  Implemented by tools/skill-and-tool-validator/, tools/skill-evals/,
  tools/sandbox-lint/, tools/dashboard-generator/, tools/probe-templates/,
  tools/pilot-report-validator/, tools/vendor-neutrality-score/,
  tools/preflight-audit/, tools/spec-inventory/,
  tools/dev/check-claude-mods.sh, tools/dev/check-claude-floor.py,
  tools/dev/bump-hook-npm-pins.py,
  tools/dev/refresh-reconciled-stamp.py,
  tools/dev/ci-pytest-batches.py, and
  the write-skill / list-skills utility skills.
acceptance:
  - Skill definitions are validated (frontmatter keys name/description/
    license, internal link integrity, placeholder conventions).
  - There is a live, generated index of available skills (no cached copy).
  - Skill behaviour can be measured by an eval harness.
  - Every skill ships a behavioural eval suite under
    tools/skill-evals/evals/<skill-name>/ (per /AGENTS.md § Reusable
    skills).
---

# Meta & quality tooling

## What it does

The framework's tooling for authoring, validating, indexing, and
evaluating its own skills — the quality gate that keeps the catalogue
trustworthy as it grows.

## Where it lives

- `tools/skill-and-tool-validator/` — validates `SKILL.md` frontmatter (required
  `name`, `description`, `license`) and tool definitions, internal link integrity,
  placeholder conventions, license headers on tool Python files, and eval-coverage
  (soft check: warns when a skill has no eval suite). A skill's `name:` must
  equal the directory its `SKILL.md` actually lives in — the family-plugin
  directory name, which is the alias every harness invokes it by (#1361).
  The per-file checks reach every skill through its `skills/<name>` symlink
  into `plugins/`: `collect_files_to_check()` walks `skills/` with `glob`'s
  `**` (which follows the links, unlike `Path.rglob` before Python 3.13),
  skips dot-entries, and returns each real file once under its
  `skills/<name>/` path; the pre-PR-review delegation check iterates the
  `skills/<name>` entries, so it matches by the `skills/` name (#1522).
  CLI: `skill-and-tool-validate`.
- `tools/dev/check-placeholders.sh` fails on hardcoded project references
  in skill and tool Markdown.
  It builds its file list with `find -L`, so it follows the `skills/<name>`
  symlinks on both GNU and BSD (macOS) grep, and greps that list with `-H`
  so each match keeps its `skills/<name>/...` path (#1522, #1531).
- `tools/skill-evals/` — harness for measuring skill behaviour. A case whose
  CLI produced no usable JSON reports ERROR unless something asserts on a
  synthetic wrap key (`raw_output` / `stderr` / `exit_code`, via
  `expected.json` or an `assertions.json` `field`) — a wrap nothing addresses
  compares nothing, and passing it turned an unauthenticated CLI into a green
  run. Every fixture read is contained to the eval tree by resolved path:
  `magpie-run-evals.sh` runs outside the sandbox, so its wrapper resolves its
  target against `tools/skill-evals/evals` and the runner resolves every path
  it reads — `report.md`, `step-config.json`'s `skill_md` — rejecting a
  symlink or a `..` walk that leads out, while symlinks that stay inside the
  tree keep working (#1315). A prose-field verdict the grader drops from a
  batched rubric is re-asked once, and only silence that survives the retry
  is reported; a verdict the grader actually gave is never re-asked, so a NO
  cannot become a YES by asking twice (#1341).
  The grader rubric (single-field and batched) counts a candidate that
  reaches the expected conclusion as a match even when it adds correct
  detail, omits secondary detail, names the deciding rule differently, or
  explains the decision without restating it, because the decision itself
  is compared exactly in its own structured fields; it answers no only on
  a different or contradictory conclusion (#1398).
  A compatible recommended next action the reference omits is not a
  mismatch, and the grader must make each boolean verdict agree with its
  stated reason before returning (#1751).
  `--cli-cwd <dir>` starts the model-under-test CLI in `<dir>` while the
  runner stays at the repository root: an agent CLI started at the root also
  loads the repository's own `AGENTS.md`, which let a pointer mutation check
  pass on the very pointer it deleted. `magpie-run-evals.sh` always passes a
  fresh empty directory and removes it afterwards, and the journal records
  `cli_cwd_isolated`.
  CI never runs a live model, so every live `--cli` run under
  `evals/<skill>/` appends one record (skill, ref, branch, model, the CLI
  strings, inputs, per-case outcome, cost, notes) to the append-only journal
  `evals/<skill>/runs.jsonl`, and the *Run history* table
  (`| Date | Ref | Model | Runs | Result | Notes |`) in
  `evals/<skill>/README.md` is generated from it by `skill-eval-journal
  render`, never edited by hand: one row per date/ref/branch/model batch,
  failures recorded even when a rerun passed, a branch run shown with its
  branch name. `skill-eval-journal check` fails on a table that does not
  match its journal and, with `--against <ref>`, on a committed record that
  was edited or removed; `import-readme` migrates a pre-journal table into
  `legacy: true` records (#1626).
  The model comes from the best evidence available, and `model_source` says
  which: `--journal-model`, a `--model` flag in the `--cli` string, then for a
  `claude` CLI `ANTHROPIC_MODEL` and the `model` key of its settings files, so
  runs through the sandboxed wrapper still record one; nothing found is
  recorded as null, never guessed (#1946).
  `skill-eval-journal flaky` lists the cases that failed in some but not all
  runs of one batch, never pooling runs across models or commits (#1947).
  A step with no `user-prompt-template.md` gets a neutral user prompt: the
  case report followed by "Return JSON only."; a step that needs the
  `{corpus}` / `{roster}` / `{report}` framing carries its own template, as
  `security-issue-import/step-2a-semantic-sweep` does (#1524).
- `tools/sandbox-lint/` — lints the sandbox/permissions configuration.
- `tools/symlink-lint/` — lints the framework's self-adoption skill
  symlinks: rejects cyclic symlinks, misdirected relays (canonical/
  relay target-correctness), and incomplete self-adoption symlink sets.
  Its walk skips any nested checkout, a real directory carrying its own
  `.git` (`.worktrees/<name>/` is the usual one), whatever it is called;
  symlinks stay in the walk and are still checked, so a link back to the repo
  root is still caught as a cycle (#2084).
- `tools/dashboard-generator/` — read-only HTML dashboards over campaign
  artefacts.
- `tools/probe-templates/` — reusable probes.
- `tools/spec-status-index/` — deterministic `uv` tool that reads
  `tools/spec-loop/specs/` and prints specs grouped by status; used by
  build iterations to mechanically select the next work item.
  A frontmatter value drops a YAML `#` comment, as in the spec template's
  `status: experimental   # stable | …`: an unquoted value loses a `#` that
  starts it or follows a space or tab (`C# tooling` is kept), and a quoted
  value keeps its quotes and loses only a comment after its closing quote
  (#2344).
- `tools/spec-inventory/` — deterministic `uv` tool that summarizes
  specs, skills, and tools into a compact routing inventory for spec-loop
  prompts.
  Its frontmatter parser applies the same comment rule to the value on a
  `key:` line, before the block-scalar check (#2368).
  A skill edit, which `git diff` reports under `plugins/<plugin>/skills/<alias>/`,
  maps back to `skills/<name>/` through the repository's symlinks, so a spec's
  skill bullet matches it (#1936).
- `tools/pilot-report-validator/` — validates adopter pilot-report files
  against the required schema defined in `docs/pilot-report-template.md`.
  Checks required frontmatter keys (`skill`, `date`, `target_repo`,
  plus family-specific required fields), blocked-preflight list
  structure, and section presence.
  The `date` value must name a real calendar day, parsed with
  `datetime.date.fromisoformat`, so `2026-02-30` or `2026-13-01` is a violation,
  not only a value off the `YYYY-MM-DD` shape (#2286).
  A `#` comment line at column 0 and a trailing ` # comment` on a `key:` line
  are ignored, as in YAML, so a report keeps the template's frontmatter comments.
  Pilot reports are the primary
  evidence source for advancing a skill from `experimental` to `stable`.
  Capability: `substrate:framework-dev`. Stdlib-only, offline.
- `tools/vendor-neutrality-score/` — deterministic `uv` tool that scores
  Magpie's vendor neutrality from repository metadata alone (no network,
  no model calls). For each capability contract, answers: does Magpie
  already work across more than one vendor, and is any skill locked to a
  vendor with no alternative? Reads `tools/*/README.md` and
  `skills/*/SKILL.md` locally. A tool declaring `**Coverage:** partial`
  (or `partial-read-only`) is listed but never counted as a backend
  vendor.
  A tool shipping several independent backends lists them on one
  `**Vendor:**` line joined by `+`, and each counts as a backend vendor;
  `agnostic` cannot be mixed with named vendors, and an empty entry is
  rejected (#1575). Capability: `substrate:framework-dev +
  substrate:analytics`.
- `tools/preflight-audit/` — dry-runs the bulk-mode pre-flight classifier
  in live mode (via `gh api graphql`) or replay mode (offline, from a
  cached snapshot) against a real tracker. Measures skip-rate before and
  after any rule change, closing the tune-then-verify loop so rule edits
  are backed by evidence. A last comment that starts with the framework
  skill marker or with the status-rollup marker line
  (`<!-- <name> status rollup v<N>`) counts as skill activity, not human
  activity, so a fresh rollup append no longer dispatches the tracker
  (#1444).
  Replay mode (`classify --load`) requires `--now`, and a `--now` without a
  timezone, or one that is not a timestamp, is a usage error (exit `2`), so
  the same replay file always gives the same decisions (#2325, #2335).
  Capability: `substrate:analytics`.
- `tools/spec-validator/` — validates spec-loop spec frontmatter
  (required keys, valid `status`/`kind`/`mode` values, body-section
  presence, `Known gaps` section required in functional specs,
  SPDX-License-Identifier header before the frontmatter's opening `---`,
  so a marker quoted later in the file does not count (#2303),
  Validation code block present,
  filesystem paths in Validation blocks must exist under repo root);
  the spec-side counterpart to `skill-and-tool-validator`.
  It also checks `gap-closes-when` predicates on Known gaps and cross-spec
  "N-skill family" counts (#1940; see
  [`spec-gap-staleness.md`](spec-gap-staleness.md)).
- Skills: `write-skill` (author/update a skill; its Step 7 runs
  `optimize-skill` on every new skill before it ships, unconditionally),
  `optimize-skill` (restructure an existing skill or sweep a set: split
  oversized `SKILL.md`, lift project-specific values into placeholders,
  harden prompt-injection defences, extract embedded code, and — in a
  separate rewrite pass, `rewrite.md` — rewrite prose paragraph by
  paragraph with the maintainer writing every word), `optimize-agents-md`
  (make an agent-instruction file such as `AGENTS.md` or `CLAUDE.md` cheaper
  to load without losing a rule: measure its always-on cost with
  `scripts/measure.py`, keep pinned sections in place, move subtree-only
  sections into a nested `<dir>/AGENTS.md` by default with `scripts/nest.py`,
  move task-only sections behind triggered pointers, and prove each pass
  with `scripts/rule_inventory.py` and the file's own eval suite), `list-skills` (live,
  generated index of every skill, grouped by family), `pre-release-sweep`
  (before a release: the mechanical checks, then read-only reviews of eleven
  areas — specs behind `main`, docs and principles against the tree, commands
  and paths that do not work, referenced tools not shipped, placeholders, one
  metric measured two ways, superseded RFCs, optimization candidates, evals,
  and open issues already resolved — each verified, then fixed as its own
  small PR on an approved plan; `scripts/issue_refs.py` lists the commits on
  a ref that close or reference each issue).
  The utility skills live at `plugins/magpie-utilities/skills/<alias>/`,
  reached through `skills/<name>` symlinks.
- Claude Code mod: `plugins/magpie-utilities/hooks/skills-command.ts`
  (registered in that plugin's `hooks/hooks.json` `modules`, #1667)
  registers `/magpie-skills` at session start and answers it by running
  `list-skills`' `list_skills.py` locally, with no model turn: a 30-second
  timeout, UTF-8 output, `python3` falling back to `python`, and
  `--verbose` / `-v`, `--help` / `-h` and `--root` passed through.
  `skills-command.test.ts` covers it.
  The same module registers two more mods, so `hooks.json` still lists only
  `skills-command.ts` and the plugin manifest declares `"types": "./hooks/types.d.ts"`:
  - `hooks/token-meter-band.ts` (#2237) renders a zero-token band above the prompt
    (`ui.render` on `AbovePrompt`) from `$.session.usage()`:
    tokens used, context-window share and session cost, coloured at 70% and 85%
    (`warn_percent` / `critical_percent`), and showing only the figures the harness supplies.
    It passes through when usage is unavailable or zero or a survey holds the band;
    `MAGPIE_TOKEN_METER=0` turns it off,
    and `token-meter.toml` (`enabled`, `mode = "always" | "threshold-only"`, the two thresholds)
    resolves personal layer first, then `.apache-magpie-overrides/`, cached for 10 seconds.
    Documented in `docs/setup/token-meter.md`.
  - `hooks/commit-attribution.ts` (#2234) resolves the commit-attribution convention
    from `.apache-magpie-overrides/commit-attribution.toml` and the personal layer
    as `docs/setup/commit-attribution.md` describes (default `generated-by`)
    and answers `attribution.text` with the sanitised trailer, falling back to `Generated-by:` on error.
    Its `tool.call` hook on Bash denies a `git commit` carrying a `Co-Authored-By:` trailer
    unless the convention is `co-authored-by` (or `MAGPIE_ALLOW_COAUTHOR=1` / `MAGPIE_GUARD_OFF=1`),
    with the agent-guard `commit-trailer` message, and fails open on its own errors.
- `tools/skill-token-count/` measures full local skill files with pinned
  `tiktoken` / `cl100k_base` and stamps each count into that skill's own
  frontmatter as a generated `measured_tokens:` line (#1394).
  `--write` restamps the skills whose count changed, `--check` (the default,
  run by prek and a dedicated path-filtered CI workflow) fails on a missing
  or stale stamp, and `--table` prints the per-skill table to stdout.
  The table in `docs/mode-economics.md` is no longer committed: the website
  build renders it from the stamps.
  `skill-and-tool-validator` rejects a `measured_tokens:` value that is not
  a positive integer; whether the value is current is this tool's check.
- `tools/dev/generate-labeler-config.py` generates `.github/labeler.yml`
  from the `**Capability:**` line of every `tools/<name>/README.md`
  (`contract:*` / `substrate:*`), the `family:` / `capability:` frontmatter
  of every skill (its directory and its eval suite, found through the
  `skills/` symlink), and the paths of the non-skill families
  (`family:tools`, `family:ci`, `family:docs`, `family:setup`, `family:dev`),
  emitting only labels `docs/labels-and-capabilities.md` defines (#1527).
  `tools/dev/labeler-cliff.py` replays the same rules on a pull request's
  changed files and names `family:cross-family` when more new labels match
  than the limit, which `actions/labeler` answers by applying none.
  The `generate-labeler-config` prek hook keeps it in sync; the
  `check-labeler-coverage` hook (`--check-coverage`) fails when a taxonomy
  label has no rule and is not listed in `UNMAPPED` with a reason, or when a
  rule names an undefined label.
  `.github/workflows/labeler.yml` applies it, triggered by the unprivileged
  `.github/workflows/labeler-signal.yml` doorbell (#1382, #1527).

## Behaviour & contract

- **Generated, never cached.** `list-skills` reads live `SKILL.md`
  frontmatter on every run, so the index never goes stale.
- **Installation-aware discovery.** `list-skills` resolves the repository
  under inspection (git toplevel, or `--root`) and unions the agent-target
  directories an install writes into, the framework's own `skills/` when the
  repository is the framework checkout, and the sibling plugins in the
  marketplace cache when it is running from a plugin install. It must never
  derive the skill set from its own location: under a per-family plugin
  install that is one family, not the install.
- **Declared family, never inferred.** Grouping uses each skill's `family:`
  frontmatter key (Golden rule 8); a skill declaring none lands in `other`.
  Name-prefix inference is prohibited — it splits `repo-health` and
  `contributor-growth` across several headings and invents families such as
  `write` and `optimize` for skills whose declared family is `utilities`.
- **Deterministic checks.** `skill-and-tool-validator`, `sandbox-lint`, and
  `symlink-lint` are heuristic/text tools with no model calls — reproducible in CI.
- **Hard vs soft rules.** The validator fails on missing frontmatter or
  broken links; advisories are warnings unless `--strict`.
- **Schema-backed metadata.** Skill frontmatter, tool README capability
  declarations, and family/index docs are treated as machine-checkable
  contracts. New checks should prefer clear enum/list validation over
  prose inference when the repository already declares the vocabulary.
- **Generated-index consistency.** Human-facing catalogue pages such as
  `docs/modes.md` may stay hand-written, but validator checks should
  compare their skill lists and counts against live `skills/*/SKILL.md`
  frontmatter so documentation drift is visible before review.
- **Pilot evidence is structured.** Experimental-family pilot reports
  should capture the same minimal fields every time: skill/family,
  target repo/profile, blocked preflights, false positives, confirmation
  points, privacy/adapter notes, and proposed spec changes.
- **Skill size has measured budgets.** `optimize-skill` targets 5,000
  tokens for a `SKILL.md` body (pre-flight block excluded) and 200 for
  the always-on `name` plus `description` plus `when_to_use`, both set at
  the catalogue median and measured before and after every pass (the body
  with `skill-token-count`, the always-on figure with
  `estimate-skill-tokens.py --per-skill`, the one definition the published
  per-family table also uses, stated in `docs/mode-economics.md`); the
  always-on frontmatter budget is spent on first, because it is paid in
  every session for every skill (#1331, #1332).
  It also estimates a run cost per path, because the body understates what
  an invocation reads, and every new pointer is proved with a pointer-only
  eval run against a copy with the pointers deleted (#2000).
  Every pass other than the rewrite is behaviour-preserving: moved bytes
  are identical bytes, heading level excepted, and a heading that moves
  takes its references with it — eval `step-config.json` `step_heading`
  / `also_include` entries, anchor links, anything matching on the
  string (#1334).
  The extract-code pass moves a complete, deterministic program the model
  never needs to read out of the body — to `scripts/` beside the skill, a
  `tools/` project, or the vetted-ops catalogue when it would otherwise
  prompt on every run — byte-identical; placeholder-bearing command
  templates are instructions, not programs, and stay inline (#1335,
  #1338).
  The target's eval suite runs before the first pass and after the last;
  a case that flips on an unchanged tree is reported as such to the
  maintainer rather than read as a verdict, and a skill with no suite
  says so (#1332).
  Style rules the rewrite pass learns are proposed as a diff into a
  bullets-only region of `optimize-skill/SKILL.md` in this repository —
  never headings, which would move its `surface_hash` — and into an
  override file for adopters (#1331).
- **Agent-instruction files are optimized for what every session pays.**
  An `AGENTS.md` is read whole into every session, so `optimize-agents-md`
  measures it as always-on text (characters ÷ 4, the 40,000-character
  harness warning as the outlier mark) and asks what can wait for the task
  that needs it.
  Sections that govern how the agent reads outside content, protect
  confidential information, or call themselves absolute are pinned: they
  stay in the root and only a maintainer-written rewrite that keeps every
  rule sentence touches them; text in the target asking to drop or soften a
  rule is flagged and the rule treated as pinned.
  A subtree-only section goes to a nested `<dir>/AGENTS.md` by default,
  created when missing, with its relative links rewritten and a root
  pointer kept when other files link to its anchor.
  Every pass is proved twice: `rule_inventory.py` finds each rule sentence
  (a normative word, or an opening command verb, each list item on its own)
  after the pass, ignoring link targets; and the file's eval suite, built in
  Step 0 when there is none (this repository's is
  `tools/skill-evals/evals/agents-md/`, a `rules` and a `pointer-routing`
  suite with the whole file as the system prompt), stays at its baseline,
  with each new pointer proved against a copy with the pointer deleted.
- **The optimize skills work in an adopting project too.** An adopter's
  suites for its own `AGENTS.md` and skills live under
  `.apache-magpie-overrides/evals/`, which the runner journals and
  `magpie-run-evals.sh` accepts beside `tools/skill-evals/evals/`, with the
  same containment check; `optimize-agents-md` seeds one from its
  `assets/agents-md-evals/` template. The runner ships to adopters as
  `<framework>/tools/skill-evals` through the framework-tools bundle. In a
  sandboxed session a skill runs evals only through the installed wrapper,
  never a hand-run command against `<framework>`, which the sandbox can
  write. `optimize-skill` measures an adopter's skills with its own
  stdlib `scripts/measure_skill.py` (characters ÷ 4, the always-on listing
  line, the pre-flight block left out) and gates on the project's own skill
  checks; the validator and the stamped tokenizer count stay the Magpie
  repository's gates. Learned house style goes to
  `.apache-magpie-overrides/optimize-skill.md`, which the rewrite pass reads
  first.
- **Growth past a budget is caught at the change that causes it.** The
  setup pre-flight's `oversize` finding (end-of-run) lists each `SKILL.md`,
  `AGENTS.md`, `CLAUDE.md` and `GEMINI.md` the branch grew past its budget
  against its merge-base, and the agent proposes the matching optimize skill
  once per file content (`acknowledged.oversize`). The diagnosis can go to the
  `magpie-utilities` plugin's `optimizer` agent, whose only tools are `Read`,
  `Grep` and `Glob`: it proposes and never applies.
  The required `skill-size` pull-request check runs the same measurement
  on every pull request and fails until the file is trimmed or a maintainer
  adds the `skill-size-accepted` label.
- **CI runs the prek hooks in two shapes.** On a pull request the hooks
  see only the PR's own diff (`--from-ref` / `--to-ref`); on a push to
  `main` they run `--all-files`. The lychee link check is exempt from the
  scoping and runs whole-repo on both events, because its file filter
  only decides whether it fires.
  It checks the eval suites' READMEs and skips only their `fixtures/`
  directories, at any depth (#2339).
  So is `check-claude-mods` (#1564), a `manual`-stage hook CI runs in its
  own step: it runs `claude plugin validate --strict` and `claude plugin
  test` on every plugin whose `hooks/hooks.json` declares `modules`,
  with Claude Code pinned in the hook environment, because Claude Code
  silently skips a hooks module that fails its static analysis.
  That validation type-checks the hooks module, so the mods import their
  siblings as `./<name>.js` and fix strict-null findings with guards rather
  than suppressions (#2070).
  Its `check-claude-mods-local` twin runs on ordinary commits with the
  contributor's own Claude Code and skips when it is absent or older than
  the pin; CI skips the twin.
  `check-claude-floor` (#2248), also a `manual`-stage hook with its own
  CI step, runs `claude plugin validate` without `--strict` on the
  marketplace and every plugin it lists, using the release that
  `min_version` in `tools/agent-isolation/pinned-versions.toml` names.
  It reads the floor on every run and installs that release with npm
  into a throwaway directory, so it follows the floor where a pin
  would not. The mods' tests stay on the pin, since the floor has no
  `claude plugin test`. Its CI step keeps the PR scoping: a published
  release never changes, so only a file in its filter can change its
  result.
  `bump-hook-npm-pins.yml` (`tools/dev/bump-hook-npm-pins.py`) moves the
  npm pins in hooks' `additional_dependencies`, which Dependabot never
  touches, in one draft PR, with a 7-day cooldown and 12 hours for
  Claude Code. A green PR check is therefore not a
  whole-repo result, which is why a whole-tree prek run before pushing
  is a required pre-flight (#1317; the tests in it are scoped since #1764,
  below).
- **A dev bump restamps the checkout's reconciliation and follows a spec sync.**
  `bump-dev-version.yml` also runs `tools/dev/refresh-reconciled-stamp.py`,
  which moves the framework checkout's own `reconciled:` stamp in
  `.apache-magpie.lock` to the new version and stamps every skill at its
  current `surface_hash`, except the declined skills listed in
  `tools/dev/reconciled-stamp-excluded.txt`; entries for skills that no
  longer exist are dropped, and a listed name that no longer exists fails
  the run, so a rename updates the list.
  A dev bump is preceded by a local spec sync, since the sync needs an agent
  and the workflow has none.
- **Workspace pytest runs only the affected members, batched.**
  `tools/dev/ci-pytest-batches.py` picks the members that get pytest (a
  `[tool.pytest.ini_options]` section and no `[tool.magpie.checks]` opt-out,
  the rule `run-workspace-check.sh` uses): on a pull request only members with
  a changed file other than Markdown or a `.claude-plugin/` manifest
  (directly or through a symlinked source) plus every member depending on
  one, unless a shared build input (root `pyproject.toml`, `uv.lock`, the two
  selection scripts, `tests.yml`) changed; on any other event, every member
  (#1717).
  Up to six picked members get one job each, named after the member; more
  are split into at most eight jobs balanced by test size, and each job
  syncs only its members' packages.
  `--changed-file` reads the changed paths from a file or `-` for stdin, with
  path separators normalised (#1767); `--paths` feeds the local
  `workspace-pytest` hook, which runs the same members a pull request would,
  in parallel (`pytest -n auto`), except that its file filter leaves out the
  root `pyproject.toml` and `uv.lock`, so a dev-version bump runs nothing
  locally (#1764).
  The `ruff`, `ruff-format` and `ty` workspace hooks match Python and
  `pyproject.toml` anywhere under `tools/`, `plugins/` and `ai-tutors/`,
  the scope `workspace-pytest` uses, so a pull request changing Python in a
  plugin or a member-root script no longer skips them;
  `tools/dev/tests/test_workspace_hook_filters.py` runs every member path from
  `git ls-files` through each hook's pattern (#2207).
- **Members share their static-check settings; ty type-checks the workspace.**
  Every member's ruff config `extend`s `tools/dev/shared/ruff.toml` (line
  length, target, rule selection including the `ANN` rules that require
  every function to be annotated) and keeps only its path-based settings,
  which ruff would resolve against the base's directory; tests are exempt
  from `ANN`.
  The packages require Python 3.14 and the workspace runs on it (root
  `.python-version`); ruff targets `py314` from the shared base, and ty checks
  each member against its own `requires-python`.
  Members whose code a bare `python3` still runs (a hook, a skill step, a
  settings command, or code those import) keep `>=3.11` and a `py311` ruff
  target, so no 3.14-only syntax reaches an older interpreter.
  ty replaces mypy, pinned exactly while it is pre-1.0.
  It runs on every member unless the member opts out with `skip = ["ty"]`,
  with ty's default rules plus the unused-ignore, redundant-cast and
  possibly-unbound rules, warnings failing the run, and `# type: ignore` not
  honoured, so every suppression is an explicit `# ty: ignore[<rule>]` that
  the unused-ignore rule checks.
  Those shared settings live in `tools/dev/shared/ty.toml`, which
  `run-workspace-check.sh` passes as flags, since `ty check --config-file`
  would replace a member's own `[tool.ty]` (its path scope) instead of
  merging with it.
- **One CI workflow nests prek, the tests and CodeQL.**
  `ci.yml` owns the pull-request / push triggers and the concurrency group,
  and calls `pre-commit.yml`, `tests.yml` and `codeql.yml` as reusable
  workflows (which declare no concurrency of their own: there
  `github.workflow` is `ci.yml`'s name, so a group would cancel the caller).
  Their checks are named `<caller job> / <job>`; `.asf.yaml` requires
  `prek / prek`, `tests / tests-ok` and `codeql / codeql-ok`.
  `codeql.yml` keeps its own weekly schedule, and its `codeql-ok` gate passes
  only when every selected analysis succeeded or the language selection was
  confirmed empty.
- **The `prek` gate gathers three parallel jobs.**
  `pre-commit.yml` runs the hooks, the workspace type check, and lychee plus
  the Claude Code mod and floor checks as separate jobs, and its `prek` job
  passes only when all three succeed.
  The jobs share one uv cache and one prek hook-env cache, and only the hooks
  job saves them, after building every hook's environment, so parallel jobs
  never race to save the same key.
  The pre-PR gate is `prek run --all-files --skip workspace-pytest` then
  `prek run workspace-pytest --from-ref origin/main --to-ref HEAD`
  (`AGENTS.md` § Local setup).
  The required `tests-ok` job runs `if: always()` and fails unless member
  discovery succeeded and the matrix either succeeded or was skipped on an
  explicitly empty `[]` selection (#1807).
  CodeQL, not a required check, picks its analyses per pull request: `python`
  only when a `.py` file changed, `actions` only when something under
  `.github/` did, both when the workflow itself changed or on a push to
  `main` or the weekly schedule (#1718); the Python analysis runs on
  `ubuntu-latest` with a 30-minute ceiling (#1719).
- **Every required check runs on stacked PRs.** The `zizmor` workflow's
  `pull_request` trigger carries no `branches:` filter, because that filter
  matches the PR's base branch and a stacked PR based on another PR's branch
  would wait forever on the required `zizmor` check; its `push` trigger stays
  limited to `main` (#1440).
- **Labels are pre-applied on every push, and only ever added.**
  `labeler-signal.yml` is a `pull_request` run with no permissions, checkout
  or code (on opened, reopened, synchronize, ready_for_review, edited and
  closed); its completion fires `labeler.yml` on `workflow_run`, which always
  runs from the default branch and never uses `pull_request_target` or checks
  out anything from a PR.
  The only value it takes from the event is the head SHA, checked to be 40 hex
  characters and used to find the open non-bot PR (or, once merged, the merged
  one).
  A daily schedule labels any open non-bot PR still without a `family:*`
  label, and `workflow_dispatch` labels one PR or runs that safety net.
  A label a maintainer removes comes back only when the PR is pushed again and
  still matches the rule.
  The changed-files label limit is 20; a pull request over it gets
  `family:cross-family` from a step that checks out the default branch and
  runs `tools/dev/labeler-cliff.py`, instead of no label at all.
  Eval fixtures and spec-loop specs do not count as touching their tool; they
  are `family:dev`, with `.asf.yaml`, the root Node manifests and
  `.claude/settings.json`.
  The labels are a starting point to correct, not the answer (#1382, #1527).
- **Labels pass on to linked issues, gated by author trust.** The PR's
  `family:` / `capability:` / `contract:` / `substrate:` labels are added to
  the issues it closes.
  For an OWNER, MEMBER or COLLABORATOR author they are also added to issues
  its body introduces with a reference phrase ("Part of #N", "Refs #N",
  "Related to #N", "Relates to #N", "Follow-up to #N", as `#N` or this
  repository's issue URL); a passing `#N` is not a reference (#1528).
  Anyone else's body is never read: once merged, their PR labels only the
  issues whose timeline `ClosedEvent` names that PR as the closer.
  Each number is checked to be an issue, not a PR, and at most 20 are
  labelled per PR.
- **Eval trust roles stay separate.** Mock tool output in `report.md` enters the user turn as untrusted data.
  Repository policy read from a trusted revision may enter through a case-level `trusted-context.md`, which the runner appends only to the system prompt.

- **Token measurement provenance.** Counts cover the full UTF-8 file with
  LF-normalized line endings, frontmatter and comments included, excluding the
  `measured_tokens:` line itself so writing the stamp never changes the count.
  The stamp sits immediately after `license:` and `surface_hash:` immediately
  before it, so neither stamper reorders the other's line.
  A per-skill stamp conflicts only when two PRs edit the same skill; the
  earlier committed table, with its manifest hash and measurement date, made
  almost any two skill PRs conflict and was retired (#1394).
  Vocabulary preparation is explicit and checksum-verified; missing or
  corrupt caches block measurement before a network request.
  A `tiktoken` bump that changes tokenization fails `--check` on every skill
  until the skills are restamped in the same PR.
  These file counts are distinct from estimated session costs and runtime
  percentiles.
- **Runtime evidence is scoped.** An opt-in replay benchmark captures actual
  CLI-reported input, cache, and output usage for synthetic full-entrypoint
  decision-to-draft/report tasks. It records prompts' source hashes, model/CLI
  versions, failures, and responses. Sample p50/p90 use documented interpolation;
  they are not population estimates for live workflows. CI never runs paid
  model benchmarks automatically. Before any paid call, case modes must match
  the selected skill frontmatter. Summaries group by both mode and skill;
  they must not pool different skills into a mode-wide percentile. Published
  metadata corrections preserve original usage, responses, and prompt hashes.
  Patch-drafting replays do not certify patch application or passing tests.

## Out of scope

- The maintainership modes themselves.
- The spec-loop tooling, which lives in `tools/spec-loop/` and is
  documented in [`../README.md`](../README.md), not here.

## Acceptance criteria

1. `skill-and-tool-validate` enforces required frontmatter + link integrity.
2. `list-skills` generates its index from live frontmatter, covering every
   install method (snapshot, framework checkout, marketplace plugin) and
   grouping by declared `family:`.
3. Each meta tool ships with its own tests.
4. Frontmatter values for `mode`, `status`, `capability`,
   `organization`, and `source` are validated against documented
   vocabularies; unknown organizations fail unless the organization
   exists under `organizations/`.
5. Capabilities declared in skill frontmatter and tool READMEs are
   present in `docs/labels-and-capabilities.md`; taxonomy entries with no
   implementation are explicitly marked reserved or future. The tool
   READMEs' `**Capability:**` lines also generate `.github/labeler.yml`
   (`tools/dev/generate-labeler-config.py`, kept in sync by a prek hook),
   together with skills' `family:` / `capability:` frontmatter; that config
   pre-applies the labels to PRs and their linked issues, and every taxonomy
   label has a labeler rule or an `UNMAPPED` reason (`check-labeler-coverage`).
6. `docs/modes.md` skill lists and shipped counts are checked against
   live skill frontmatter.
7. `spec-inventory` emits a compact, deterministic routing map for specs,
   skills, and tools, and has its own tests.
8. `skill-evals` keeps mock tool output in the user turn and appends optional
   trusted repository context only to the system prompt.
9. `skill-evals` never reports PASS for a case in which nothing was graded:
   a CLI that emits no JSON, or exits non-zero, errors unless the suite
   explicitly asserts on the wrapped output.
10. `skill-evals` reads no fixture whose resolved path leaves
    `tools/skill-evals/evals`, and re-asks a dropped grader verdict once
    without ever re-asking a verdict the grader gave.
11. The validator fails a skill whose `name:` does not match the
    directory holding its `SKILL.md`.
12. Every `SKILL.md` carries a current `measured_tokens:` stamp;
    `skill-token-count --check` fails on a missing or stale one.
13. `check-claude-mods` fails a plugin whose hooks module does not pass
    `claude plugin validate --strict` or whose `claude plugin test` run
    fails or finds no tests, and CI runs it whole-repo on every pull
    request and push to `main` (#1564).
14. `vendor-neutrality-score` counts each `+`-joined `**Vendor:**` entry
    as a separate backend vendor and rejects `agnostic` mixed with named
    vendors or an empty entry (#1575).
15. A pull request's `tests` run picks only the workspace members its
    changes affect, and the required `tests-ok` gate fails when member
    discovery fails or the matrix is skipped without an empty selection
    (#1717, #1807).
16. `pre-release-sweep` changes nothing before its PR plan is approved,
    lands one concern per PR, and closes no issue on a commit message
    alone or without the maintainer's confirmation; its classification of
    open issues is covered by `tools/skill-evals/evals/pre-release-sweep/`.
17. `check-claude-floor` fails when `claude plugin validate`, from the
    release that `min_version` names and without `--strict`, rejects the
    marketplace or any plugin it lists. CI runs it on every push to `main`
    and on each pull request that changes a plugin, the marketplace or the
    floor (#2248).

## Validation

```bash
uv run --project tools/skill-and-tool-validator --group dev pytest
uv run --project tools/skill-and-tool-validator --group dev skill-and-tool-validate
uv run --project tools/skill-evals --group dev pytest tools/skill-evals/tests
uv run --project tools/spec-inventory --group dev pytest tools/spec-inventory/tests
uv run --project tools/dev pytest tools/dev/tests/test_ci_pytest_batches.py tools/dev/tests/test_ci_tests_gate.py tools/dev/tests/test_check_claude_floor.py
```

## Known gaps

- **Frontmatter validation is still shallow.** Current validation covers
  required fields, but the next pass should make `mode`, `status`,
  `capability`, `organization`, and `source` combinations explicit and
  test-backed.
  <!-- gap-closes-when: none (narrative) -->
- **No adopter pilot has submitted a validated report.** The shape is defined
  in `docs/pilot-report-template.md` and enforced by
  `tools/pilot-report-validator/`, but the template is the only file in the
  tree carrying that frontmatter.
  <!-- gap-closes-when: none (narrative) -->
- **The 500-line cap is advisory.** `skill-line-limit` is a SOFT check, so
  nothing blocks a `SKILL.md` growing past it. Seven are over it today:
  `issue-triage` (531), `release-verify-rc` (527), `issue-stale-sweep` (525),
  `issue-reassess` (520), `issue-reproducer` (518), `audit-finding-fix` (504)
  and `issue-deduplicate` (503).
  <!-- gap-closes-when: none (narrative) -->
