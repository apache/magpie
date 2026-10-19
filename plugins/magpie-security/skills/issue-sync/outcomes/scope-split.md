<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# security-issue-sync — splitting a multi-scope report

The Guardrails rule in [`SKILL.md`](../SKILL.md#guardrails), with the split procedure.
Relative links are rooted one level deeper than in `SKILL.md`.

- **Multi-scope reports must be split into one tracking issue per
  scope.** When a report affects more than one scope (for example a root cause in a shared core module
  whose vector also exists in a plugin/extension component), never apply two scope labels to one issue;
  propose the split instead:

  1. Keep the original issue on the scope whose milestone family ships *first*
     (usually core, whose patch releases cut faster), and drop the extra scope label from it.
  2. Create one new issue per remaining scope via `gh issue create
     --repo <tracker>`, copying the report body
     verbatim but with a one-line preamble that says *"Split from
     [#NNN](https://github.com/<tracker>/issues/<N>) for the `<scope>` scope — see that issue for the
     full discussion history."*
  3. Apply to each split issue:
     - exactly one scope label (see
       [`<project-config>/scope-labels.md`](../../../../../<project-config>/scope-labels.md));
     - the same `cve allocated` label if a CVE is shared across
       scopes — CVE reuse is correct when the same upstream bug
       affects multiple products, with one `affected[]` entry per
       product in the CVE record;
     - the PR / advisory labels (`pr created` / `pr merged` /
       `fix released`) derived independently per scope from the same
       fix PR, because each scope rides a different release train;
     - the matching milestone for that scope (see
       [`<project-config>/milestones.md`](../../../../../<project-config>/milestones.md));
     - the same assignee set as the anchor issue.
  4. Post a cross-link comment on **each** issue pointing at the other(s).
  5. Update the open reporter email draft, if any, to mention the split and link every tracker.

  Do **not** silently drop a scope label without splitting: each scope's release managers need the issue on their own milestone.
  A single issue with two scope labels is a process bug — flag it as a **blocker** and propose the split as a concrete numbered item.
