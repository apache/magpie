<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Vetted command surface

**Status:** partial — the dispatcher ships; per-scope enforcement does not.

**Capability:** substrate:sandbox

## Problem

[RFC-AI-0002 Layer 3](../../../docs/rfcs/RFC-AI-0002.md) forces confirmation on
outward-visible actions with wildcard rules — `Bash(gh issue edit *)`,
`Bash(gh api * -X *)`, and so on. The wildcard is what makes the rule safe (an
unbounded argument surface cannot be pre-approved) and also what makes it
expensive: a maintainer sweeping thirty trackers answers a hundred prompts, and
the hundredth gets less attention than the first.

Prompt fatigue is a security failure, not an ergonomics complaint. A posture that
is correct but unusable degrades into a posture that is bypassed.

## Approach

Replace the wildcard, not the confirmation. Route forge actions through a
dispatcher whose operations are a **closed catalogue** of fixed shapes:

- parameters are typed and validated; none may start with `-`; an anchored
  check matches the whole value (`fullmatch`), so a trailing newline is
  refused, in the operations, the git operations and the policy loader alike
  (#2270, #2314);
- every parser (the four dispatchers, `vetted-op-checks` and
  `vetted-ops-codex-rules`) sets `allow_abbrev=False`, so a long option is
  matched by its exact spelling, as the pre-parse checks assume, and a
  prefix such as `--call` for `--caller` is a usage error (#2363);
- builders return `list[str]` executed without a shell for forge operations, or a request descriptor executed via Python stdlib `urllib.request` for HTTP read operations;
- the repository is policy, never a parameter;
- value-bearing parameters (labels, milestones, assignees, columns, close
  reasons) must appear in adopter-declared enums;
- free text reaches the forge only by file reference, and the file must sit
  inside a declared workspace, reached with no symlink on its path;
- GraphQL documents are *named*, not supplied: the caller picks one of the
  allowlisted queries shipped with the dispatcher, which supplies the text and
  fills owner/name from policy.

A bounded effect set can be `allow`ed once. Widening it is a reviewed code
change.

Shipping implementation: [`tools/vetted-ops`](../../vetted-ops/README.md).

**Where the policy is read from** (#1787).
Without `--config`, the dispatcher reads the committed
`.apache-magpie-overrides/tools/vetted-ops/config.toml` first, then
`tools/vetted-ops/config.toml` in a personal layer, so a maintainer whose
project has not adopted Magpie can still run the security skills.
A personal layer counts only in a shape the sandbox profile's deny globs
cover (`//**/.git/**/apache-magpie/…`, `//**/.svn/apache-magpie/…`,
`//**/.apache-magpie-local/…`), and a policy reached through a symlink
anywhere on its path, or that is not a regular file, is not read.
The personal policy supplies data only and grants nothing `--config` could
not; `setup config` drafts it, the user saves it.

**The write entry points act only on an approved policy** (#1957).
`vetted-op` and `vetted-op-tracker` run outside the sandbox, so a policy they
act on must be one the agent cannot write.
They refuse `--config` whenever an operation runs; a dry run, `policy` and
`list-ops` publish nothing and keep it.
They act on the discovered policy only when it is byte-for-byte a `.toml` the
user placed in `~/.config/apache-magpie/vetted-ops/`, because discovery starts
from a working directory the agent picks.
That directory sits outside every sandbox-writable root and is `Edit`-denied,
and its home comes from the password database, not `$HOME`.
`vetted-op-read` still takes `--config`.
`safe_read.py` opens every policy and body one path component at a time from
the checked descriptor, following no symlink, and a `workspace` with a symlink
on its path is refused.

The HTTP read backend (`http-read`, which implies `writes=False`) carries the
security-data lookups the adapters used to spell as raw `curl`: four OSV.dev
operations (`osv-get-vuln`, `osv-query-package`, `osv-query-commit`,
`osv-query-batch`) and `cve-check-published` against CVE Services. URLs are
built from closed templates over `[endpoints]` bases the policy declares, which
must be `https://`; parameters are validated against `..` and shell
characters; responses stream to stdout, never to a file; and `urllib.request`
honours `HTTPS_PROXY`, so the egress gateway still applies (#1326). The
`tools/osv/` and `tools/cve-org/` recipes, and `security-issue-sync`'s
cve.org check, invoke it through the same `uv run --project
~/.claude/magpie/vetted-ops vetted-op-read …` spelling every permission rule
and sandbox exclusion names — a bare `vetted-op-read`, or the in-repo
`tools/vetted-ops` copy, would miss the allowlist and prompt or run sandboxed
(#1339). No rule names the in-repo copy: it is agent-editable, so excluding it
would run editable code outside the sandbox.
Two spellings are recognised, and each is both allowed and excluded from the
sandbox: `uv run --project … vetted-op-read` and `uvx --from … vetted-op-read`,
the form the read-only gatherer agents use (#1393). Before #1393 only the
`uv run --project` form was excluded and neither was allowed, so every
gatherer read prompted. The adopter install now carries these read `allow`
entries into the settings merge and the update skill diffs them; `vetted-op`
(writes) stays on `ask`.

The `procedure` backend carries the tracker read-modify-write updates that
`tools/github-rollup` and `tools/github-body-field` do outside the sandbox:
`rollup-append`, `rollup-amend-latest`, `rollup-fold` and `body-field-set`
(writes), and `body-field-get` (a read). The builder returns a plan bound to one
of five fixed procedures; the procedure reads the rollup comment or the issue
body in-process and makes its writes through a runner that permits only `gh`
calls with no shell, `gh issue view|comment|edit` with `--repo <tracker>`, and
`gh api` paths under `repos/<tracker>/` (plus the fixed `gh api user` login
read), with bodies on stdin and no `@file` fields. An operation declared
read-only gets a runner that refuses every write. The parsing and composing
modules are vendored byte-for-byte from the two tools, with a test that fails
on drift, because the dispatcher installs without them.
The runner also refuses a `gh api` call that names its own repo or host, a
path that traverses, a method other than `GET`, `PATCH` or `DELETE`, and a
`gh issue --body-file` other than `-`, so no procedure makes `gh` read a local
file.
The dispatcher refuses a plan bound to any repository other than the policy's
tracker.
`rollup-amend-latest` refuses when the latest entry carries a different action,
and `rollup-fold` refuses the rollup comment itself or a comment that belongs
to another issue, and deletes the folded comment only after the append
succeeded.
Skills write with `vetted-op-tracker --caller <skill> rollup-append|rollup-amend-latest|rollup-fold|body-field-set …`
and read a field with `vetted-op-read --caller <skill> body-field-get …`;
the `github-rollup` and `github-body-field` uv CLIs remain for use outside the
sandbox (#1448).
`body-field-get` and `body-field-set` use the vendored copy of
github-body-field's parser (kept byte-identical, with a parity test), so
they refuse a field readers could disagree on, and `body-field-set`
refuses a rewrite that would change any other field (#1672).
On stdout, `body-field-get` prints the one value and `rollup-append` /
`rollup-amend-latest` print the rollup comment's URL (`…#issuecomment-<id>`),
so a caller can link to the entry without reading the rollup (#1451).
The security skills are the first callers (#1451), and the policy example
grants each security caller exactly the tracker operations it uses.
The CVE JSON refresh needs no operation of its own: the skills save the issue and the roster
with `vetted-op-read --save … issue-view` / `collaborators`, run `generate-cve-json` in the sandbox on those files
(`--issue-json`, `--collaborators`, `--attach --output-body`, which never call `gh`),
and write the body back with `issue-edit-body`;
the policy example grants those to `security-issue-sync`, `security-cve-allocate` and `security-issue-deduplicate`.

A third entry point, `vetted-op-tracker`, refuses every operation except the
procedure ones before it reads the policy — the same shape as
`vetted-op-read`'s write refusal. It is excluded from the sandbox, because the
procedures' `gh` must verify TLS, and kept on `ask`, never `allow`.
`vetted-op` is excluded too, in both launcher forms, and likewise never
`allow`ed (#1956): a sandboxed `vetted-op` cannot read `~/.claude/magpie/` to
start, and every operation is a fixed `gh` argv with no shell and bodies read
only from the owner-only workspace, so it reaches less than the bare `gh *`
exclusion.

A read too large to carry through the agent's context goes to a file:
`vetted-op-read --save NAME` writes a read operation's output to
`<workspace>/saved/NAME` and prints one JSON line (`saved`, `bytes`), so a
sweep's pages reach a deterministic tool such as `tools/pr-management`
without passing through the agent (#1570).
Writes and procedures refuse it, and `NAME` is a single path component.
Each `--save` also prunes `saved/` entries older than `saved_retention_days`
(under `[values]`, default 7 days): only regular files and symlinks the
caller owns, relative to the same `saved/` descriptor, never following a
link; the marker, dot-files, subdirectories and the file just written stay
(#2183).
Body and title files are removed from the workspace once their write
succeeds (#2163).
Because `vetted-op-read` runs outside the sandbox and `--config` can name a
policy the agent wrote, `--save` writes only into a `<workspace>/saved/`
directory that already exists and holds a regular `.vetted-ops-save` marker;
it creates neither, so it never reaches a directory the caller could not
already write.
The output goes to an exclusively created `0600` temporary file renamed into
place, opened with `O_NOFOLLOW`, so a planted symlink or hard link is
replaced rather than written through.

A skill family's operations may live in their own `ops_<family>.py` module
inside the `vetted_ops` package (`ops_code_review`, `ops_quick_merge`,
`ops_stack_review`, `ops_stale_sweep` today), registered like the core
catalogue; only modules shipped in the package load, so the catalogue stays
closed and adding one is the same reviewed change (#1579).

The dispatcher runs from the installed `magpie-vetted-ops` plugin, which ships
`tools/vetted-ops` without the workspace root, so the project must resolve
standalone: it declares no `dev` dependency group, because uv resolves every
group before running and `magpie-dev` resolves only through the root's
`[tool.uv.sources]`. Its tests take the shared toolchain from the root `dev`
group instead (#1357).

The plugin is part of every install's baseline, but installing it grants
nothing. The read `allow` rules and sandbox exclusions are a permission bypass
that is safe only inside the sandbox, so the isolated setup wires them (and the
Codex native rules) only where the sandbox is configured; without it every
vetted operation keeps its prompt, and verify treats such rules as a failure.

Permission rules and sandbox exclusions name the fixed path
`~/.claude/magpie/vetted-ops`, never the versioned plugin-cache directory. The
plugin's `SessionStart` hook points that path at the installed version each
session, and it is `Edit`-denied alongside the catalogue. A `*` in place of the
version would also match spaces, approving a command with extra `uv` options
spliced in at that position; sandbox-lint rejects any Bash `allow` rule with a
`*` before its end.
The hook (`tools/vetted-ops/hooks/link-stable-path.sh`) only ever replaces a
symlink: a real file or directory at the path is left alone and reported. The
isolated-setup update and verify skills report a leftover versioned glob as
must-fix (#1406).
The fixed path must never be a working directory
(`permissions.additionalDirectories` or `/add-dir`): the sandbox makes working
directories writable to sandboxed Bash, and the exclusions run this checkout's
code outside the sandbox. `sandbox-add-project-root.sh` once listed it to stop
reads there prompting under `permissions.blockReadsOutsideWorkingDirectories`
(#1418) and now removes it; sandbox-lint fails on such an entry (see
[`agent-isolation-sandbox.md`](agent-isolation-sandbox.md)).
The read block cannot be satisfied for the dispatcher commands anyway: they spell `~`
literally, which the read check cannot resolve, so every call prompts while
the block is on, whatever the `allow` rules or working directories say.
Read-only vetted ops must never prompt, because background gatherer agents
cannot answer a prompt and each one becomes a silent denial. The required
shape is `vetted-op-read` allowed and excluded for both launchers on the
literal `~` base only, no `ask` rule matching a `vetted-op-read` command, the
read block off in every scope, and the three vetted-ops `Edit` deny rules present.
The install skill applies it (Step V.1), verify checks it (check 16), update
reports drift as must-fix, and sandbox-lint enforces it on the committed
settings. `vetted-op-tracker` and `vetted-op` keep their `ask`.
Every call spells the base `~/.claude/magpie/<tool>` (AGENTS.md golden rule):
the agent-guard `vetted-ops-spelling` guard refuses an expanded home path,
`$HOME/…` or a relative checkout path for `vetted-op`, `vetted-op-read`,
`vetted-op-tracker` and `adversarial-review`, and names the `~` command.
The `excluded-chain` guard covers the other half of the exclusion contract:
a sandbox-excluded command (a `~/.claude/magpie/…` `uv run --project` /
`uvx --from` launch, or an excluded user-scope script) runs outside the
sandbox only as the whole command line, so a chained, piped, substituted or
redirected line is refused with an instruction to run it alone
(`MAGPIE_ALLOW_CHAINED_EXCLUSION=1` overrides; #2142).
It accepts the `~` only bare and space-separated: a quoted or escaped `~`,
a quote after it, or the `--project=~/…` form leaves it unexpanded, so uv
gets a directory named `~` and the exclusion does not match. Because an
exclusion matches a command line by its start, the right spelling behind
`env` or `command` still runs sandboxed and is refused with the command to
run instead. The eval wrapper gets the same treatment: any spelling of
`magpie-run-evals.sh` other than the bare `~/.claude/scripts/…` path is
refused (override `MAGPIE_ALLOW_SCRIPT_PATH=1`), because it would run in the
sandbox and every eval case would error ungraded (#1691).
It also refuses an absolute path inside the working tree, and reads `uv`'s
options on either side of `run`. Under Codex it lets a `vetted-op-read`
through from the exact root Codex's own hook substitutes for `~` (the
registered `--stable-path`, else the account's home from the password
database), since Codex execpolicy cannot match `~`; any other root is one the
agent could have built and stays refused.

**Project-board operations** (#2179, #2181).
A GitHub-backed tracker's Projects V2 board is kept through five operations
whose ids come from the policy (`board_project_id`, `board_status_field_id`,
`[values.board_columns]`): reads `board-item` and `board-items`, writes
`board-add-item`, `board-set-status` and `board-archive-item`.
`security-issue-sync` adds a missing item, moves it to the column its labels
call for and archives it once closed; its end-of-sync sweep archives anything
that is not a security tracker, keeping the board security-only
(`tools/github/project-board.md`).

**Every skill carries the sandbox golden rule** (#2162).
The shared block `tools/dev/blocks/sandbox-golden-rule.md`, kept in sync by
`check-shared-blocks.py`, tells the agent that a step the sandbox blocks
becomes a vetted operation (`vetted-op-read`, `vetted-op`, `vetted-op-tracker`,
`vetted-op-git`) or a documented in-sandbox route, never a bypass or a wider
exclusion; if none exists it gives the user the one command and proposes
`setup-upstream-fix`.

## Scoping — what is real and what is aspiration

The dispatcher requires `--caller` and refuses operations outside that caller's
declared manifest. **This is least-privilege, not a security boundary.** Within a
session the agent is one principal and supplies `--caller` itself. It defends
against the wrong skill reaching for the wrong operation — including the
prompt-injection case where hostile issue text talks a read-only triage pass into
a state change — and not against a determined agent.

A real boundary requires the runtime to bind scope to permissions. Surveying what
exists today:

| Mechanism | Available? | Note |
|---|---|---|
| Plugin-declared permissions | No | No `permissions` field in a plugin manifest |
| Marketplace-declared permissions | No | Same |
| `permissionMode` on plugin agents | No | Explicitly unsupported, for security reasons |
| Subagent with a restricted `tools` list | **Partly** | Claude Code only |

The last row is the opening. A skill that delegates its write operations to a
subagent shipping a restricted `tools` list gets enforcement from the runtime
rather than from an honour-system argument. It is not portable: Claude Code
supports it, the only other shipping runtime adapter is Codex
(`experimental`), and the remaining runtimes are unimplemented extension points
per [`docs/adapters/registry.md`](../../../docs/adapters/registry.md).

## Future work

1. **Per-scope enforcement where the runtime allows it.** Ship write operations
   behind a subagent with a restricted tool list on runtimes that support it,
   keeping the dispatcher as the portable floor. Treat it the way
   [RFC-AI-0002 treats the push gate](../../../docs/rfcs/RFC-AI-0002.md): a
   harness-specific hardening layered on a harness-agnostic base, with the
   asymmetry stated rather than hidden.

2. **Generalise beyond the security family.** *PR management has landed* — 22
   operations covering list / view / diff / reviews, the label, milestone,
   assignee and reviewer edits, the three review verdicts, draft/ready, close,
   branch update, CI re-run and workflow approval, plus two allowlisted GraphQL
   queries (`pr-liveness`, `pr-review-threads`). *The issue family has landed* —
   ten `repo-issue-*` operations against the **upstream** repository, kept
   distinct from the `issue-*` operations that address the private tracker, with
   a test asserting the two never cross. Repo health, release management,
   mentoring and contributor growth remain; each needs its own operations and
   its own caller manifests, and none needs a second dispatcher.
   `pr-view` deliberately leaves the PR `body` out, so the pr-management sweeps
   do not load every PR description; `pr-view-with-body` returns the same fields
   plus `body`, against the policy-pinned upstream only, and is granted to
   `security-issue-import-from-pr`, which builds the tracker body from it (#1457).
   The pr-management skills that now run their rules as code added the reads
   those rules consume, each meant to be saved with `--save`: the triage
   sweeps (open / label / author / review-requested) and one PR in a single
   paginated triage shape, the triage pre-flight, recent main-branch failures,
   the `action_required` run index, a head's workflow and check runs,
   commits-behind, a team's roster, and the stats open and closed reads
   (#1570); and per-family reads for quick-merge, pr-stale-sweep,
   stack-review and code-review (#1580, #1581, #1582, #1585).
   Each search string is built by the operation with `repo:<upstream>` from
   policy first, so its parameter narrows a sweep and cannot re-aim it; this
   is a fixed shape, unlike the free-text search refused below.
   `pr-management-code-review`'s auto-merge path added `run-rerun`, for a run
   held in `action_required` that `workflow-approve` answers is not waiting for
   approval (#1951).
   It also reads `check-runs` for the head commit before proposing an
   approval, the secondary confirmation that real CI ran there (#2072); the
   read is the triage one, granted to `pr-management-code-review` as well.
   `pr-management-triage`'s recovery journal added two read-only operations,
   `pr-triage-recovery-state` (the PR fields a triage write changes, read
   before each write) and `pr-triage-comment-receipt` (one issue comment by
   numeric id, after a comment write), both against the policy-pinned upstream
   and granted to `pr-management-triage` (#2065).
   Workflow run ids and REST comment ids are database ids, already past ten
   digits, so they are validated with their own bound of 19 digits (any int64);
   issue and pull request numbers keep ten (#2264).
   `security-issue-sync` reads a GitHub Security Advisory's comments with
   `advisory-comments` and posts a reply the reporter sees with
   `advisory-comment` (#1964).
   Read-only gatherers for `security-issue-sync` and `security-issue-triage`
   search the upstream repository with `repo-pr-search` and `repo-code-search`,
   so "was this already fixed upstream?" needs no raw `gh search` outside the
   dispatcher. Like `issue-search`, each pins the repository from policy and
   takes one plain-word `query` (no `:`, one line, no leading `-`, after `--`).
   The README's caller example grants each security skill the reads its own
   docs run under its caller, so a gatherer never borrows another skill's
   caller: `security-issue-triage` reads its queue (`issue-list-label`),
   searches trackers (`issue-search`) and upstream (`repo-pr-search`,
   `repo-code-search`); `security-issue-import` reads a relayed GHSA
   (`advisory-view`, `advisory-comments`) and runs its duplicate search
   (`issue-search`, `issue-view`) and its Step 2c upstream search
   (`repo-pr-search`, which `security-issue-sync` also runs in Step 1b);
   `security-issue-invalidate` posts the closing GHSA comment
   (`advisory-comment`).
   `security-issue-import-from-scan` has its own caller for the import and
   triage steps it reuses: the open-tracker list (`issue-list-with-bodies`),
   the duplicate and precedent searches (`issue-search`, `issue-view`), the
   fixed-since-the-scan check (`repo-pr-search`, `pr-view`, `pr-diff`,
   `compare`) and the patch comment on a new tracker (`issue-comment`).
   `test_caller_grants.py` checks every `--caller` call in the repository's
   Markdown against that example.

   *Repo health, release management, contributor growth and mentoring have
   landed*, completing the pass over the families that touch the forge. They
   needed seven operations between them — `repo-view`, `repo-tree`, `run-list`,
   `run-view`, `release-list`, `release-view`, `user-profile` — because they are
   overwhelmingly read surfaces; mentoring needed none at all, working entirely
   through the issue and PR operations. A family earns new operations only when
   it has a shape the catalogue lacks.
   `release-rc-cut` needed none either: its only GitHub access is the existing
   `tags` read in Step 0 and, after the Release Manager confirms it, the
   `repo-issue-comment` planning-issue comment, which runs through `vetted-op`
   and asks every time (#1518).
   `tags` lists every tag under a prefix, so the skill treats the RC tag as
   existing only on an exact `refs/tags/<version>-<rcN>` line (`rc1` also
   lists `rc10`).
   The README's caller example and Magpie's own policy grant
   `"release-rc-cut" = ["tags", "repo-issue-comment"]` (#1520).

   Several shapes are refused rather than wrapped, and will stay refused:
   free-text search (`gh search issues` / `prs`, and GraphQL's `search(...)`)
   has no fixed shape;
   release publication and deletion is vote-gated and irreversible; and
   `gh run download` writes to local disk rather than to the forge, which is a
   different risk class entirely. All keep their `ask` rule. The catalogue
   covers the sweep, not everything — and **widening it must never widen the
   posture**, which is why `pr-merge` and `release-delete` are both absent.
   Tracker creation has since got a fixed shape: `issue-create-labeled` (GitHub
   only) takes `title` and `body` as workspace file paths through
   `Op.title_files`, so the dispatcher reads and validates the title and a dry
   run shows only its size, and a JSON array of 1 to 20 distinct policy-approved
   labels applied in the same request; it prints `number`, `node_id` and `url`
   (#1982).
   Opening a pull request, once refused for its free-text title, has a fixed
   shape in `vetted-op-git` (`git-pr-create`, below).

   Note what the PR family deliberately does *not* include: there is no
   `pr-merge`. Merging is this framework's deferred Agentic Autonomous mode —
   `pr-management-merge-candidates` prints a merge command for the maintainer rather
   than running one — so a vetted merge operation would hand the agent the one
   capability the surrounding design withholds. **Widening the catalogue must
   not widen the posture**, and that constraint binds every family added next.
   `pr-management-code-review` enabling auto-merge does not change this: it runs
   the rendered `gh pr merge --auto` directly, which stays on `ask`, not through
   the dispatcher (#1951).

3. **Adapter parity.** Forge operations are `gh`-shaped today (HTTP read operations
   now ship alongside them via a stdlib backend). The forge is already an
   adapter axis (`github`, `jira`, `bitbucket`, `sourcehut`, `fossil`), so the
   catalogue should eventually resolve its builder per configured forge rather
   than assuming one.

4. **Close the loop with `permission-audit`.** Once a repo routes through the
   dispatcher, its wildcard `ask` rules become dead weight;
   [`tools/permission-audit`](../../permission-audit/README.md) is the natural
   place to detect and offer to remove them.

## Batches of private-tracker writes (`vetted-op-tracker-batch`, `-unprompted`)

A bulk run makes dozens of private-tracker writes, and each vetted call is one permission prompt.
When the approved policy sets `[approval] private_tracker_writes` to `batch` or `none`
(default `each`: the batch entry point refuses), a skill writes those writes into one JSON manifest in the workspace
(`{"version": 1, "ops": [{"op": …, "params": […]}, …]}`, 1–200 entries, positional parameters exactly as a single call takes them).
`vetted-op-read --caller <skill> batch-check <manifest>` checks it against the approved policy and prints one line per entry
(bodies and file titles by size only) and a digest; it runs nothing.
The digest binds the destination and what runs: the approved policy's hash, tracker, tracker backend, board id, resolved workspace and mode,
the manifest, every body and title it names, and every entry's built command, so a manifest checked under one policy is refused under another.
`vetted-op-tracker-batch --caller <skill> --expect <digest> <manifest>` checks the manifest again,
refuses a digest that does not match, and runs the entries in order, stopping at the first failure.
Its report lists the entries that `succeeded`, the failing one as `unknown` (a write can land and still exit non-zero) and the rest as `not_run`;
the caller reads the tracker before proposing the unknown entry again.
Body and title files are consumed only after every entry succeeded; the manifest is removed after any run, so it is never rerun blindly.
`vetted-op-tracker-batch-unprompted` takes the same arguments and refuses, before it reads the manifest, any policy not set to `none`.
Every check runs before the first write, and one failure refuses the whole batch:
batching on, the schema, every operation in the closed `BATCHABLE` list of private-tracker writes
(public and outbound writes — `pr-*`, `repo-issue-*`, `advisory-comment`, the CVE-tool operations, `tracker-publish`, `vetted-op-git` — are refused by name, even when granted),
the caller's grants, the single-call parameter checks and builder, a built argv that addresses the tracker or the policy's board,
and, on GitHub, the forge reporting the tracker private and a touched board not public.
The prompt is the harness's: both batch dispatchers are excluded from the sandbox and on `ask` like the other write dispatchers.
sandbox-lint accepts `allow` for `vetted-op-tracker-batch-unprompted` alone, which an adopter writes only under `none`;
since that script runs no other mode, an `allow` for one project cannot run another approved project's `batch` policy unprompted, whichever policy `--policy-from` or `cd` selects.
`batch-check` and both batch dispatchers take `--policy-from <dir>` with the single-call dispatchers' confinement:
only a checkout the operator's own `operator-git.toml` lists, compared as text before the file system is touched,
and only an approved policy there that lists that checkout for its upstream; a repeated `--policy-from` is refused.
Design, alternatives and the trade-off of `none`:
[`docs/designs/2026-11-26-vetted-ops-batch-tracker-writes.md`](../../../docs/designs/2026-11-26-vetted-ops-batch-tracker-writes.md).

## Git operations the sandbox blocks (`vetted-op-git`)

A fourth entry point, `vetted-op-git`
(`tools/vetted-ops/src/vetted_ops/git_ops.py`, #2161), runs the git steps a
sandboxed session cannot: a push over SSH (the proxy gives no TCP and a
hardware key's touch prompt never reaches the user) and adding, moving or
removing a linked worktree the session did not create (its administrative
directory is read-only). It is excluded from the sandbox and kept on `ask`,
like `vetted-op`.
Operations are closed shapes: `git-push-branch` (a leased push, `--force-with-lease`
on the caller's expected SHA or `new`, to the policy's `fork` or to an
`upstream_push`-matching branch of upstream, protected branches always
refused, an emptied rebase refused), `git-delete-fork-branch` (a branch on the
policy's fork only, never a protected one, and only once the forge reports a
merged pull request against upstream headed by it at the caller's expected
SHA; leased on that SHA), `git-push-pr-head` (a maintainer fixup:
fast-forwards an open upstream pull request's head branch, named by the
caller so the confirmation shows it and checked against what the forge
reports, leased on the head the caller built on, at most ten non-merge
commits on top, apart from a merge of upstream's `pr_base` (fetched by the
operation), whose upstream commits do not count; a contributor's fork only
when its author allows maintainer edits), `git-merge-upstream` (a signed merge
of a full SHA of the upstream `pr_base`, fetched by the operation, into a clean
non-protected topic branch at the caller's expected SHA, with a fixed message;
when the user signs, the commits it vouches for must carry their signature:
on their own branch every commit not on upstream, on a pull request's branch
only those on top of the head the forge reports; a conflict aborts and names
the paths, and a merge onto a moved branch is taken back off),
`git-switch` (a clean working tree to an existing local branch, only when
the branch's own commits leave its files that steer the agent harness,
plus the policy's `harness_paths`, as upstream's `pr_base` had them where
the branch left it: that commit asked of the policy's URL during the
call, both trees walked through objects re-hashed against their names,
and every harness file written hashed again after the checkout),
`git-switch-create` (a new, non-protected topic branch at upstream's
`pr_base` as the policy's URL reports it during the call, then `git-switch`
to it; a branch it could not switch to is deleted again),
`git-worktree-sync` (`reset --keep` of a
clean linked worktree), `git-rebase` (a clean, non-protected topic branch with no
merge commits onto a full SHA of the upstream `pr_base`, which the operation
fetches itself from the policy URL and checks against that fetch's own result;
refused unless the branch is at the caller's expected SHA, and put back if it
moves while the rebase starts; re-signs per the global config, and when that
signs commits, refuses any replayed commit without the user's good signature,
so a commit the agent made unsigned in the sandbox is never signed; with `rerere`,
autostash, `updateRefs`, editors and hooks pinned off; a conflict aborts and
names the paths), `git-cherry-pick` (one plain commit onto a clean
non-protected topic branch at the caller's expected SHA, to finish a
conflicting rebase commit by commit; when the user signs, the commit must
already carry their signature; a conflict aborts and names the paths, and a
pick onto a moved branch is taken back off), `git-worktree-add` and
`git-worktree-remove`
(never `--force`), and the publishing steps (#2224): `git-stage` (exactly the
relative paths listed in a workspace file, as literal pathspecs inside the
worktree), `git-commit` (what is staged, on a non-protected branch, message from
a workspace file, signed per the user's global config), `git-fetch` (one upstream
branch from the policy's URL into `refs/remotes/<upstream_remote>/<branch>`) and
`git-pr-create` (a pull request from `<fork>:<branch>` against `pr_base`, the
title on the command line so the confirmation shows it, the body from a
workspace file, both refused when they hold a never-publish term from
`forbidden_terms.py`, except the ones the policy's `[git] published_terms`
names: only `CVE id` and `CVE`, a project key the operator file cannot set, for
the policy of a site repository whose pull requests add records already public;
it requires `[git] published_paths`, relative glob-free path prefixes, and
applies only when the forge's compare of the pushed branch against `pr_base`
lists every changed file under one of them, with the branch's head at the local
branch's commit, so a source-repository change never gets it).
`--policy-from <absolute dir>` (on `vetted-op-git`, and on `vetted-op`,
`vetted-op-read` and `vetted-op-tracker`, where it makes even a read require an
approved policy; on all of them the directory must be a `checkouts` entry of
the operator's `operator-git.toml`, checked before the file system is touched,
and the policy's upstream table must list it, so the unprompted read dispatcher
cannot probe the host; `approval-status` and `source` refuse it) discovers the
policy from that directory instead of the working directory; only an approved policy acts either way, so it lets a
tracker session reach a site repository's own policy without a `cd` that would
put the call back in the sandbox. `security-issue-sync` uses it to publish its
records pull request, granted only in a policy whose `[repos] upstream` is the
site repository (the README's second-policy example).
`[git]` values bound them: the project's (`upstream_push`, `protected`,
`pr_base`, `host`) from the policy's `[git]` table, and each operator's
(`checkouts`, `fork`, `worktree_roots`, `upstream_remote`, `transport`, more
`protected`) from `~/.config/apache-magpie/vetted-ops/operator-git.toml`, one
table per upstream repository, which may not set a project key (#2227). A worktree
root must be owned by the operator and writable by nobody else.
When that table is missing, the refusal prints a ready-to-save draft of it
(main checkout, upstream remote, a `<checkout>-worktrees` root, the fork left as
a placeholder), and under the secure setup `setup config` Step 3a.3 proposes the
same table as a line the user runs, never writing the file itself (#2230).
Safety rests on: destinations built from policy, never from a configured
remote; refusal while repository config holds any key outside an inert list,
checked in every working tree and again before the acting command (the list
admits `gh-stack.remote`, which `gh stack link` writes and git never reads,
#2263); the signing and verification settings (`gpg.format`, the gpg programs,
the allowed-signers and revocation files, the default-key command, the minimum
trust level, `user.signingKey`) pinned to the user's own values on every call
(#2282); pinned
config (no fsmonitor/gc, `https`/`ssh` only, attributes read from the empty
tree, hooks never run, `--no-verify`); validated directories held by
descriptor and git given the validated git directory; and every `GIT_*`
variable dropped with `HOME` taken from the password database.
Git 2.42 or newer is required.
The `pre-push` checks run in the sandbox first. The pre-commit checks are
enforced: `vetted-op-checks`, the one vetted-ops command that runs inside the
sandbox (no exclusion names it, and a test keeps it so), starts from the
readable per-version copy the plugin's session hook keeps at
`~/.cache/apache-magpie/vetted-ops/current` (the sandbox cannot read
`~/.claude/magpie/`), runs the worktree's
hooks on the listed paths and records the content they passed in
`<workspace>/checks/` (in a linked worktree whose git directory the sandbox
cannot read, it computes SHA-1 blob ids itself and refuses when a hook
configuration is present, since the hook manager runs git, unless the
policy is a records-site one with `[git] site_hooks = "skip"`, where
`--skip-site-hooks` records them as skipped and `git-commit` accepts only
that policy's record); `git-commit` refuses a staged path missing from that
record or staged with other content. The record is sandbox-writable, so it
holds an agent to the checks the way CI does, not against a forgery.

**Publishing skills run these steps through one shared block** (#2228).
`tools/dev/blocks/vetted-git-publish.md`, rendered with each skill's `--caller`
into a `vetted-git-publish.md` companion, takes a change to an open pull request
(fetch, worktree, checks, stage, commit, push, open, label, then rebase,
cherry-pick, worktree sync or removal and fork-branch cleanup as needed) for
`security-issue-fix`, `issue-fix-workflow`, `audit-finding-fix`,
`setup-upstream-fix`, `setup-override-upstream`, `pr-management-shepherd`,
`pr-management-code-review` (fixups), `release-audit-report`, `release-prepare`,
`release-announce-draft`, `security-submit-to-oss-scan` and
`committer-onboarding`.
With no `[git]` values configured it hands the user the commands instead; a
draft pull request or a base other than `pr_base` keeps `gh pr create --web`.
Labelling uses the existing `pr-add-label`, with labels listed by name in
`[values]`, never a pattern (#2283); `security-issue-fix` labels its public pull
request only after `<sm> scrub` passes the labels too (#2304).
`tests/test_publish_grants.py` fails when the block names an operation that a
carrying skill is not granted, in the README `[callers]` example or in Magpie's
own policy (draft-PR flows get no `git-pr-create` or `pr-add-label`), and
`tests/test_committed_policy.py` fails when the committed policy is invalid TOML,
grants an operation that does not exist, or misses a taxonomy label from
`docs/labels-and-capabilities.md` (#2231, #2283).
Magpie's own policy grants the installed non-security skills the callers the
README example lists; the security-family callers are left out because the
framework checkout has no tracker (#2320).

**Keeping a policy's grants current** (#2235, #2299).
`setup` reconcile check 3a compares every caller the policy declares, and every
installed skill the README `[callers]` example names, with that example and
reports missing operations as a minimal TOML diff for the user to save; it never
proposes removing a grant.
For a caller that opens and labels pull requests it also lists the upstream's
`<dimension>:<value>` labels and proposes them by name in `[values]
upstream_labels`, grouped by prefix.
`setup verify` check 11 runs it read-only, the isolated-setup install (Step V)
and update (a fifth drift check) run it too, and `vetted-op-read
approval-status` (no options, so it cannot probe other files) prints whether
the discovered policy is approved, for verify check 11a and for the
re-approval line `upgrade` hands the user.
The example grants only what a skill runs: the unused OSV grants for
`security-issue-triage` and `security-issue-deduplicate` were dropped, with a
test that every OSV grant those callers hold is named in the skill (#2250).

Every install method provides the stable path the dispatchers start from,
`~/.claude/magpie/vetted-ops`. A marketplace install links it into the
plugin cache (the plugin's session hook keeps it current). A pinned snapshot
gets a real copy of `<snapshot-dir>/tools/vetted-ops`, made by `setup` and
refreshed by `setup update`, both as lines the user runs. A framework
checkout links it into the main checkout's own `tools/`, so a vetted-ops
change is what the next call runs; that code is the agent's to edit, so
agent-guard's `vetted-ops-source` check answers `ask` for every launch through
such a link, `vetted-op-read` included; a harness whose hook cannot ask (Codex
and the other deny-only adapters) refuses it instead, unless
`MAGPIE_ALLOW_VETTED_PATH=1` (#2287, #2297). The plugin's hook moves only a link
into its own cache, never a copy or a checkout link, and
`vetted-op-read source` reports which of the three is in use (`setup verify`
check 11b).

## Codex native integration

The Codex marketplace advertises the self-contained vetted-ops substrate plugin.
Its packaged runtime and policy remain separate: fixed code lives outside
workspace-writable roots, while the adopter supplies the existing policy.
The shared SessionStart stable-path hook requires Codex hook-definition trust.

`vetted-ops-codex-rules` only prints native rules for review and installation in
user scope, with absolute stable paths rather than version globs, never `~`
(execpolicy rejects `~` words, and a `~` rule would follow a reassignable `HOME`
or a relative `~` directory). `--hook` prints a Codex-only PreToolUse hook that
rewrites a command that is exactly one `vetted-op-read` call in the `~` spelling
to the absolute path fixed at render time, before the rules evaluate it; writes
and compound commands are never rewritten, so it grants nothing itself.
Both uv launchers allow `vetted-op-read` and prompt `vetted-op` and
`vetted-op-tracker`; there is no general uv allowance or automatic policy edit.
Codex escalation and native rules replace Claude's sandbox exclusions.

Source changes to runtime code, hooks, metadata or README trigger the packaging
consistency hook in diff-scoped PR CI as well as whole-tree runs.
Packaged README links to shipped files stay local; links to framework files
outside the installed package point to their public source.

## Non-goals

- **Replacing the sandbox.** This operates at Layer 3 only. Layers 0–2 are
  unchanged and still carry the load.
- **Removing human confirmation from genuinely novel actions.** Anything outside
  the catalogue keeps its `ask` rule. The catalogue is deliberately small and
  grows by review.
- **Pretending `--caller` is authentication.** Stated plainly wherever the
  mechanism is documented.
