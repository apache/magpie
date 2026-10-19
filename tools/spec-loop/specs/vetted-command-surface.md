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

- parameters are typed and validated; none may start with `-`;
- builders return `list[str]` executed without a shell for forge operations, or a request descriptor executed via Python stdlib `urllib.request` for HTTP read operations;
- the repository is policy, never a parameter;
- value-bearing parameters (labels, milestones, assignees, columns, close
  reasons) must appear in adopter-declared enums;
- free text reaches the forge only by file reference, and the file must resolve
  inside a declared workspace;
- GraphQL documents are *named*, not supplied: the caller picks one of the
  allowlisted queries shipped with the dispatcher, which supplies the text and
  fills owner/name from policy.

A bounded effect set can be `allow`ed once. Widening it is a reviewed code
change.

Shipping implementation: [`tools/vetted-ops`](../../vetted-ops/README.md).

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

A third entry point, `vetted-op-tracker`, refuses every operation except the
procedure ones before it reads the policy — the same shape as
`vetted-op-read`'s write refusal. It is excluded from the sandbox, because the
procedures' `gh` must verify TLS, and kept on `ask`, never `allow`.
`vetted-op` itself stays sandboxed: excluding it would run the whole write
catalogue there.

A read too large to carry through the agent's context goes to a file:
`vetted-op-read --save NAME` writes a read operation's output to
`<workspace>/saved/NAME` and prints one JSON line (`saved`, `bytes`), so a
sweep's pages reach a deterministic tool such as `tools/pr-management`
without passing through the agent (#1570).
Writes and procedures refuse it, and `NAME` is a single path component.
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
   has no fixed shape; creation (`gh issue create` / `gh pr create`) would need
   a free-text title, since `gh` offers `--body-file` but no `--title-file`;
   release publication and deletion is vote-gated and irreversible; and
   `gh run download` writes to local disk rather than to the forge, which is a
   different risk class entirely. All keep their `ask` rule. The catalogue
   covers the sweep, not everything — and **widening it must never widen the
   posture**, which is why `pr-merge` and `release-delete` are both absent.

   Note what the PR family deliberately does *not* include: there is no
   `pr-merge`. Merging is this framework's deferred Agentic Autonomous mode —
   `pr-management-quick-merge` prints a merge command for the maintainer rather
   than running one — so a vetted merge operation would hand the agent the one
   capability the surrounding design withholds. **Widening the catalogue must
   not widen the posture**, and that constraint binds every family added next.

3. **Adapter parity.** Forge operations are `gh`-shaped today (HTTP read operations
   now ship alongside them via a stdlib backend). The forge is already an
   adapter axis (`github`, `jira`, `bitbucket`, `sourcehut`, `fossil`), so the
   catalogue should eventually resolve its builder per configured forge rather
   than assuming one.

4. **Close the loop with `permission-audit`.** Once a repo routes through the
   dispatcher, its wildcard `ask` rules become dead weight;
   [`tools/permission-audit`](../../permission-audit/README.md) is the natural
   place to detect and offer to remove them.

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
