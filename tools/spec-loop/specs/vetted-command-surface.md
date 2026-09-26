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
<framework>/tools/vetted-ops vetted-op-read …` spelling every permission rule
and sandbox exclusion names — a bare `vetted-op-read` would miss the
allowlist and prompt or run sandboxed (#1339).

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

   *Repo health, release management, contributor growth and mentoring have
   landed*, completing the pass over the families that touch the forge. They
   needed seven operations between them — `repo-view`, `repo-tree`, `run-list`,
   `run-view`, `release-list`, `release-view`, `user-profile` — because they are
   overwhelmingly read surfaces; mentoring needed none at all, working entirely
   through the issue and PR operations. A family earns new operations only when
   it has a shape the catalogue lacks.

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

## Non-goals

- **Replacing the sandbox.** This operates at Layer 3 only. Layers 0–2 are
  unchanged and still carry the load.
- **Removing human confirmation from genuinely novel actions.** Anything outside
  the catalogue keeps its `ask` rule. The catalogue is deliberately small and
  grows by review.
- **Pretending `--caller` is authentication.** Stated plainly wherever the
  mechanism is documented.
