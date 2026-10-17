<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Read `tracker.platform` from `<project-config>/project.md` before the first tracker operation; unset or `TODO` means `github`.
With `github`, every recipe below runs as written.
With `local-files` or `jira`, never run a `gh` command against `<tracker>`:
look the command up in the [skill-command → vetted-operation table](../../../../tools/security-tracker/contract.md#from-skill-commands-to-vetted-operations)
and run that vetted operation instead — `vetted-op-read` for reads, `vetted-op-tracker` for the rollup, body-field and publish operations, `vetted-op` for the other writes.
Vetted-ops translates it for the configured backend; issue numbers become the backend's IDs (`SEC-0012`, `FOOSEC-12`), and the returned `url` is the link.
Operations on `<upstream>` (PRs, code search) do not change.
A refusal — the backend's confidentiality guard, or an operation the backend does not have — stops the step: report it, never route around it.

**Pre-flight on another backend.** The GitHub checks in Step 0 — `gh api repos/<tracker>` access, the collaborator roster, project-board ids — do not apply.
Run the `tracker-doctor` vetted operation instead and stop on any failing check; take the security-team roster from `<project-config>/release-trains.md`, and treat the project board as disabled.

**CVE JSON on another backend.** `generate-cve-json <N> --attach` reads and attaches through GitHub, so do not run it.
Instead: save the body with the `issue-body` vetted operation (`vetted-op-read … --save cve-body issue-body <id>`),
run `generate-cve-json --stdin --title "<issue title>" --output <workspace>/<CVE-ID>.json` on that saved file —
adding `--review` when the issue's labels (from `issue-view`) include the release-vote label or a forward-state label the generator's config names, since `--stdin` cannot see labels and would otherwise produce DRAFT —
and attach the result with the `issue-attach` vetted operation (`<id> <workspace>/<CVE-ID>.json <CVE-ID>.json`).

**Publish local tracker changes before ending.** With `local-files`, nothing reaches the team until it is committed.
If this run wrote to the tracker, run the `tracker-pending` vetted operation as the last step, show the changed files and any unpushed commits,
draft a commit message naming the trackers and the action, ending with the project's commit-attribution trailer, and ask.
Only on the user's confirmation run `tracker-publish` with that message file
(Git: commit the tracker folder and push; SVN: commit, which publishes).
