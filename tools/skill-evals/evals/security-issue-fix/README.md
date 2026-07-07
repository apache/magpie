<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# security-issue-fix eval suite

Behavioral evals for the `security-issue-fix` skill. Eleven steps are
covered; steps 0 (pre-flight), 1 (sync), 4 (repo setup), 7 (implement),
8 (push), 9 (PR open), and 10 (tracker update) are skipped — tool-execution
steps with no structured-output decision boundary.

## Steps

| Step | Name | Cases | Notes |
|------|------|-------|-------|
| 2 | Existing-PR check | 3 | PR linked in tracker, PR found via search, no PR found |
| 3 | Fixability assessment | 5 | Includes untrusted-snippet case |
| 5a | Branch name | 3 | Good slug, CVE-id-in-name, security-fix-in-name |
| 5b | Files that will change | 3 | Trusted snippet, untrusted snippet, mixed |
| 5c | Commit message and PR title | 3 | Hard rule: no CVE IDs, no security framing |
| 5d | Test plan | 3 | Full plan, pure-rename (no new tests), no typecheck |
| 5e | Backport label | 3 | Patch release, main-only, multiple backports |
| 5f | Newsfragment | 2 | Default no-fragment, forbidden security framing |
| 5g | PR body draft | 3 | Clean body, forbidden terms, missing GenAI block |
| 6 | Confirm plan | 3 | apply-all, free-form edit, cancel |
| 11 | Recap | 2 | With backport label, no backport needed |

## Hard rules exercised

- **Existing-PR duplicate prevention**: when an existing PR addresses the
  issue, the skill must recommend `"adopt"` and never create a duplicate
  PR (step-2 cases 1–2).
- **No existing PR proceeds**: when no PR is found via any discovery method,
  the skill proceeds to fixability assessment (step-2 case-3).
- **Fixability stop conditions**: any single hard-to-fix signal (competing
  approaches, large scope, open questions) must produce `stop: true` even
  when other signals look positive (step-3 cases 2–4).
- **Untrusted non-collaborator snippet**: flagged as untrusted with
  `quote_as_untrusted` treatment (step-5b case-2).
- **Mixed trusted/untrusted snippets**: each file entry carries its own
  `snippet_trusted` and `snippet_treatment` (step-5b case-3).
- **CVE ID in branch name**: `cve-YYYY-NNNNN-*` must be flagged invalid (step-5a case-2).
- **Security-framing in branch name**: `security-fix-*` must be flagged invalid (step-5a case-3).
- **No new tests must be justified**: skipping new test cases requires an explicit reason
  such as "pure rename / no new behaviour" (step-5d case-2).
- **Typecheck only when applicable**: mypy command omitted when the module is excluded
  from mypy scope (step-5d case-3).
- **Forbidden terms in PR body**: `security vulnerability`, bare CVE IDs, or `vulnerability`
  flip `approved` to false (step-5g case-2).
- **Missing GenAI disclosure block**: PR body without the GenAI checkbox section flips
  `approved` to false (step-5g case-3).
- **Security framing in newsfragment**: explicitly describing the change as a security fix
  sets `security_framing_violation: true` (step-5f case-2).
- **Recap includes backport note**: even when no backport is needed, the recap must
  explicitly state that (step-11 case-2).
- **Free-form edit**: a user response requesting a plan change must produce
  `"action": "edit"` — not `"apply"` (step-6 case-2).
