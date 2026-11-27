<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [vetted-ops](#vetted-ops)
  - [Prerequisites](#prerequisites)
  - [Why](#why)
  - [What it actually guarantees](#what-it-actually-guarantees)
    - [The boundary is the entry point, not `--caller`](#the-boundary-is-the-entry-point-not---caller)
  - [Configuration](#configuration)
  - [CLI](#cli)
    - [Where do the dispatchers start from?](#where-do-the-dispatchers-start-from)
    - [Is the policy approved?](#is-the-policy-approved)
    - [Saving a read instead of printing it](#saving-a-read-instead-of-printing-it)
    - [Searching the upstream repository](#searching-the-upstream-repository)
    - [The Vulnogram CVE-tool operations](#the-vulnogram-cve-tool-operations)
    - [The project board](#the-project-board)
    - [The pr-management-triage reads](#the-pr-management-triage-reads)
    - [The other pr-management reads](#the-other-pr-management-reads)
    - [The pr-management-stats reads](#the-pr-management-stats-reads)
  - [Tracker procedures: rollup and body-field writes](#tracker-procedures-rollup-and-body-field-writes)
  - [Batches of private-tracker writes](#batches-of-private-tracker-writes)
  - [Tracker backends](#tracker-backends)
  - [Git operations the sandbox blocks](#git-operations-the-sandbox-blocks)
  - [Wiring it into settings](#wiring-it-into-settings)
    - [Codex native rules](#codex-native-rules)
  - [Tests](#tests)
  - [Referenced by](#referenced-by)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# vetted-ops

**Capability:** substrate:sandbox

**Harness:** agnostic

A dispatcher for **fixed, policy-scoped forge operations**, so an agent session
needs *one* allowlist entry instead of a dozen wildcard `ask` rules.

## Prerequisites

- **Runtime:** Python 3.11+ via `uv`.
The package itself is stdlib-only.
- **CLIs:** the `gh` CLI on `PATH`, authenticated for the repositories the policy names.
HTTP operations do not use `gh` or `curl`; they use the `urllib.request` standard library module.
With a non-GitHub security tracker (`[tracker] platform`), tracker operations run `uv` and that backend's CLI instead of `gh` — see [Tracker backends](#tracker-backends).
- **Credentials:** whatever `gh` already uses (`~/.config/gh/`).
This tool reads no credential of its own and stores none.
- **Network:** `github.com` / `api.github.com` for `gh` operations.
HTTP operations connect to the domains configured in the `[endpoints]` table (e.g., `api.osv.dev`, `cveawg.mitre.org`).
- **Configuration:** a policy TOML (see *Configuration*).
Without one, every operation refuses.

## Why

[RFC-AI-0002 Layer 3](https://github.com/apache/magpie/blob/main/docs/rfcs/RFC-AI-0002.md) forces confirmation on every
outward-visible action:

```json
"ask": [ "Bash(gh issue edit *)", "Bash(gh issue comment *)",
         "Bash(gh issue close *)", "Bash(gh api * -X *)", … ]
```

The wildcard is doing the work, and it is also the cost. `gh issue edit *` covers
an unbounded argument surface — `--add-label`, `--body`, `--repo <somewhere
else>` — so a human has to read every invocation to know what it does. On a
sweep that touches thirty trackers, that is a hundred prompts, and the hundredth
gets the same attention as the first. Prompt fatigue is itself a security
problem.

This tool removes the wildcard rather than the confirmation. Each operation is a
**closed shape**: a name, typed parameters, and a builder that returns an argv
list. The repository comes from policy, not the command line. Labels, milestones,
assignees, board columns and close reasons must be values the policy declares.
Because the effect set is bounded by construction, the dispatcher can be
`allow`ed once instead of `ask`ed every time.

## What it actually guarantees

Being precise, because a security tool that overstates itself is worse than none:

- **A parameter can never become a command.** Builders return `list[str]`, executed
  with `subprocess.run(..., shell=False)`. There is no string interpolation
  anywhere in the path, so `1; rm -rf /` is simply an invalid issue number.
- **A parameter can never become a flag.** Any parameter starting with `-` is
  refused before validation, which closes flag-injection into `gh`.
- **The repo is not addressable.** No operation takes a repository parameter; it
  is read from policy. An operation cannot be pointed at another repository, and
  parameters that reach an API *path* — repo paths and git refs — refuse `..`,
  so none of them can walk out of the pinned repository either.
- **Body content is free; body *location* and *timing* are not.** Comment bodies
  may contain anything — backticks, `$(…)`, newlines — because content is never
  interpolated into a command. What is constrained is which file may be read and
  when. The file must resolve inside the configured workspace, that workspace
  must be owned by you and closed to group and world, and a symlink is refused
  (`O_NOFOLLOW`, plus a realpath check for the parents). The dispatcher then
  **reads the bytes itself and pipes them to `gh` on stdin**, so there is exactly
  one open. Handing `gh` a path would leave a window between the check and the
  send in which the file could be swapped; the bytes that were validated are the
  bytes that get published.
- **Published files do not stay behind.** Once a write succeeds, the dispatcher
  deletes the body and title files it read, when each is still a regular file
  inside the workspace. The workspace outlives the session, and these files often
  carry text from a private report. A failed write or a `--dry-run` keeps them,
  so the call can be retried; a file a skill needs again is kept elsewhere.
- **Writes cannot be reached through the read entry point.** `vetted-op-read`
  refuses any operation with `writes=True` *before* it consults the policy or
  looks at `--caller`, so the refusal cannot be argued out of it by argv. This
  is the one property that makes an unattended `allow` defensible — see below.
- **GraphQL is named, not written.** `gh api graphql` normally takes a query as a
  string — the widest surface `gh` offers. Here a caller names one of the
  documents shipped in [`queries/`](src/vetted_ops/queries), the dispatcher
  supplies the text, and `owner`/`name` come from policy. A caller can choose
  among the allowlisted queries; it cannot write one, and cannot re-aim one at
  another repository.
- **A parameter can never become a URL path traversal.**
For HTTP operations, URLs are built from closed templates and injected parameters are strictly validated to refuse `..` and shell characters.
- **HTTP operations are read-only by construction.**
The backend `"http-read"` implies `writes=False`, enforced by the dispatcher.
- **No `curl` or `wget` is involved.**
The `urllib.request` implementation automatically obeys `HTTP_PROXY` and `HTTPS_PROXY` environment variables (egress gateway).
- **HTTP responses are streamed to stdout**, or, with `--save`, written to one
file in a `saved/` directory you marked for it, and nowhere else (see
[Saving a read instead of printing it](#saving-a-read-instead-of-printing-it)).
- **Read-modify-write procedures stay on the tracker.**
The `procedure` backend (see [Tracker procedures](#tracker-procedures-rollup-and-body-field-writes)) runs a fixed sequence of `gh` calls, and every call passes a runner check first: `gh` only, no shell, `gh issue view|comment|edit` only with `--repo <tracker>`, `gh api` only under `repos/<tracker>/`, no `-F key=@<file>` or `--body-file <path>` (bodies travel on stdin), and no write at all from an operation declared read-only.
- **The catalogue is closed.**
Widening the surface means editing [`ops.py`](src/vetted_ops/ops.py) — a reviewed code change, not a runtime decision.

### The boundary is the entry point, not `--caller`

**Per-caller scoping is least-privilege, not a security boundary.** The policy
declares which operations each caller may run, and `--caller` is required. But
within one agent session the agent is a single principal that chooses what to
pass as `--caller`. This protects against *the wrong skill reaching for the wrong
operation* — a real and common failure, especially under prompt injection, where
a hostile issue body talks a read-only triage pass into closing something. It
does **not** stop a determined agent, and a permission rule must never be
written as though it does. Concretely: allowlisting `vetted-op *` on the strength
of a read-only caller name grants **every** operation in the catalogue, because
the next invocation can name a different caller.

What *can* be bound is the **entry point**, because a permission rule keys on the
command and argv cannot change which binary is running. Hence two console
scripts over one catalogue:

| Entry point | Can write? | Intended permission |
|---|---|---|
| `vetted-op-read` | never — refused before policy is consulted | `allow` |
| `vetted-op-tracker` | only the [tracker procedures](#tracker-procedures-rollup-and-body-field-writes) — everything else refused before policy is consulted | `ask`, and excluded from the sandbox |
| `vetted-op-git` | only the [git operations](#git-operations-the-sandbox-blocks), plus `git-pr-create` (the one `gh` call there) | `ask`, and excluded from the sandbox |
| `vetted-op` | yes, subject to policy | `ask` (or unlisted) |

That split is what lets the read path lose its prompts without the write path
losing its gate, and it is why `--caller` repeated twice is an error rather than
a last-wins convenience: argparse keeps the last occurrence, so repetition would
let a command match a rule written against a read-only prefix while resolving to
a privileged caller.
Every dispatcher also refuses abbreviated long options (`--call` for `--caller`),
so each option is matched exactly, as that check and the permission rules assume.

For writes, the confirmation the harness puts in front of `vetted-op` is still
doing the work. A finer boundary — per-skill scope bound by the runtime — needs
something no portable mechanism offers yet: plugin manifests cannot declare
permissions, and `permissionMode` is unsupported for plugin-shipped agents. The
closest primitive is a subagent with a restricted `tools` list, which is **Claude
Code-specific**. See
[`tools/spec-loop/specs/vetted-command-surface.md`](https://github.com/apache/magpie/blob/main/tools/spec-loop/specs/vetted-command-surface.md)
for that trajectory.

**The policy file is only as protected as the filesystem makes it.** Rewriting
the policy cannot reach a write through `vetted-op-read` — that refusal ignores
the config entirely — but it can widen which repository the *reads* point at. If
the policy lives somewhere the agent's shell can write, treat its contents as
advisory rather than enforced.

**This is not a substitute for the sandbox.** It reduces prompt volume at Layer 3.
Layers 0–2 are unchanged and still carry the load.

## Configuration

> **Upgrade Note:** Existing adopters upgrading to use `osv-query-package` must add `ecosystems = ["PyPI", "Maven", "npm", ...]` to the `[values]` table in their policy TOML; without it, `vetted-op-read` refuses package queries during parameter validation.

Adopter-owned, at
`.apache-magpie-overrides/tools/vetted-ops/config.toml` by default:

```toml
# Body files must resolve inside this directory.
workspace = "/tmp/agent-scratch"

[endpoints]
osv_api = "https://api.osv.dev/v1"
cve_services_api = "https://cveawg.mitre.org/api"

[repos]
tracker  = "acme/tracker"   # optional — see below
upstream = "acme/product"

[values]
labels        = ["needs triage", "security issue", "cve allocated", "pr merged"]
# Issues *and* PRs. List every label a skill may set, by name: a publishing
# skill labels the pull request it opened with pr-add-label, one per call.
upstream_labels = ["ready for maintainer review", "area:scheduler"]
milestones    = ["1.2.3", "1.3.0"]
# Optional: full-match patterns that widen the list above (see below).
milestones_patterns = ['Providers \d{4}-\d{2}-\d{2}']
assignees     = ["alice", "bob"]
issue_states  = ["open", "closed", "all"]
pr_states     = ["open", "closed", "merged", "all"]
close_reasons = ["completed", "not planned"]
ecosystems    = ["PyPI", "Maven", "npm", "Go"]

board_project_id      = "PVT_kwDO…"   # ProjectV2 node id
board_status_field_id = "PVTSSF_…"    # its Status field id

[values.board_columns]           # column name -> single-select option id
"Assessed"      = "aee65beb"
"CVE allocated" = "aae2beb3"

[callers]                        # caller -> operations it may run
"security-issue-sync"   = ["issue-view", "issue-comments", "issue-add-label",
                           # Step 5: the saved issue and roster the generator reads,
                           # and the body it writes back.
                           "collaborators", "issue-edit-body",
                           "issue-set-milestone", "issue-comment", "comment-update",
                           "rollup-append", "rollup-amend-latest", "rollup-fold",
                           "body-field-get", "body-field-set",
                           "cve-check-published",
                           "advisory-view", "advisory-comments", "advisory-comment",
                           "issue-create-labeled",
                           "cve-record-fetch", "cve-record-update",
                           "board-item", "board-items", "board-add-item", "board-set-status",
                           "board-archive-item",
                           # Step 1b: upstream PRs that mention the tracker.
                           "repo-pr-search"]
"security-cve-allocate" = ["issue-view", "issue-add-label", "comment-update",
                           "collaborators", "issue-edit-body", "issue-edit-title",
                           "rollup-append", "rollup-amend-latest", "rollup-fold",
                           "body-field-get", "body-field-set",
                           "cve-record-fetch", "cve-record-update", "cve-allocate"]
"security-issue-fix"    = ["rollup-append", "rollup-fold",
                           "body-field-get", "body-field-set",
                           # Step 10: assignee, milestone and labels on the tracker.
                           "issue-add-assignee", "milestone-list", "milestone-create",
                           "issue-set-milestone", "label-list",
                           "issue-add-label", "issue-remove-label",
                           # vetted-op-git: from a change to an open pull request. Its
                           # labels pass the same scrub as the title and body first: they
                           # are public before the advisory.
                           "git-fetch", "git-worktree-add", "git-worktree-sync",
                           "git-worktree-remove", "git-rebase", "git-cherry-pick",
                           "git-switch", "git-switch-create",
                           "git-stage", "git-commit", "git-push-branch", "git-pr-create",
                           "pr-add-label", "git-delete-fork-branch"]
# The other skills that publish a change through vetted-op-git (each skill's
# vetted-git-publish.md names its caller and every step granted here; a test
# keeps the two in step). Grant only the skills the project runs; the
# draft-PR flows open the draft with `gh pr create --web --draft`, so they
# need no git-pr-create or pr-add-label.
"issue-fix-workflow"    = ["git-fetch", "git-worktree-add", "git-worktree-sync",
                           "git-worktree-remove", "git-rebase", "git-cherry-pick",
                           "git-switch", "git-switch-create",
                           "git-stage", "git-commit", "git-push-branch",
                           "git-delete-fork-branch"]
"audit-finding-fix"     = ["git-fetch", "git-worktree-add", "git-worktree-sync",
                           "git-worktree-remove", "git-rebase", "git-cherry-pick",
                           "git-switch", "git-switch-create",
                           "git-stage", "git-commit", "git-push-branch",
                           "git-delete-fork-branch"]
"release-prepare"       = ["git-fetch", "git-worktree-add", "git-worktree-sync",
                           "git-worktree-remove", "git-rebase", "git-cherry-pick",
                           "git-switch", "git-switch-create",
                           "git-stage", "git-commit", "git-push-branch",
                           "git-delete-fork-branch"]
"pr-management-shepherd" = ["git-fetch", "git-worktree-add", "git-worktree-sync",
                            "git-worktree-remove", "git-rebase", "git-cherry-pick",
                            "git-switch", "git-switch-create",
                            "git-stage", "git-commit", "git-push-branch", "git-pr-create",
                            "pr-add-label", "git-delete-fork-branch"]
"release-audit-report"  = ["git-fetch", "git-worktree-add", "git-worktree-sync",
                           "git-worktree-remove", "git-rebase", "git-cherry-pick",
                           "git-switch", "git-switch-create",
                           "git-stage", "git-commit", "git-push-branch", "git-pr-create",
                           "pr-add-label", "git-delete-fork-branch"]
"security-submit-to-oss-scan" = ["git-fetch", "git-worktree-add", "git-worktree-sync",
                                 "git-worktree-remove", "git-rebase", "git-cherry-pick",
                                 "git-switch", "git-switch-create",
                                 "git-stage", "git-commit", "git-push-branch",
                                 "git-pr-create", "pr-add-label", "git-delete-fork-branch"]
"committer-onboarding"  = ["git-fetch", "git-worktree-add", "git-worktree-sync",
                           "git-worktree-remove", "git-rebase", "git-cherry-pick",
                           "git-switch", "git-switch-create",
                           "git-stage", "git-commit", "git-push-branch", "git-pr-create",
                           "pr-add-label", "git-delete-fork-branch"]
# Only in a policy whose [repos] upstream is the site repository / apache/magpie.
"release-announce-draft" = ["git-fetch", "git-worktree-add", "git-worktree-sync",
                            "git-worktree-remove", "git-rebase", "git-cherry-pick",
                            "git-switch", "git-switch-create",
                            "git-stage", "git-commit", "git-push-branch", "git-pr-create",
                            "pr-add-label", "git-delete-fork-branch"]
"setup-upstream-fix"    = ["repo-issue-search", "repo-pr-search", "repo-issue-view", "pr-view",
                           "git-fetch", "git-worktree-add", "git-worktree-sync",
                           "git-worktree-remove", "git-rebase", "git-cherry-pick",
                           "git-merge-upstream", "git-switch", "git-switch-create", "git-stage", "git-commit",
                           "git-push-branch", "git-pr-create", "pr-add-label",
                           "git-delete-fork-branch"]
"setup-override-upstream" = ["git-fetch", "git-worktree-add", "git-worktree-sync",
                             "git-worktree-remove", "git-rebase", "git-cherry-pick",
                             "git-merge-upstream", "git-switch", "git-switch-create", "git-stage", "git-commit",
                             "git-push-branch", "git-pr-create", "pr-add-label",
                             "git-delete-fork-branch"]
"security-issue-import" = ["issue-list-with-bodies", "issue-create-labeled", "rollup-append",
                           # Step 7: put the new tracker on the board in Needs triage.
                           "board-item", "board-add-item", "board-set-status",
                           # Rejections-ledger records for reject-without-tracker dispositions.
                           "issue-comment",
                           # Fold-ins: add an independent finder to an existing tracker's credit.
                           "body-field-get", "body-field-set",
                           # Receipts for reports relayed from a GitHub Security Advisory.
                           "advisory-comment",
                           # Step 1: read a GHSA-relayed report and its discussion.
                           "advisory-view", "advisory-comments",
                           # Step 2a: the duplicate search and its follow-up reads.
                           "issue-search", "issue-view",
                           # Step 2c: an upstream PR that already fixes the report.
                           "repo-pr-search"]
"security-issue-import-from-scan" = [
                           # Step B: the open-tracker list, the duplicate and precedent
                           # searches, and their follow-up reads.
                           "issue-list-with-bodies", "issue-search", "issue-view",
                           # Step B: the fix-already-public / fixed-since-the-scan check.
                           "repo-pr-search", "pr-view", "pr-diff", "compare",
                           # Step F: a finding's candidate patches, on its new tracker.
                           "issue-comment"]
"security-issue-import-from-md" = ["issue-create-labeled", "rollup-append"]
"security-issue-import-from-pr" = ["pr-view-with-body", "issue-create-labeled", "rollup-append"]

# Non-GitHub tracker additions, per import caller.
# Add these to the corresponding existing caller array; preserve base grants.
#
# security-issue-import:
#   jira: tracker-doctor, issue-search, issue-list, issue-list-label,
#         issue-view, issue-comments, issue-comment, issue-create,
#         issue-body, issue-attach
#   local-files: same as jira, plus tracker-pending, tracker-publish
#
# security-issue-import-from-md:
#   jira: tracker-doctor, issue-search, issue-view, issue-create,
#         issue-body, issue-attach
#   local-files: same as jira, plus tracker-pending, tracker-publish
#
# security-issue-import-from-pr:
#   jira: tracker-doctor, issue-search, issue-view, issue-create,
#         issue-set-milestone, issue-body, issue-attach
#   local-files: same as jira, plus tracker-pending, tracker-publish
#
# These are conditional additions, not universal grants.
# issue-list-with-bodies works only with GitHub. The email importer must
# stop on Jira/local-files when this deduplication step is unsupported;
# never bypass the refusal or assume that unmatched reports are new.
#
# Other security callers (sync, fix, CVE allocation, deduplication,
# triage and invalidation) also require their own backend grants.
# Setup derives those from each workflow and the security-tracker contract,
# preserving existing grants and requesting explicit confirmation.
# Do not duplicate TOML keys or grant every operation to every caller.
"security-issue-invalidate" = ["rollup-append", "rollup-amend-latest",
                               # The closing comment on a GHSA-relay-only report.
                               "advisory-comment"]
"security-issue-triage" = ["issue-view", "issue-comments",
                           # Step 1: the `needs triage` queue, and the CVE selector.
                           "issue-list-label", "issue-search",
                           # Step 2: linked and independent upstream fixes.
                           "repo-pr-search", "repo-code-search",
                           # Step 6: the confirmed triage-proposal comment.
                           "issue-comment"]
"security-issue-deduplicate" = ["rollup-append", "rollup-fold",
                                # item 6: regenerate the kept tracker's JSON block.
                                "issue-view", "collaborators", "issue-edit-body"]
"dependency-vulnerability-audit"      = ["osv-query-package", "osv-query-commit", "osv-query-batch"]
"pr-management-triage"  = ["pr-list", "pr-view", "pr-checks", "gql-pr-liveness",
                           "gql-pr-triage-open", "gql-pr-triage-label", "gql-pr-triage-author",
                           "gql-pr-triage-review-requested", "gql-pr-triage-one", "gql-pr-triage-preflight",
                           "gql-main-recent-failures", "runs-action-required", "runs-at-head", "check-runs",
                           "compare-behind", "team-members", "upstream-permission", "viewer",
                           "pr-view-with-body", "pr-triage-recovery-state", "pr-triage-comment-receipt",
                           "pr-add-label", "pr-remove-label", "pr-draft", "pr-ready",
                           "pr-comment", "pr-update-branch", "run-rerun-failed",
                           "workflow-approve"]
"pr-management-code-review" = ["viewer", "upstream-permission", "pr-review-context",
                               "pr-files", "pr-diff", "pr-comments", "pr-reviews",
                               "pr-checks", "pr-list", "pr-list-label",
                               "pr-search-review-requested", "pr-search-mentions",
                               "pr-search-reviewed-by", "pr-search-team-review-requested",
                               "commits-by-path", "repo-file", "label-list",
                               "gql-pr-review-threads", "team-members", "gql-pr-liveness", "gql-cr-open", "gql-cr-pr", "gql-cr-pr-stack", "cr-codeowners-github", "cr-codeowners-root", "cr-codeowners-docs", "cr-pr-template", "cr-viewer-commits", "cr-commit-files", "cr-path-commits", "cr-commit-pulls",
                               "pr-review-approve",
                               "pr-review-request-changes", "pr-review-comment",
                               "runs-at-head", "workflow-approve", "run-rerun",
                               # The head commit's check runs, read before an APPROVE to confirm real CI
                               # ran there (code-review disposition's secondary check, #2072).
                               "check-runs",
                               # FIXUP disposition: a worktree at the PR head, commit the fixups,
                               # fast-forward the PR's head branch.
                               "git-worktree-add", "git-worktree-remove",
                               "git-stage", "git-commit", "git-merge-upstream",
                               "git-push-pr-head"]
"pr-management-stats"   = ["viewer", "gql-pr-stats-open", "gql-pr-stats-closed-page",
                           "gql-pr-stats-closed-search", "team-members"]
"pr-management-merge-candidates" = ["viewer",
                               "gql-pr-triage-preflight",
                               "gql-pr-express-ready",
                               "gql-pr-express-one",
                               "pr-live-state",
                               "gql-pr-review-decision",
                               "runs-action-required",
                               "pr-diff"]
"pr-stale-sweep" = ["gql-pr-stale-open",
                    "gql-pr-stale-label",
                    "gql-pr-stale-one",
                    "team-members",
                    "upstream-permission"]
"pr-management-stack-review" = ["viewer",
                                "upstream-permission",
                                "gql-stack-of-pr",
                                "gql-stack-scan",
                                "gql-pr-by-head",
                                "pr-checks",
                                "pr-comments"]
"pr-management-thread-mentor" = ["viewer",
                          "repo-issue-view",
                          "pr-view-with-body",
                          "pr-comments",
                          "team-members",
                          "upstream-permission"]
"reviewer-routing" = ["pr-view-with-body",
                      "repo-issue-view",
                      "commits-by-path",
                      "pr-search-review-requested",
                      "repo-file"]
"issue-triage"          = ["repo-issue-view", "repo-issue-comments", "repo-issue-list",
                           "repo-issue-add-label", "repo-issue-remove-label",
                           "repo-issue-comment"]
"issue-stale-sweep"     = ["repo-issue-list", "repo-issue-view", "repo-issue-comment",
                           "repo-issue-close", "repo-issue-reopen"]
"issue-backlog-stats"   = ["repo-issue-list"]
"license-compliance-audit" = ["repo-view", "repo-tree", "repo-file"]
"flaky-test-triage"     = ["run-list", "run-view", "pr-view"]
"release-verify-rc"     = ["release-list", "release-view", "tags", "repo-file"]
"release-rc-cut"        = ["tags", "repo-issue-comment"]
"contributor-nomination" = ["user-profile", "pr-list", "repo-issue-list"]
"mentoring-welcome"     = ["repo-issue-view", "repo-issue-comment", "pr-view"]
```

`mentoring-welcome` needs no operation of its own: it works on upstream issues
and PRs, which the issue and PR families already cover. A family earns new
operations only when it has a shape the catalogue lacks.

**A second policy, for the security records site.** A project that publishes its
security records to a site repository through pull requests
([`advisory_records`](https://github.com/apache/magpie/blob/main/docs/security/advisory-records.md#publishing-through-a-pull-request))
gives that repository its own policy, so the project's policy never names a second
repository to push to. It lives in the site checkout's personal layer
(`<site checkout>/.git/apache-magpie/tools/vetted-ops/config.toml`), is approved
like any other (a copy in `~/.config/apache-magpie/vetted-ops/`), and grants
`security-issue-sync` the git steps of the records pull request and nothing else;
`security-issue-sync` names it with `--policy-from <site checkout>` on every call.
Only in a policy whose `[repos] upstream` is that site repository:

```toml
workspace = "/tmp/agent-scratch"

[repos]
upstream = "acme/product-site"

[git]
pr_base = "main"
# The pull request adds a published record, which names its identifier: the one
# term git-pr-create lets through here. Never in the source repository's policy.
published_terms = ["CVE id", "CVE"]
# ...and only for a branch that changes nothing outside the records directory.
published_paths = ["content/security/json"]
# Optional, a records-site policy only (one with published_paths): the site's own hooks
# (.pre-commit-config.yaml) cannot run in the sandbox, which cannot read the site checkout's
# .git; "skip" lets vetted-op-checks --skip-site-hooks record them as skipped. A records pull
# request changes only the files under published_paths, and the site's CI runs the hooks on it.
# Unset (the default): vetted-op-checks refuses, and the skill hands over the commands instead.
# site_hooks = "skip"

[callers]
# Only in a policy whose [repos] upstream is the advisory_records site repository.
"security-issue-sync" = [# The site's current records at the base branch, read from the forge
                         # (the sandbox cannot read the site checkout).
                         "repo-file", "repo-tree",
                         "git-fetch", "git-worktree-add", "git-worktree-remove",
                         "git-stage", "git-commit", "git-push-branch", "git-pr-create",
                         "git-delete-fork-branch"]
```

**Patterns for milestones a project mints on a schedule.** `milestones` can
gain a sibling `milestones_patterns` list of regular expressions. A milestone
parameter then accepts a listed value or one that a pattern matches *in full*
(`fullmatch`, so `Providers 2026-11-17 extra` does not pass). A project that
cuts a dated milestone every release wave declares its shape once instead of
editing and re-approving the policy for each wave. A pattern-matched value must
also be a plain name: 1 to 100 characters, no leading or trailing space, the
plain space as its only whitespace, no `,` `"` or `\`, and no Unicode control,
format or line-separator character, whatever the pattern allows. The patterns
are checked when the policy loads: one that does not compile, or that matches
the empty string (`.*`, `''`), is refused, so a pattern is always a real
constraint. The milestone list may be replaced entirely by its patterns. No
other list takes patterns, and the policy refuses one that tries: labels reach
`gh` list flags and search qualifiers, and logins have their own format check,
so both stay listed by name.

Grant the narrowest set that lets a skill finish its job: `pr-management-stats`
is a read-only dashboard, so it gets no write operation at all, and a
prompt-injection payload in a PR title cannot talk it into one.

The policy *contents* are never supplied on the command line: no flag adds a
repo, a caller, or an operation. What `--config` selects is *which policy file*
applies, so a caller's reach is bounded by the policy files that already exist
on disk and by who may write them — not by the absence of a flag. The `deny`
rules and the file's location are what close that surface; see
[Wiring it into settings](#wiring-it-into-settings), which points `--config` at
a policy outside the sandbox-writable root on purpose.

**Only `vetted-op-read` takes `--config` for an operation that runs.**
`vetted-op` and `vetted-op-tracker` run outside the sandbox, so a policy they
act on must be one the agent cannot write. An agent-written policy could set
`workspace` to a private directory such as `~/.ssh` (owned by you and mode 0700,
so it passes the workspace check) and post a key from it as a comment on a
repository it chose. So they refuse `--config`, and they act on the discovered
policy — `.apache-magpie-overrides/tools/vetted-ops/config.toml`, else a
personal-layer copy — **only when it is byte-for-byte a copy you placed in
`~/.config/apache-magpie/vetted-ops/`**. Discovery starts from the working
directory, which the agent picks, and a directory renamed into place gets past
any deny glob; the approved directory is outside every sandbox-writable root and
`Edit`-denied, so nothing the agent can do puts a policy there. A planted copy of
an approved policy gains nothing. Approve a policy in your own terminal, after
reviewing it, and again after every change:

```bash
mkdir -p ~/.config/apache-magpie/vetted-ops && cp .apache-magpie-overrides/tools/vetted-ops/config.toml ~/.config/apache-magpie/vetted-ops/<project>.toml
```

`<project>` is the project's slug: `short_name` in its `project.md`, lowercased,
or the basename of the main checkout when there is no `project.md` (`foo.toml`).
Only a plain slug is used (lowercase letters, digits, `-` and `_`), else `policy.toml`:
both sources are text the agent can write, and the name lands in a `cp` you run.
The write dispatchers print their refusal with this name filled in, and a skill that renders the command does the same, since it cannot list the directory.
Any `.toml` name approves except `operator-git.toml`, which holds the operator's `[git]` table;
the fixed name only makes each approval replace the stale copy instead of adding one beside it.
A stale copy approves nothing, so an earlier one under another name is clutter to delete, not a risk.

The home directory comes from the password database, not `$HOME`, and so does a
`~` in the policy's `workspace`. Every policy file and every body is opened one
path component at a time without following symlinks, so the file read is the
file checked. The `workspace` itself must not run through a symlink either: an
approved policy is the user's, but the directory it names is not, and one
swapped for a link to a private directory such as `~/.ssh` (yours, mode 0700)
would otherwise pass the workspace checks and turn its files into bodies. Name
the workspace by its real path (on macOS, `/private/tmp/…` rather than `/tmp/…`).
`--dry-run`, `policy` and `list-ops` need neither approval nor discovery, and
still accept `--config`: they publish nothing. `vetted-op-read approval-status`
reports whether the discovered policy is approved (see
[Is the policy approved?](#is-the-policy-approved)).

When a repo holds more than one policy, bind the flag in the permission rule so
the grant names the policy it was reasoned about:

```jsonc
"allow": [
  "Bash(… vetted-op-read --config .apache-magpie-overrides/tools/vetted-ops/config.toml *)"
]
```

`upstream` is required; **`tracker` is optional**. A project whose skills only
touch public work has no tracker to name, and requiring one would fail every
operation at load time over a value most of them never read — including
upstream-only reads like `viewer` and `pr-diff`. Omit it and those keep working;
an operation that addresses the tracker refuses by name instead:

```text
vetted-op: refused: this operation addresses the tracker, which the policy
does not configure. Declare `tracker` under [repos] to enable it;
upstream-only operations are unaffected.
```

The refusal happens in the builder, before any argv exists, so a tracker
operation can never fall back to `upstream` — which is the outcome that would
matter, since it would publish embargoed content to a public repository.
*Absent* is allowed; *present but malformed* is still a load error, because a
typo'd repo points operations somewhere unintended.

## CLI

```bash
vetted-op list-ops                          # the catalogue
vetted-op policy                            # resolved policy, as JSON
vetted-op --caller <name> <operation> [param …]
vetted-op --caller <name> <operation> [param …] --dry-run   # print argv, run nothing
```

Exit codes: `0` ok, `2` usage, `3` refused by policy or validation, `4` the
underlying command failed.

### Where do the dispatchers start from?

```bash
uvx --from ~/.claude/magpie/vetted-ops vetted-op-read source
# {"stable": "~/.claude/magpie/vetted-ops", "kind": "plugin", "resolves_to": "/Users/me/.claude/plugins/cache/apache-magpie/magpie-vetted-ops/0.9.0/tools/vetted-ops"}
```

Every skill launches the dispatchers from `~/.claude/magpie/vetted-ops`, and what that path is depends on how Magpie is installed:

| Install | `~/.claude/magpie/vetted-ops` | `kind` |
|---|---|---|
| Marketplace | a link into the `magpie-vetted-ops` plugin's cache, kept by its session hook | `plugin` |
| Pinned snapshot | a real copy of `<snapshot-dir>/tools/vetted-ops`, made by `setup` and refreshed by `setup update` | `copy` |
| Framework checkout | a link into the main checkout's `tools/vetted-ops`, made by `setup`'s self-adoption | `checkout` |

The plugin cache and a copy sit under `~/.claude`, which the sandbox cannot write.
A checkout link runs code the agent can edit, outside the sandbox, so agent-guard asks before every launch through one, `vetted-op-read` included.
The plugin's hook moves only a link into its own cache; a copy or a checkout link is left alone.
`source` prints that path's `kind` and where it resolves (`missing` when nothing is there); like `approval-status`, it takes no option or parameter and never prompts.

### Is the policy approved?

```bash
uvx --from ~/.claude/magpie/vetted-ops vetted-op-read approval-status
# {"policy": "/work/repo/.apache-magpie-overrides/tools/vetted-ops/config.toml", "approved": false, "approved_dir": "/Users/me/.config/apache-magpie/vetted-ops"}
```

`approval-status` tells a sandboxed session whether the write entry points would act on the policy it works with.
After a policy change merges, the approved copy is stale until the user copies the policy again, and the first write is refused;
the sandbox cannot read `~/.config/apache-magpie/`, so without this subcommand a skill cannot see that coming.
It discovers the policy from the working directory exactly as `vetted-op`, `vetted-op-tracker` and `vetted-op-git` do, and compares it byte for byte with the approved copies, as they do.
It prints one JSON object and nothing else: `policy` (the discovered path, or `null` when there is none), `approved` (`true` only when an approved copy matches) and `approved_dir`.

- It never prints a file's content, parses nothing and runs nothing, so it needs no approval itself.
- It takes no `--config`, `--caller`, `--save`, `--dry-run` or parameter; any of them is a usage error (exit `2`).
  Discovery only: an explicit path would let it probe whether an arbitrary file exists or matches an approved policy.
- A symlink on the committed policy path is refused (exit `3`), as on the write entry points.
- It exists on `vetted-op-read` only, which is allowlisted and excluded from the sandbox, so the check never prompts.

When `approved` is `false`, the user reviews the policy and approves it again in their own terminal, with the command under [Configuration](#configuration).

### Saving a read instead of printing it

```bash
vetted-op-read --caller pr-management-triage --save triage-pages.json gql-pr-triage-open
# {"saved": "/tmp/agent-scratch/saved/triage-pages.json", "bytes": 482113}
```

`--save NAME` writes a **read** operation's output to `<workspace>/saved/NAME`
and prints one JSON line instead of the output itself. It exists for reads too
large to carry through the caller's context — a full triage sweep is hundreds of
kilobytes — which a deterministic tool then reads from the file.

- Only reads: a write, or a procedure, with `--save` is refused.
- `NAME` is one path component (`[A-Za-z0-9][A-Za-z0-9._-]*`, at most 100
  characters).
- **`--save` never widens what the caller can write.** `vetted-op-read` runs
  outside the sandbox and `--config` can name any policy file, including one
  the agent wrote, so the policy's `workspace` proves nothing about who may
  write there. `--save` therefore writes only into a `<workspace>/saved/`
  directory that **already exists and holds a regular `.vetted-ops-save`
  file** — it creates neither. Whoever made them, you or a sandboxed agent
  inside its own writable roots, could already write there. Create them once:

  ```bash
  mkdir -p -m 700 <workspace>/saved && touch <workspace>/saved/.vetted-ops-save
  ```

- The workspace passes the same ownership and mode checks as for body files;
  `saved/` must be yours and closed to group and world. The output goes to an
  exclusively created temporary file, written `0600`, then renamed over `NAME`,
  so a symlink or hard link planted under that name is replaced, never written
  through. Every path is opened with `O_NOFOLLOW` relative to the checked
  workspace.
- An HTTP read saved this way still never touches any other path.
- **Old saved reads are pruned.** Saved reads carry tracker and pull-request
  text, and the workspace outlives the session, so each `--save` also removes
  entries of `saved/` older than `saved_retention_days` (under `[values]`; a
  whole number of days, default 7). Only regular files and symlinks you own
  are removed, relative to the same `saved/` descriptor and without following
  a link; the marker, dot-files, subdirectories and the file just written stay.

### Searching the upstream repository

```bash
vetted-op-read --caller security-issue-triage repo-pr-search "credentials redirect"
vetted-op-read --caller security-issue-triage repo-code-search "IMAP_SOURCE_SSL"
```

| Operation | Kind | Parameters | Notes |
|---|---|---|---|
| `repo-pr-search` | read | `query` | `gh search prs` on the policy-pinned upstream, open and closed, up to 100 results. |
| `repo-issue-search` | read | `query` | `gh search issues` on the policy-pinned upstream, open and closed, issues only (no pull requests), up to 100 results. |
| `repo-code-search` | read | `query` | `gh search code` on the upstream default branch; returns paths and URLs only. |

Free-text search is otherwise kept out of the catalogue. These three, like the
tracker's `issue-search`, are bounded: the repository comes from policy, and the
`query` is plain words — one line, at most 200 characters, no `:` (so no
`repo:` / `org:` / `is:` qualifier can re-aim or reshape it), no leading `-`, and
passed after `--`. They let a read-only gatherer check whether something was
already fixed upstream without a raw `gh search` outside the dispatcher.
Grant them per caller like any other operation.

### The Vulnogram CVE-tool operations

The ASF CVE tool's client, `vulnogram-api-*`, reads an OAuth session from
`~/.config/apache-magpie/`, which the sandbox denies, so a sandboxed agent could
only hand each push or allocation to the user. Excluding the client from the
sandbox as it is would also hand over its flags: `--credentials` (a session
file the agent wrote, naming a host of its choosing) and the
`--allow-state-downgrade` / `--allow-product-change` / `--replace-references`
overrides. Three operations run it instead, outside the sandbox through
`vetted-op`, with a fixed argv:

| Operation | Parameters | Runs |
|---|---|---|
| `cve-record-fetch` (read) | `cve_id` | `vulnogram-api-record-fetch --cve-id <id>` |
| `cve-record-update` (write) | `cve_id body` | `vulnogram-api-record-update --cve-id <id> --json-file -`, the record on stdin |
| `cve-allocate` (write) | `pmc title` (title a workspace file) | `vulnogram-api-allocate --pmc <pmc> --title <title>`; the client refuses a token held for another PMC |

- The client is the copy shipped in this plugin beside vetted-ops
  (`tools/cve-tool-vulnogram/oauth-api`, resolved like the tracker backends),
  never a path the agent can write.
- The record travels on stdin as the bytes vetted-ops read from the workspace,
  so no second open can swap them. None of the override flags is reachable, so
  the record commands' merge-mode guards always apply.
- The child gets an allowlisted environment: `HOME` from the password
  database, `PATH` set to the directory of the absolute `uv` binary followed by
  the system directories, plus locale. No `VULNOGRAM_*` session override, no
  `PYTHON*`, `UV_*`, `DYLD_*` or `LD_*` variable and no `TMPDIR` (sandbox-writable
  inside the harness, and where uv builds) reaches it, so the session is always
  the user's own default file and nothing the caller exports changes what Python
  or uv load.
- `cve-record-update` parses the record before it is sent and refuses it unless
  its `cveMetadata.cveId` is the target id (the client posts to `--cve-id`
  whatever the document says), and refuses a top-level `go` key, which Vulnogram
  reads as a request envelope rather than record content.
- Publishing (`vulnogram-api-record-publish`) has no operation. It is the
  release manager's terminal step and stays a hand-run command. For the same
  reason `cve-record-update` always passes `--no-promote-to-public`: a push
  that would move `CNA_private.state` to `PUBLIC` from any other state
  (including a first push) is refused, while re-pushing a record that is
  already `PUBLIC` is unaffected.

Grant them to the callers that push records or allocate:
`cve-record-fetch` and `cve-record-update` to `security-issue-sync` and
`security-cve-allocate`, and `cve-allocate` to `security-cve-allocate`. The
user still runs `vulnogram-api-setup` once per login session to approve the
tokens; nothing here can mint one.

### The project board

A GitHub-backed tracker can keep a Projects V2 board, one `Status` column per lifecycle state.
The board's node id, its `Status` field id and the column → option-id map come from the policy
(`board_project_id`, `board_status_field_id`, `[values.board_columns]`); an operation run under a
policy without them is refused by name.

| Operation | Kind | Parameters | What it does |
|---|---|---|---|
| `board-item` | read | `number` | One tracker issue's node id, and its item on the configured board, archived ones included: `{node_id, item}` with `item` `null` when the issue is not on the board, else `{item_id, status, archived}`. |
| `board-items` | read | — | Every item still on the board, every page, one JSON line each: `{item_id, type, repo, number, state, labels, status}`. The sweep uses it to find anything that is not a security tracker. |
| `board-add-item` | write | `content_id` | Add an issue (by its node id, from `board-item`) to the board; returns the item id. Idempotent. |
| `board-set-status` | write | `item_id column` | Move an item to a configured column. |
| `board-archive-item` | write | `item_id` | Archive an item off the board (a closed tracker). Idempotent. |

`security-issue-sync` reads `board-item` for each tracker it syncs and, on confirmation, adds a
missing item, moves it to the column its labels call for, and archives it once the tracker is closed;
its end-of-sync sweep also reads `board-items` and archives anything that is not a security tracker
([`tools/github/project-board.md`](https://github.com/apache/magpie/blob/main/tools/github/project-board.md)).

### The pr-management-triage reads

| Operation | Parameters | Returns |
|---|---|---|
| `gql-pr-triage-open` | — | every open PR, every page (`--paginate --slurp`), in the triage shape of [`queries/pr-triage-search.graphql`](src/vetted_ops/queries/pr-triage-search.graphql) |
| `gql-pr-triage-label` | `label` (policy `upstream_labels`) | the same, narrowed to one label |
| `gql-pr-triage-author` | `login` | the same, narrowed to one author |
| `gql-pr-triage-review-requested` | `login` | the same, narrowed to a requested reviewer |
| `gql-pr-triage-one` | `number` | one PR in the same shape |
| `gql-pr-triage-preflight` | — | the viewer's login and permission on the upstream repo, and every label name (all pages) |
| `gql-main-recent-failures` | — | the check contexts of the ten most recently merged PRs |
| `runs-action-required` | — | every run awaiting approval, every page |
| `check-runs` | `commit_hash` | every check run on one commit, every page |
| `runs-at-head` | `commit_hash` | every workflow run on one head commit, every page — the pre-mutation guards' read |
| `compare-behind` | `base head` | `{base, behind_by, ahead_by}` |
| `team-members` | `team` (slug; org from policy) | one login per line |

The search string is built by the operation, `repo:<upstream>` first, so the
selector parameter narrows a sweep and cannot re-aim it.

### The other pr-management reads

| Operation | Parameters | Returns | Skill |
|---|---|---|---|
| `gql-pr-express-ready` | `label` (policy `upstream_labels`) | the open PRs carrying that label in the triage shape plus each PR's changed files, every page | quick-merge |
| `gql-pr-express-one` | `number` | one PR in the same shape | quick-merge |
| `gql-pr-review-decision` | `number` | review decision, approvals so far, and the base branch's required approving-review count | quick-merge |
| `pr-live-state` | `number` | live `{number, head_sha, mergeable, mergeable_state}` (REST computes mergeability on demand) | quick-merge |
| `gql-pr-stale-open` | — | every open, non-draft PR in the pr-stale-sweep shape (raw comment bodies), all pages | pr-stale-sweep |
| `gql-pr-stale-label` | `label` (policy `upstream_labels`) | the same, narrowed to one label | pr-stale-sweep |
| `gql-pr-stale-one` | `number` | one PR in the same shape | pr-stale-sweep |
| `gql-stack-of-pr` | `number` | the stack a member PR belongs to, every entry | stack-review |
| `gql-stack-scan` | — | every open PR's stack number, all pages | stack-review |
| `gql-pr-by-head` | `head` | open PRs whose head is one branch (the trunk walk) | stack-review |
| `gql-cr-open` | — | every open PR in the code-review queue shape, all pages | code-review |
| `gql-cr-pr` | `number` | one PR's review context: headline, files, threads, reviews, checks, and whether the repository and viewer can enable auto-merge | code-review |
| `gql-cr-pr-stack` | `number` | the stack a PR belongs to, for stacked-layer reviews | code-review |
| `cr-codeowners-github` | — | `.github/CODEOWNERS` from the default branch | code-review |
| `cr-codeowners-root` | — | `CODEOWNERS` at the repository root | code-review |
| `cr-codeowners-docs` | — | `docs/CODEOWNERS` | code-review |
| `cr-pr-template` | — | the repository's pull-request template | code-review |
| `cr-viewer-commits` | `login date ref` | the viewer's commits on the base branch since a date | code-review |
| `cr-commit-files` | `commit_hash` | the files a commit touched | code-review |
| `cr-path-commits` | `path` | the commits that touched a path | code-review |
| `cr-commit-pulls` | `commit_hash` | the merged PRs a commit belongs to | code-review |

### The pr-management-stats reads

| Operation | Parameters | Returns |
|---|---|---|
| `gql-pr-stats-open` | — | every open PR, every page, in the dashboard shape of [`queries/pr-stats-open.graphql`](src/vetted_ops/queries/pr-stats-open.graphql) |
| `gql-pr-stats-closed-page` | `cursor` (opaque base64, or `start`) | one page (50) of closed and merged PRs, newest update first — the default closed path, outside the search index; `pr-management stats build` names the next cursor until a page predates the cutoff |
| `gql-pr-stats-closed-search` | `date` (strict `YYYY-MM-DD`) | closed and merged PRs since the date through the search index, every page — the `fast-closed` opt-in, capped at 1000 |

The open sweep carries each PR's changed files (for the CODEOWNERS panel); the committers roster comes from `team-members`.

## Tracker procedures: rollup and body-field writes

The status rollup and the `### Field` sections of a tracker issue body are
read-modify-write updates: the write depends on what a read returned. The
[`github-rollup`](https://github.com/apache/magpie/blob/main/tools/github-rollup/README.md) and
[`github-body-field`](https://github.com/apache/magpie/blob/main/tools/github-body-field/README.md) tools do them without
bringing the rollup or the body into agent context, but they call `gh` from a
`uv run` subprocess, which under the secure setup stays sandboxed and fails.
These operations are the same procedures as reviewed catalogue entries:

| Operation | Kind | Parameters | Same as |
|---|---|---|---|
| `rollup-append` | write | `number action body` | `github-rollup append` |
| `rollup-amend-latest` | write | `number action body` | `github-rollup amend-latest` |
| `rollup-fold` | write | `number comment_id action` | `github-rollup fold` |
| `body-field-set` | write | `number field value` | `github-body-field set` |
| `body-field-get` | read | `number field` | `github-body-field get` |

```bash
uv run --project ~/.claude/magpie/vetted-ops vetted-op-tracker --caller security-issue-sync rollup-append 212 "Sync" <workspace>/entry.md
uv run --project ~/.claude/magpie/vetted-ops vetted-op-tracker --caller security-issue-sync rollup-amend-latest 212 "Sync" <workspace>/entry.md
uv run --project ~/.claude/magpie/vetted-ops vetted-op-tracker --caller security-issue-sync rollup-fold 212 2890012345 "Legacy status"
uv run --project ~/.claude/magpie/vetted-ops vetted-op-tracker --caller security-cve-allocate body-field-set 212 "CVE tool link" <workspace>/value.md
uv run --project ~/.claude/magpie/vetted-ops vetted-op-read --caller security-issue-sync body-field-get 212 "Severity"
```

Skills run the four writes through **`vetted-op-tracker`**, a third entry point
that refuses every operation except these procedures before it reads the policy,
the same way `vetted-op-read` refuses writes. That is what lets it be excluded
from the sandbox — the writes need a `gh` that can verify TLS — while `vetted-op`
is not: its catalogue is closed to tracker-only procedures whose runner refuses
any `gh` call outside `repos/<tracker>/`. It stays in `ask`, so every write still
prompts. `vetted-op` can run the same operations, but only inside the sandbox.

- `body` and `value` are body files, read from the workspace like any other body.
- `action` is one printable line of 1-80 characters, with no leading `-` and no
  `<`, `>` or `·` (the summary-line separator); `field` is a heading name of
  1-80 characters with no leading `-` and no `#`.
- `rollup-append` attributes the entry to the authenticated `gh` login and today's
  UTC date, and creates the rollup (marker line `<!-- apache-magpie: status-rollup v1 -->`)
  when the issue has none. It finds the rollup by that marker first, then by the
  legacy `<!-- <name> status rollup v<N>` marker, so a tracker carrying both keeps
  growing the canonical one.
  Only a comment by the authenticated `gh` login or a tracker collaborator
  (`gh api repos/<tracker>/collaborators`) counts as the rollup, for every rollup
  operation; a marker line in anyone else's comment is ignored. When the
  collaborator list cannot be read, only the authenticated login's comments count,
  and an existing rollup by anyone else makes the operation refuse rather than
  start a second one.
- `rollup-amend-latest` refuses unless the latest entry's action equals `action`,
  so a concurrent entry by someone else is never overwritten.
- `rollup-fold` keeps the legacy comment's date and author, left-trims its lines,
  refuses the rollup itself and a comment belonging to another issue, and deletes
  the legacy comment only after the append succeeded.
- `body-field-set` refuses when the field is absent or appears more than once, and
  writes nothing when the value is unchanged.
- Only a one-line summary reaches stderr. On stdout, `body-field-get` prints the one value, and `rollup-append` / `rollup-amend-latest` print the rollup comment's URL (`…#issuecomment-<id>`) so a caller can link to it without reading the rollup.
  Refusals exit `3`, a failed `gh` call exits `4`.
- `--dry-run` runs the reads (the plan depends on them) and prints each write
  instead of running it, with any body reported by size, never by content.

The parsing and composing code is vendored byte-for-byte from the two tools
(`rollup_format.py`, `body_field_format.py`), because the dispatcher installs as a
copy of its own directory and cannot import them; a test fails if a copy drifts
from its source.

## Batches of private-tracker writes

A bulk run (an import of a dozen reports, a bulk sync) makes dozens of tracker writes, and each vetted call is one permission prompt.
When the approved policy turns batching on, a skill writes those writes into one manifest and the user confirms them once.
Design and trade-offs: [the batch design note](https://github.com/apache/magpie/blob/main/docs/designs/2026-11-26-vetted-ops-batch-tracker-writes.md).

```toml
[approval]
# each  — the default: every tracker write prompts on its own; the batch entry point refuses.
# batch — a checked manifest of private-tracker writes runs under one prompt.
# none  — as batch, and the adopter allows vetted-op-tracker-batch-unprompted without a prompt.
private_tracker_writes = "batch"
```

There are two batch entry points, so that an unprompted run can never act on a policy whose adopter asked for a prompt:

| Entry point | Runs a policy set to | Permission |
|---|---|---|
| `vetted-op-tracker-batch` | `batch` or `none` | `ask`, always |
| `vetted-op-tracker-batch-unprompted` | `none` only; refuses anything else before it reads the manifest | `ask` by default; `allow` only where the adopter chose `none` |

Without the split, an `allow` written for a `none` project would also run, unprompted, the policy of any other approved project the caller selects with `--policy-from` or `cd`, including one set to `batch`.
`batch-check` and both batch scripts take `--policy-from <dir>` under the same rules as the single-call dispatchers:
only a checkout listed in your own `operator-git.toml`, compared as text before anything on disk is touched,
whose approved policy lists that checkout for its upstream.
Pass body files and the manifest as absolute paths with it.
Skills run `vetted-op-tracker-batch-unprompted` when the policy says `none`, and `vetted-op-tracker-batch` otherwise.

The manifest is a `.json` file in the workspace, written with the file-writing tool:

```json
{"version": 1,
 "ops": [{"op": "issue-add-label", "params": ["212", "needs triage"]},
         {"op": "rollup-append", "params": ["212", "Sync", "<workspace>/entry-212.md"]}]}
```

Each entry is one operation and its positional parameters, exactly as a single call takes them.
Then, each as a command line of its own:

```bash
uvx --from ~/.claude/magpie/vetted-ops vetted-op-read --caller security-issue-sync batch-check <workspace>/batch-sync.json
uv run --project ~/.claude/magpie/vetted-ops vetted-op-tracker-batch --caller security-issue-sync --expect <digest> <workspace>/batch-sync.json
```

1. `batch-check` runs nothing and never prompts.
   It checks every entry against the approved policy and prints one line per entry (bodies and file titles by size, never by content), then a JSON line with the `digest`.
   Show the user that summary as the proposal.
2. `vetted-op-tracker-batch` checks the manifest again, refuses unless its digest equals `--expect`, and runs the entries in order.
   The digest binds the destination as well as the content: the approved policy's hash, its tracker, tracker backend, board and resolved workspace,
   the manifest, every body and title file, and every entry's built command.
   A manifest checked under one policy is refused under another, and what runs is exactly what was summarised.
   It prints a header line per entry and each operation's own output (an `issue-create-labeled` prints `number`, `node_id` and `url`),
   then `{"batch": "done", …}`, or, at the first failure and with that operation's exit code,
   `{"batch": "stopped", "succeeded": [...], "unknown": <n>, "op": …, "not_run": [...]}`.
   Body and title files, and the manifest, are deleted only after every entry succeeded; after a stop all of them stay.
3. After a stop, the `unknown` entry's outcome is unknown: a write can land and still exit non-zero.
   **Read the tracker first** (`issue-view`, `issue-comments`, `board-item`, `body-field-get` through `vetted-op-read`) to see whether it took effect.
   Then write a new manifest with the `not_run` entries, plus the `unknown` one only if it did not take effect, check it, and show the user the new summary.
   Never rerun the old manifest: entries that succeeded would run twice.

The whole batch is refused, with nothing run, when any of these fails:
batching is on in the approved policy and the policy declares a tracker;
the manifest matches the schema (exactly `version` and `ops`, each entry exactly `op` and `params`, 1–200 entries);
every operation is a private-tracker write (`issue-create`, `issue-create-labeled`, the `issue-*` label, milestone, assignee, comment, body, title, close and reopen writes, `comment-update`, `milestone-create`, `milestone-close`, the four procedure writes, and `board-add-item`, `board-set-status`, `board-archive-item`);
the caller is granted every one of them;
every entry passes the same parameter checks and builder as a single call, and the built command addresses the tracker or the policy's board;
and, on GitHub, the tracker reports itself private and the board, when a board write is present, not public.
Public and outbound writes (`pr-*`, `repo-issue-*`, `advisory-comment`, `cve-allocate`, `cve-record-update`, `tracker-publish`, every `vetted-op-git` operation) are refused by name, even when granted: they keep their own confirmation.
No grant is needed for the batch itself; the caller needs the grants for the operations in it.

A batch cannot refer to a number an earlier entry creates.
A skill that creates trackers and then labels, boards or annotates them runs two batches: the creates, then the rest with the numbers the first one printed.

## Tracker backends

The security tracker need not be a GitHub repository.
The optional `[tracker]` table selects one of the backends of the
[security-tracker contract](https://github.com/apache/magpie/blob/main/tools/security-tracker/contract.md); with it, every
catalogue operation that addresses the tracker runs that backend's CLI instead
of its `gh` builder, and the skills keep calling the same operations:

```toml
[tracker]
platform = "local-files"                                  # github (default) | local-files | jira
root     = "/abs/path/to/the/repo/security/reports"       # the tracker folder

# platform = "jira"
# jira_url            = "https://issues.example.org/jira"
# jira_project        = "FOOSEC"
# jira_security_level = "Security Team"
# jira_issue_type     = "Bug"                             # default Bug
# jira_deployment     = "server"                          # server | cloud
# jira_rollup_authors = ["alice", "bob"]                  # whose rollup comment counts, beside the token's user
```

The guarantees above carry over, because the translation lives in reviewed code
([`tracker_backends.py`](src/vetted_ops/tracker_backends.py)), not in the policy:

- **The program and its code are fixed.** The backend runs from the tool
  directory installed beside vetted-ops itself — `tools/local-tracker` or
  `tools/jira` in a checkout, the same siblings inside the installed
  `magpie-vetted-ops` plugin — never from a path a policy names. Under
  `uvx --from` the module runs from a wheel in a cache the agent can write to,
  so the backend is then taken from beside the protected
  `~/.claude/magpie/vetted-ops` link instead. A policy can be
  picked with `--config`, so a policy that could name code would let whoever
  writes one run code through the allowlisted read entry point; a `project` key
  is therefore refused. The argv is `uv run --project <that dir> <script>`
  followed by the target and the translated subcommand.
- **The target is not addressable.** The tracker folder, or the Jira URL,
  project and security level, come from the policy, exactly as `[repos] tracker`
  does for `gh`.
- **Parameters stay parameters.** They are validated as before, placed as single
  argv elements, and run without a shell. Bodies are still read here and piped on
  stdin; the backend reads `-`.
- **No silent fallback.** A tracker operation with no counterpart on the backend
  — project boards, milestone administration, the collaborator roster,
  `comment-update`, `rollup-fold` — is refused by name. A test derives the set of
  tracker operations from the catalogue itself and fails if one is neither
  translated nor refused.
- **The backend's guard is a refusal here.** A backend exit `4` — its
  confidentiality guard, or an `amend-latest` mismatch — is reported as exit `3`.

The full mapping, from the `gh` shape in the skills to the vetted operation to
the backend subcommand, is in the contract's
[skill-command table](https://github.com/apache/magpie/blob/main/tools/security-tracker/contract.md#from-skill-commands-to-vetted-operations).
Eleven operations exist for it:

| Operation | Kind | Parameters | Notes |
|---|---|---|---|
| `issue-create-labeled` | write | `title body labels` | GitHub only: create a private tracker with a JSON array of policy-approved labels, applied atomically. `title` and `body` are paths to workspace files: the title is read and validated here, and the body travels on stdin. Returns `number`, `node_id`, and `url`. |
| `issue-create` | write | `title body` | GitHub: `gh api …/issues -f title=… -F body=@-`. |
| `issue-reopen` | write | `number` | |
| `issue-list-label` | read | `state label` | `issue-list` filtered by one configured label. |
| `issue-list-with-bodies` | read | none | GitHub tracker only: up to 1000 open and closed issues with bodies; requires an explicit caller grant. Use `--save` to keep confidential bodies out of model context. Unsupported on Jira/local-files. |
| `issue-search` | read | `query` | Plain words; a `:` is refused, so a `repo:` qualifier cannot re-target the search. |
| `issue-body` | read | `number` | Non-GitHub only: the body as markdown sections, for `generate-cve-json --stdin`. |
| `issue-attach` | write | `number file attachment` | Non-GitHub only: attach a workspace file under a plain name (no path, no `..`). |
| `tracker-doctor` | read | — | The backend's setup check; replaces the GitHub pre-flight (`gh api repos/<tracker>`, roster) on `local-files` and `jira`. |
| `tracker-pending` | read | — | `local-files` only: uncommitted changes and unpushed commits. |
| `tracker-publish` | write | `message` | `local-files` only: commit the tracker folder and push. Runs on `vetted-op-tracker`, outside the sandbox, because the push needs credentials. |

`tracker-publish` is the one non-procedure operation `vetted-op-tracker` admits.
On `github` every `tracker-*` operation refuses, and on `jira` `tracker-pending`
and `tracker-publish` do: those writes are visible as soon as they return.
On a non-GitHub tracker the `number` parameter of a tracker operation takes the
backend's own IDs (`SEC-0012`, `FOOSEC-12`, `2024-007-xss`): letters, digits,
`-` and `_` only, so an ID can never name a path.

## Git operations the sandbox blocks

These steps fail in a sandboxed session however the agent phrases them, and
used to end in a command the user pasted into their own terminal:

- **Pushing over SSH.** The sandbox routes network through an HTTP proxy, so an
  SSH transport gets no TCP at all, and a hardware key's touch prompt never
  reaches the user.
- **Moving a linked worktree** to a rebased or pushed commit. Harnesses keep
  `.git/worktrees/<name>/` read-only for worktrees the session did not create,
  so `git reset`, `git fetch` and `git rebase` in such a worktree stop half-way.
- **Adding or removing a linked worktree**, for the same reason.
- **Staging and committing in such a worktree**: both write its index and the
  shared object store, and a signed commit needs the user's key (its PIN and
  touch), which the sandbox does not reach.
- **Fetching over SSH**, for the same reason as pushing.
- **Rebasing a signed branch.** A rebase re-creates every commit it replays,
  so it signs each one with the user's key, which the sandbox does not reach;
  and the replayed commits can change paths the harness keeps read-only, such
  as `.claude/settings.json`.
- **Opening the pull request.** Raw `gh pr create` runs unconfirmed, and the
  publication guard refuses its text when it cannot read the body file.

`vetted-op-git` runs exactly those steps outside the sandbox, as closed
shapes, behind the harness's confirmation like `vetted-op`, so the whole path
from a change to an open pull request needs no sandbox bypass and no pasted
command, and every step is still confirmed by the user:

| Operation | Parameters | What it does |
|---|---|---|
| `git-push-branch` | `checkout branch target remote_branch expected` | Pushes local `branch`'s commit to `remote_branch` of the policy's `fork` or `upstream` repository, with `--force-with-lease=refs/heads/<remote_branch>:<expected>` and `--no-verify`. `expected` is the remote branch's current full SHA, or `new`. Run the pre-push checks in the sandbox first. |
| `git-delete-fork-branch` | `checkout branch expected` | Deletes `branch` on the policy's `fork` (never upstream, never a protected branch) once its pull request has merged: the forge (`gh api repos/<upstream>/pulls?head=<fork owner>:<branch>&state=closed`) must report a merged pull request against the upstream repository whose head is that branch at exactly `expected`. A squash or rebase merge leaves the branch out of the base's history, so the forge's answer is the check. The deletion is leased on `expected`, so a branch pushed to since the merge is kept. |
| `git-push-pr-head` | `worktree branch number head_repo head_branch expected` | The maintainer-fixup push: fast-forwards `head_branch` of `head_repo`, the head of upstream pull request `number`, from `expected` (its full SHA) to local `branch`'s commit. The caller names the destination so the confirmation shows it, and the forge (`gh api repos/<upstream>/pulls/<number>`) must report that same head. Refused unless the pull request is open against the upstream repository, its head is still `expected`, `branch` adds at most 10 commits on top of `expected` and none of them is a merge, except one of the upstream `pr_base` (fetched by the operation; see `git-merge-upstream`), whose upstream commits do not count towards the 10 (so no other local history goes along, and nothing of the contributor's is rewritten), and the head branch is not protected; a head in a contributor's fork also needs the author to allow edits from maintainers, and one on the upstream repository an `upstream_push` glob. Leased on `expected`, `--no-verify`; run the pre-push checks in the sandbox first. |
| `git-worktree-sync` | `worktree commit` | Moves a clean linked worktree's branch to `commit` with `git reset --keep`, and prints the commit it was on. |
| `git-rebase` | `worktree onto expected` | Rebases the clean topic branch checked out in `worktree` (never a protected one) onto `onto`, a full SHA on the upstream `pr_base`: the operation fetches `pr_base` itself, from the policy's URL, and checks `onto` against the commit that fetch returned, never against a remote-tracking ref a sandboxed fetch could also write. `expected` is the branch's current full SHA, so a branch that moved after the user approved the call is refused, and one that moves while the rebase starts is put back where it was. A branch with merge commits over `onto` is refused, since a rebase would flatten them. Signing follows the user's global git configuration, and when that signs commits, every commit replayed must already carry the user's good signature (`%G?` is `G`, verified here, outside the sandbox): one made through `git-commit` or signed by the user, never one the agent committed unsigned in the sandbox. A user who does not sign gets no signature from the rebase and no such check. No recorded resolution (`rerere`), stash, editor or hook takes part. On a conflict it aborts, leaves the branch where it was, and names the conflicting paths: start a fresh branch on `onto`, replay the commits one by one with `git-cherry-pick`, and make the one that conflicts again in the sandbox and commit it with `git-commit`. |
| `git-cherry-pick` | `worktree commit expected` | Replays one plain (non-merge) `commit` onto the clean topic branch checked out in `worktree` (never a protected one), at `expected`: the way to finish a rebase that conflicted, one commit at a time. Signing follows the user's global git configuration, and when that signs commits, `commit` must already carry the user's good signature, so an unsigned commit the agent made in the sandbox is never signed. No recorded resolution, editor or hook takes part. On a conflict it aborts and names the conflicting paths; a pick that landed on a branch or tip that moved after the checks is taken back off. |
| `git-merge-upstream` | `worktree onto expected pr` | Merges `onto`, a full SHA on the upstream `pr_base` (fetched by the operation, as for `git-rebase`), into the clean topic branch checked out in `worktree` (never a protected one), at `expected`: for a branch whose history must stay as it is, such as a contributor's pull request. The merge commit has a fixed message (`Merge <upstream> <pr_base> into <branch>`) and is signed per the user's configuration. When that signs commits, the commits the merge vouches for must already carry the user's good signature: with `pr` set to `none` (the user's own branch), every commit not on upstream; with `pr` a pull request number, only the commits on top of that pull request's head, which the forge must report as open against the upstream repository and the branch must build on. The contributor's own commits are theirs, already published, and never carry the user's signature. No recorded resolution, stash, editor, merge log or hook takes part. On a conflict it aborts and names the conflicting paths; a merge that landed on a branch or tip that moved after the checks is taken back off. A contributor's branch then goes back with `git-push-pr-head`. |
| `git-switch` | `worktree branch` | Switches a clean working tree (the main checkout or a linked worktree) to an existing local `branch`, with no hook. In the sandbox a switch fails half-way: the harness keeps `.claude/` settings, hooks and skills, the other harnesses' skill directories, `.mcp.json`, plugin manifests and the vetted-ops policy read-only (plus the policy's `harness_paths`), so git updates everything else and leaves those as local changes. Out here it can write them, so `branch` must not have changed any of them in its own commits: its version of every such file must be upstream's from where it left `pr_base`. Any branch that left them alone switches, however old. The upstream commit is asked of the policy's upstream URL during the call, never read from a local ref, the fork point must be reached from it through re-hashed parent links, and both trees are walked through objects re-hashed against their names (non-canonical tree modes refused), so neither a moved ref nor a forged object or history in the agent-writable `.git` counts. A branch checked out in another worktree is refused. Paths match at any depth, as a case-insensitive file system sees them (`.Claude/` is `.claude/`), and an entry that replaces a parent directory (a `.github` symlink) counts too. It checks out the commit it checked, detached, requires the index's harness entries to be the verified ones, hashes every harness file it wrote and puts back the verified content of any that differs, and attaches `branch` only if the branch still points there. |
| `git-switch-create` | `worktree branch` | Creates a new topic `branch` (never a protected or an existing one) at upstream's `pr_base` as the policy's upstream URL reports it during the call, never a local ref, and switches the clean working tree to it with every check of `git-switch`; its harness files are upstream's, so nothing of the branch's own is there to refuse. A branch it could not switch to is deleted again. The way to start a change, or a fresh branch to finish a conflicting rebase on, in the main checkout. |
| `git-worktree-add` | `checkout path branch start` | Creates a linked worktree at `path`, directly inside a `worktree_roots` directory, on a new `branch` at `start`. |
| `git-worktree-remove` | `worktree` | Removes a linked worktree that has no changes (never `--force`). |
| `git-stage` | `worktree paths_file` | Stages exactly the relative paths listed, one per line, in `paths_file` (a workspace file), with `--literal-pathspecs`: no glob or `:(magic)` widens the set, and nothing outside the worktree or under `.git` is accepted. At most 500 paths per call. |
| `git-commit` | `worktree message_file` | Commits what is staged on the current branch (never a protected one, never `--amend`), message from `message_file` (a workspace file), with `--no-verify`. Signing follows the user's global git configuration. Refused unless `vetted-op-checks` passed every staged path, with the content it is staged with, in the sandbox: no hook runs out here, and nothing goes in unchecked. |
| `git-fetch` | `checkout branch` | Fetches upstream `branch` into `refs/remotes/<upstream_remote>/<branch>` from the URL built from the policy, never from a remote the repository configures; no tags, no submodules. |
| `git-pr-create` | `checkout branch title body_file` | Opens a pull request from `<fork owner>:<branch>` against `pr_base` of the upstream repository (`gh api … /pulls`). The `title` is a command-line parameter, so the confirmation the user approves shows the exact title that will be published; the body comes from a workspace file. Refuses a protected head branch, and any title or body holding a term the publication guard never lets out before disclosure (the list is generated from `magpie_vcs.publication.DEFAULT_TERMS`), except those the policy's `[git] published_terms` names: only a published record's identifier (`CVE id`, `CVE`), in a site repository's policy, and only when the forge's compare of the pushed branch against `pr_base` (`gh api …/compare/<pr_base>...<fork owner>:<branch>`, its head the local branch's commit) lists every changed file under `[git] published_paths`; otherwise the normal scan applies. |

From a change to an open pull request, then, with each step confirmed:
`git-worktree-add` (or `git-fetch` + `git-worktree-sync` to refresh one, or
`git-fetch` + `git-rebase` to bring a topic branch up to date), edit in
the sandbox, `vetted-op-checks <worktree> <workspace>/<paths-file>` in the sandbox,
`git-stage` with the same paths file, `git-commit`,
`git-push-branch … fork <branch> new`, `git-pr-create`.

In a linked worktree whose git directory the sandbox cannot read (a worktree
under `~/.cache/` of a checkout the sandbox denies), `vetted-op-checks` computes
the blob ids itself, as `git hash-object --no-filters` would in a SHA-1
repository (a SHA-256 one never matches, so `git-commit` refuses), and refuses
when the worktree has a hook configuration: the hook manager runs git, which
cannot open that git directory. A records site may opt out of its own hooks on
this route: `[git] site_hooks = "skip"`, valid only in a policy that sets
`published_paths` (never from `operator-git.toml`). Then `vetted-op-checks
--skip-site-hooks` records the checks as `skipped: site hooks off by policy`,
with the computed blob ids, and `git-commit` accepts that record only under
such a policy; under any other it refuses. The site's CI still runs the hooks on
the pull request, which changes only the records files.

The read and write dispatchers take `--policy-from <absolute dir>` too, so
`vetted-op-read --policy-from <site checkout> --save <name> repo-file <path> <base>`
reads a site repository's file from the forge through its own policy.
On every dispatcher the directory must be a `checkouts` entry of your own
`operator-git.toml` (checked before anything on disk is looked at), the policy
found there must be an approved copy, and its upstream's table must list that
checkout: `vetted-op-read` runs without a prompt, so it must not be pointed at
an arbitrary directory, to probe the host or to read through another project's
policy. `approval-status` and `source` refuse the option.

`vetted-op-checks` is the one vetted-ops command that runs *inside* the
sandbox (no `excludedCommands` entry names it, and a test keeps it that way):
it runs the worktree's hook configuration on the listed paths (for prek,
`prek run --files <paths>`) and, when they pass, records each path's content
beside the paths file, in `<workspace>/checks/`. `git-commit` reads that
record from its own policy's workspace and refuses a staged path that is
missing from it or staged with other content. The record is in a
sandbox-writable directory, so it keeps an agent honest the way CI does; it
is not a proof against one set on forging it.

It starts from `~/.cache/apache-magpie/vetted-ops/current`, a copy of this package the
plugin's session hook keeps for each installed version (`hooks/link-stable-path.sh`):
the sandbox cannot read `~/.claude/magpie/` or the plugin cache behind it. The copy is
sandbox-writable, which grants nothing to a command that runs sandboxed; every command
that runs outside the sandbox keeps starting from `~/.claude/magpie/`, which the agent
cannot edit. In a framework checkout, `uv run --project tools/vetted-ops vetted-op-checks …`
does the same.

```bash
uvx --from ~/.cache/apache-magpie/vetted-ops/current vetted-op-checks ~/code/project/.worktrees/fix-thing \
  ~/.cache/apache-magpie/vetted-ops-workspace/fix-thing-paths
```

```bash
uvx --from ~/.claude/magpie/vetted-ops vetted-op-git --caller <skill> git-push-branch \
  ~/code/project fix-thing fork fix-thing 0123…(40 hex)
```

They are bounded by `[git]` values from two places.
The shared policy's `[git]` table holds what the project decides, the same for everyone who approves it:

```toml
[git]
# Branches a push may create or move on [repos] upstream. Empty or absent: never.
upstream_push = ["ci-*", "stack/*"]
# Added to the built-in list (main, master, trunk, develop, gh-pages, release*, v*-test, v*-stable, *-stable, asf-site).
protected = ["prod"]
# The upstream branch git-pr-create targets. Default: main.
pr_base = "main"
# The forge pushes and pull requests go to. Default: github.com.
host = "github.com"
# Files that steer the agent outside the sandbox, added to git-switch's built-in
# list (.claude, .agents, .codex, .gemini, .github/skills, .mcp.json, .claude-plugin,
# the vetted-ops policy layers): git-switch writes only upstream's version of them.
harness_paths = ["tools/agent-settings.template.json"]
# Never-publish terms git-pr-create lets through: only "CVE id" and "CVE", and only in the
# policy of a site repository whose pull requests add records already public. Default: none.
# published_terms = ["CVE id", "CVE"]
# Required with published_terms: relative path prefixes (no globs, no ..) the exemption is
# bound to. It applies only to a branch whose every changed file, as the forge lists it, is under one.
# published_paths = ["content/security/json"]
```

The policy is discovered from the working directory, or from the absolute
directory `--policy-from <dir>` names (`vetted-op-git --caller <skill>
--policy-from <dir> <operation> …`), which must be a checkout your
`operator-git.toml` lists for the repository the policy there names. Either way
only an approved policy acts, so the option widens nothing; it lets a session in the tracker repository reach the
site repository's own policy without leaving its working directory (a `cd` into
the site checkout would put the command back in the sandbox), and the confirmation
shows which policy the call uses.

Where your clones, worktrees and fork are differs per person, so it does not belong in a policy everyone commits and approves.
Each operator keeps those values in `~/.config/apache-magpie/vetted-ops/operator-git.toml`, one table per upstream repository, picked by the policy's `[repos] upstream`:

```toml
["acme/project"]
# Main checkouts the operations may act on; their linked worktrees count too.
checkouts = ["~/code/project"]
# Pushed over git@<host>:<repo>.git (transport = "https" for https://<host>/<repo>.git).
fork = "alice/project"
transport = "ssh"
# Directories new worktrees may be created in, directly. Each must exist, be
# owned by you and be writable by nobody else (mkdir -m 700).
worktree_roots = ["~/.cache/apache-magpie/worktrees"]
# Remote-tracking namespace git-fetch writes to (refs/remotes/<this>/<branch>). Default: upstream.
upstream_remote = "upstream"
# Added to the policy's list; an operator can protect more branches, never fewer.
protected = ["my-wip-*"]
```

That directory is outside every repository and every sandbox-writable root, and `Edit`-denied, so the file needs no separate approval step: only you put it there.
Its tables may set only `checkouts`, `fork`, `worktree_roots`, `upstream_remote`, `transport` and `protected`; a project key there (`upstream_push`, `pr_base`, `host`, `harness_paths`, `published_terms`, `published_paths`) is refused, so nothing in it widens what the shared policy allows.
Its values win over the same keys in the policy, which keeps an older policy that still carries them working.
The file is never one of the approved policies, even byte-for-byte.
With neither source naming a value for the upstream, every git operation refuses, and skills fall back to handing over the commands.
`vetted-op-git policy` prints the effective values, each with the file it came from.

`git-stage`, `git-commit` and `git-pr-create` read their path list, message
and body from the policy's top-level `workspace`, under the same checks
as every body file (`vetted-op` above), so the confirmation shows a file the
agent wrote there and the operation reads exactly that file.

What makes running git unsandboxed acceptable here:

- **Closed destinations.** A push goes to a URL built from the policy's
  repository names, never to a remote the repository configures. Protected
  branches are refused whatever the policy says, and upstream takes only
  branches matching `upstream_push`.
- **Nothing lost silently.** Every push carries a lease on the full SHA the
  caller expects (`new` for a branch that must not exist yet), so a branch
  someone else moved is never overwritten, and moving a branch to a commit with
  nothing over a remote's default branch (an emptied rebase, which would close
  the pull request it heads) is refused, as agent-guard's `empty-rebase` guard
  refuses the plain `git push`. A worktree moves only when it has
  no local changes, and the previous commit is printed and stays in the reflog.
- **No repository configuration steers git.** Keys such as `core.sshCommand`,
  `url.*.insteadOf`, `filter.*`, `core.fsmonitor`, `core.hooksPath` or
  `include.path` can be planted in a repository's own config; the operation
  refuses to run while the local or worktree config holds any key outside a
  short list of inert ones (remotes, branch tracking, `user.name`, …). Global
  and system configuration are the user's own and stay in effect, so an SSH
  wrapper or touch overlay configured there keeps working. The check covers
  every working tree the operation runs git in, and runs again right before
  the command that acts.
- **Pinned on every call**, so a key added between that check and the command
  cannot take effect: no file-system monitor, no automatic gc or maintenance,
  only `https` and `ssh` transports, `core.sshCommand` set to the user's global
  value (or `ssh`), and hooks off wherever they are not wanted. Attributes are
  read from the empty tree, so no `.gitattributes` can switch on a filter
  (the cost: a worktree is checked out without LFS smudging or line-ending
  conversion). A push sends the one ref, never tags (`--no-follow-tags`), and
  `GIT_ALLOW_PROTOCOL` limits transports whatever the configuration says.
- **Directories are held, not named.** Each validated directory is opened
  without following a symlink at any component, and git runs inside it by
  descriptor, so a directory swapped for a symlink after the checks cannot
  send git elsewhere. A new worktree is created through its root's descriptor
  and added as `.`, so git names its administrative directory `-` (`-1`, …).
  A URL rewrite (`url.*.insteadOf`) cannot be pinned away: that it cannot
  appear while the confirmed command runs rests on the harness keeping
  `.git/config` write-protected, as Claude Code's sandbox does.
- **No environment steers git.** Every `GIT_*` variable is dropped, `HOME`
  comes from the password database and `XDG_CONFIG_HOME` is dropped, so the
  global configuration git reads is the account's own.
- **Hooks never run.** No operation runs a hook: every operation sets
  `core.hooksPath=/dev/null`, and a push or commit also passes `--no-verify`. A
  `pre-push` hook is code the agent can write (`.git/hooks/pre-push`, or a
  hook manager reading its configuration from the working tree), and the
  confirmation shows the push, not what the hook would execute, so running it
  here would run agent-written code outside the sandbox. The push-time checks
  still run: the caller runs them inside the sandbox first (for prek,
  `prek run --hook-stage pre-push --from-ref <base> --to-ref <branch>`), fixes
  what they report, and only then pushes. Before `git-commit` the checks are
  enforced: `vetted-op-checks` runs them in the sandbox and records the
  content they passed, and `git-commit` refuses anything else.
- **Public text is scanned.** `git-pr-create` refuses a title or body holding
  a never-publish term before it calls `gh`, with the same list the guard
  applies (generated by `tools/dev/sync-forbidden-terms.py`, checked for drift
  in pre-commit), because the guard does not read the files this operation
  publishes.
- **Unapproved policy, dry run.** `--dry-run` against a policy that is not an
  approved copy checks the parameters and runs no git command; only an
  approved policy prints the command it would run.

Everything else git does in a sandboxed session stays there. A plain rebase
onto an upstream `pr_base` commit is `git-rebase`. Any other history rewrite for
a branch checked out in a worktree you did not create (a squash, a reorder, a
conflict resolution, a branch with merge commits) is done in a scratch clone (`git clone --shared <checkout> <scratch>`), fetched back into the main
checkout, pushed with `git-push-branch` and applied with `git-worktree-sync`.

## Wiring it into settings

Replace the wildcard `ask` rules with one `allow` entry, and keep an `ask` on
anything still invoked directly:

```jsonc
"permissions": {
  // Only the READ dispatcher is allowlisted. Allowlisting `vetted-op` itself
  // would grant every write in the catalogue, since --caller is argv.
  // Both launchers: skills use `uv run --project`, gatherer agents `uvx --from`.
  // Per machine, add the same two rules with $HOME resolved (see below).
  "allow": [
    "Bash(uv run --project ~/.claude/magpie/vetted-ops vetted-op-read *)",
    "Bash(uvx --from ~/.claude/magpie/vetted-ops vetted-op-read *)"
  ],
  "ask": [
    // The write dispatchers. Excluded from the sandbox below, so never `allow`.
    "Bash(uv run --project ~/.claude/magpie/vetted-ops vetted-op *)",
    "Bash(uvx --from ~/.claude/magpie/vetted-ops vetted-op *)",
    "Bash(uv run --project ~/.claude/magpie/vetted-ops vetted-op-tracker *)",
    "Bash(uvx --from ~/.claude/magpie/vetted-ops vetted-op-tracker *)",
    // The private-tracker batches (see "Batches of private-tracker writes"): never allow.
    "Bash(uv run --project ~/.claude/magpie/vetted-ops vetted-op-tracker-batch *)",
    "Bash(uvx --from ~/.claude/magpie/vetted-ops vetted-op-tracker-batch *)",
    // The unprompted twin runs only a `none` policy. An adopter whose policy sets
    // private_tracker_writes = "none" may move these two, and only these, to allow.
    "Bash(uv run --project ~/.claude/magpie/vetted-ops vetted-op-tracker-batch-unprompted *)",
    "Bash(uvx --from ~/.claude/magpie/vetted-ops vetted-op-tracker-batch-unprompted *)",
    "Bash(uv run --project ~/.claude/magpie/vetted-ops vetted-op-git *)",
    "Bash(uvx --from ~/.claude/magpie/vetted-ops vetted-op-git *)"
  ],
  "deny": [
    // `Edit(path)` is the path rule for every file-writing tool — Write and
    // NotebookEdit included. A `Write(path)` rule is NOT matched by the file
    // permission check, so adding one buys nothing and reads as coverage the
    // deny list does not have.
    "Edit(~/.claude/plugins/cache/apache-magpie/magpie-vetted-ops/**)",
    "Edit(~/.claude/magpie/**)",
    "Edit(.apache-magpie-overrides/tools/vetted-ops/**)",
    "Edit(//**/.apache-magpie-overrides/tools/vetted-ops/**)",
    "Edit(~/.config/apache-magpie/vetted-ops/**)",
    "Edit(//**/.git/**/apache-magpie/tools/vetted-ops/**)",
    "Edit(//**/.svn/apache-magpie/tools/vetted-ops/**)",
    "Edit(//**/.apache-magpie-local/tools/vetted-ops/**)"
  ]
}
```

The read dispatcher also needs a `sandbox.excludedCommands` entry, or the
`allow` rule above buys nothing. The framework already excludes bare `gh *`
because a sandboxed `gh` cannot verify TLS — on macOS it fails with
`x509: OSStatus -26276`. A `gh` spawned *inside* `uv run … vetted-op-read` is
not a bare `gh` invocation, so it stays sandboxed and every read operation
fails the same way:

```jsonc
"sandbox": {
  "excludedCommands": [
    "gh *",
    "uv run --project ~/.claude/magpie/vetted-ops vetted-op-read *",
    "uvx --from ~/.claude/magpie/vetted-ops vetted-op-read *",
    "uv run --project ~/.claude/magpie/vetted-ops vetted-op-tracker *",
    "uvx --from ~/.claude/magpie/vetted-ops vetted-op-tracker *",
    "uv run --project ~/.claude/magpie/vetted-ops vetted-op-tracker-batch *",
    "uvx --from ~/.claude/magpie/vetted-ops vetted-op-tracker-batch *",
    "uv run --project ~/.claude/magpie/vetted-ops vetted-op-tracker-batch-unprompted *",
    "uvx --from ~/.claude/magpie/vetted-ops vetted-op-tracker-batch-unprompted *",
    "uv run --project ~/.claude/magpie/vetted-ops vetted-op-git *",
    "uvx --from ~/.claude/magpie/vetted-ops vetted-op-git *",
    "uv run --project ~/.claude/magpie/vetted-ops vetted-op *",
    "uvx --from ~/.claude/magpie/vetted-ops vetted-op *"
  ]
}
```

The write dispatchers are excluded too: a sandboxed `vetted-op` cannot even read
`~/.claude/magpie/` to start, and its `gh` would fail the same TLS check.
Excluding them is safe for a different reason than the read dispatcher's `allow`.
`vetted-op-read` refuses writes before it consults the policy, so it can run unprompted.
`vetted-op` runs the whole write catalogue, but every operation is a fixed `gh`
argv with no shell, parameters that may not start with `-`, and a body read only
from the owner-only workspace, so unsandboxed it reaches less than the bare `gh *`
already excluded. `vetted-op-tracker` is narrower still: it refuses everything but
the tracker procedures, and their runner refuses any `gh` call outside
`repos/<tracker>/`. The repositories both write to come from the policy, which is
why both keep their `ask` (never `allow`); `sandbox-lint` fails an excluded write
dispatcher that has lost its `ask` rule.

`vetted-op-tracker-batch-unprompted` is the one exception, and only by the adopter's choice.
It runs nothing but a checked manifest of private-tracker writes, on a tracker the forge confirms is private,
and only under a policy that sets `[approval] private_tracker_writes = "none"`,
so a project whose approved policy says `none` may move its two rules from `ask` to `allow`.
`vetted-op-tracker-batch` never moves: it also runs `batch` policies, whose adopters asked for a prompt.
`sandbox-lint` accepts `ask` or `allow` for the unprompted dispatcher, fails it excluded with neither,
and treats `vetted-op-tracker-batch` like every other write dispatcher.
What `none` gives up is in [the batch design note](https://github.com/apache/magpie/blob/main/docs/designs/2026-11-26-vetted-ops-batch-tracker-writes.md#how-approval-maps-to-harness-prompts).

Every rule names the fixed path `~/.claude/magpie/vetted-ops`, not the
versioned plugin-cache directory. The plugin's `SessionStart` hook
([`hooks/link-stable-path.sh`](hooks/link-stable-path.sh)) points that path at
the installed version each session, so an upgrade changes no rule. Do not glob
the version instead (`…/magpie-vetted-ops/*/tools/vetted-ops …`): a `*` also
matches spaces, so it approves a command with extra `uv` options spliced in at
that position (`--with <any package>`, a second `--from`), and the exclusion
then runs it outside the sandbox. The fixed path is `Edit`-denied like the
catalogue it points at, and sits outside every `sandbox.filesystem.allowWrite`
root.

**The read dispatcher must never prompt.**
This is an imperative of the secure setup, not a tuning option: bulk skills call `vetted-op-read` from background gatherer agents, which cannot surface a prompt, so every prompt there is a silent denial and the sync returns partial results.
Beyond the rules above, that takes no `ask` rule that matches a `vetted-op-read` command, and `permissions.blockReadsOutsideWorkingDirectories` off in every scope, since the read block cannot check the literal `~` these commands spell.
The three `Edit` deny rules are required alongside: they are what makes the unprompted read safe.
Every rule spells the base as the literal `~/.claude/magpie/vetted-ops`, and so must every call: the agent-guard [`vetted-ops-spelling`](https://github.com/apache/magpie/blob/main/tools/agent-guard/README.md#guards) guard refuses an expanded home path or a checkout path and names the `~` command instead.
The setup skills install, verify and report drift on the whole shape; see [Read-only vetted ops never prompt](https://github.com/apache/magpie/blob/main/docs/setup/secure-agent-setup.md#read-only-vetted-ops-never-prompt).

The dispatcher must live where the agent cannot rewrite it — otherwise an agent
that edits `ops.py` has defeated the whole design. That is why it ships as the
`magpie-vetted-ops` **substrate plugin**: the installed plugin tree is not a path
the agent edits, and it sits outside every `sandbox.filesystem.allowWrite` root,
so sandboxed Bash cannot write there either.

The `deny` rules above are the other half, and the `allow` is not defensible
without them. Two surfaces define what the dispatcher may do — the operation
catalogue and the **policy**, which names the caller→operation grants. An agent
able to edit either one can grant itself the write access the wildcard `ask`
rules were removed for; adding an op to the catalogue and adding itself to a
caller list reach the same place.

Be clear about the asymmetry: the catalogue is protected twice (deny rules plus
the sandbox), the policy only once. The policy lives inside the adopter repo,
which is sandbox-writable by design, so a Bash-level write (`sed -i`, a heredoc)
is **not** covered by an `Edit`/`Write` deny. If that gap matters for reads, keep the
policy outside the writable root and point `vetted-op-read --config` at it; the
write entry points ignore `--config` and need a harness that merges the policy
path's `Edit` deny into the sandbox's write-deny list, as Claude Code does. Vendoring the
dispatcher itself into a repo the agent edits reduces it to the same single
layer.

### Codex native rules

Codex loads the plugin’s Claude-compatible `SessionStart` hook after hook trust review.
The shared stable path remains `~/.claude/magpie/vetted-ops`; no Claude runtime is needed.
Run `vetted-ops-codex-rules` from the installed tool to print twelve native prefix rules (absolute path only, never `~`), then review and install the output under `~/.codex/rules/magpie-vetted-ops.rules`.
Run `vetted-ops-codex-rules --hook` to print the Codex-only PreToolUse hook that rewrites a lone `vetted-op-read` call in the `~` spelling skills use to that path before the rules see it (writes and compound commands are never rewritten); review it and add it to `~/.codex/config.toml` — never to Claude Code, which reads its `allow` as a permission grant.
The renderer only prints; it never edits user policy.
Both supported launchers allow only `vetted-op-read` and prompt `vetted-op`, `vetted-op-tracker`, `vetted-op-tracker-batch`, `vetted-op-tracker-batch-unprompted` and `vetted-op-git`.
Paths are absolute, with no version glob or general `uv` allow rule.

These native rules provide Codex’s approval path for networked reads; they do not create a sandbox exclusion or a file-write deny.
Keep the dispatcher outside writable roots and verify authentication through a permitted read.
The [Codex adapter](https://github.com/apache/magpie/blob/main/docs/adapters/harnesses/codex.md#vetted-operations) specifies install, verification, and remaining differences from Claude’s tamper protection.

## Tests

```bash
uv run --project . python -m pytest
```

The suite asserts the properties above rather than the plumbing: hostile
parameters are refused, every builder produces a `gh` argv, the repo cannot be
influenced by a parameter, body files outside the workspace are rejected while
hostile body *content* passes through untouched, and a caller cannot run an
operation outside its manifest.

## Referenced by

- [RFC-AI-0002](https://github.com/apache/magpie/blob/main/docs/rfcs/RFC-AI-0002.md) — the layered agent-isolation posture.
- [`tools/spec-loop/specs/vetted-command-surface.md`](https://github.com/apache/magpie/blob/main/tools/spec-loop/specs/vetted-command-surface.md)
