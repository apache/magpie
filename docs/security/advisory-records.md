<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Recording published CVEs in the project's security records](#recording-published-cves-in-the-projects-security-records)
  - [When it runs](#when-it-runs)
  - [The two layouts](#the-two-layouts)
  - [Configuration](#configuration)
  - [What the user confirms](#what-the-user-confirms)
  - [Publishing through a pull request](#publishing-through-a-pull-request)
    - [Configuration in pull-request mode](#configuration-in-pull-request-mode)
    - [The commands in pull-request mode](#the-commands-in-pull-request-mode)
    - [Following the pull request](#following-the-pull-request)
    - [Publishing through `vetted-op-git`](#publishing-through-vetted-op-git)
    - [The publication guards](#the-publication-guards)
  - [Backfilling records published earlier](#backfilling-records-published-earlier)
  - [Safety properties](#safety-properties)
  - [Limits](#limits)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

# Recording published CVEs in the project's security records

**Capability:** `capability:resolve` (see [`docs/labels-and-capabilities.md`](../labels-and-capabilities.md)).

Most projects list their published vulnerabilities on their own website, built from a site repository they keep in Git or Subversion.
Once an advisory is public, the ASF security-committers policy asks the project to update those pages.
Without configuration, `security-issue-sync` only tracks that step: a checklist item in the release-manager hand-off comment, and at most one reminder.
With [`advisory_records`](../../plugins/magpie-setup/templates/project.md#advisory-records) configured, sync proposes the edit itself:
the file change, and the version-control commands that publish it.

## When it runs

**When the advisory is announced.** The record is public the moment the advisory is archived on the project's public list,
so sync writes it in the same pass that records the announcement: the *Advisory archived on `<users-list>`* combined apply
([Step 1d](../../plugins/magpie-security/skills/issue-sync/gather.md#1d-mine-comments-and-mail-messages-for-actionable-signals))
captures the archive URL, regenerates the CVE JSON with it as a `vendor-advisory` reference, and then proposes the site record
from that just-regenerated JSON, as one more item of the same batch and under the same confirmation.
The planner gets `--announced-url <archive URL>` and refuses unless the record carries exactly that URL as a `vendor-advisory` reference,
so a mistaken run cannot record an embargoed CVE.
The record is written the way the planner always writes it: sorted keys, the configured indent, without `CNA_private`.

**When cve.org lists it.** In the [Step 1g](../../plugins/magpie-security/skills/issue-sync/gather.md#1g-recently-closed-trackers--check-cveorg-publication-state) closed-bucket scan,
once cve.org reports the CVE `PUBLISHED` (the condition sync uses for the final *"CVE is live"* reporter email),
a record already on the site is checked once more against the record regenerated now;
sync proposes a refresh only when the two differ, and records the refresh with an `advisory-records-refresh v1` comment.
A tracker that was announced without the step (the configuration came later, or the announcement apply skipped it) gets the record here instead,
with the cve.org gate: `PUBLISHED` *and* a `vendor-advisory` reference in the record.

A tracker whose CVE is already recorded gets no new record, and neither does one that carries the `advisory-records v1` marker comment sync posts after a successful run.

## The two layouts

| Layout | What it changes | Example of a project laid out this way |
|---|---|---|
| `cve-json-file` | Adds `<CVE-ID>.json` to a directory of the site repository: the CVE 5.x record [`generate-cve-json`](../../tools/cve-tool-vulnogram/generate-cve-json/README.md) emits, without the CNA tool's internal `CNA_private` block. The site builds its vulnerability pages from these files. | Apache HTTP Server keeps them under `content/security/json/` in its site repository |
| `release-page` | Inserts an entry into the page for the fixed release's line, inside the section for that release; a missing section is created in newest-first order. | Apache Tomcat keeps one `xdocs/security-<line>.xml` page per release line in its Subversion site |

The shipped `release-page` example templates follow that XML shape:

```xml
<section name="Fixed in <Product> <version>" rtext="<release date>">

  <p><strong><Impact>: <title></strong>
  <cve><CVE-ID></cve></p>

  <p><description></p>

  <p>This was fixed with commit <hashlink hash="<commit>"/>.</p>

  <p>This issue was reported to the <Product> security team on <date>.
  The issue was made public on <date>.</p>

  <p>Affects: <range></p>

</section>
```

The page path, the section name and both templates are the adopter's, so another XML page format works by changing the templates,
and `format: markdown` handles a Markdown page whose sections are headings.
The template reference is in the
[tool README](../../tools/cve-tool-vulnogram/generate-cve-json/README.md#record-a-published-cve-in-the-projects-security-records--advisory-records).

A CVE fixed in several release lines is recorded on each line's page in one commit.

## Configuration

The `advisory_records` block in `<project-config>/project.md`
([template](../../plugins/magpie-setup/templates/project.md#advisory-records)):
`vcs` (`git` or `svn`, defaulting to the project's source-control backend), `repository` (used to propose the first checkout), `working_copy`,
`branch` and `remote` (Git), `commit_message`, `layout`, and the layout's own block (`cve_json_file` or `release_page`).
`publish` picks how the commit reaches the site repository: `direct` (the default) or `pull-request` (Git only, see [Publishing through a pull request](#publishing-through-a-pull-request)).
The working copy is a per-user path, so `user.md → environment.advisory_records_clone` overrides `working_copy`.

Leave the block out and nothing changes: sync notes *"advisory records: not configured — skipped"* and keeps the checklist reminder.

## What the user confirms

One numbered item in sync's Step 2b proposal: the diff, and the [`magpie-vcs`](../../tools/vcs/README.md) commands in order.
This table is the `direct` mode; the `pull-request` mode has [its own](#the-commands-in-pull-request-mode).

| Step | Git | Subversion |
|---|---|---|
| 1 | `clean` — stop on unrelated changes | `clean` |
| 2 | `branch` — must be the configured branch | — |
| 3 | `update` (`pull --ff-only`) | `update` |
| 4 | the planner again with `--apply`, on the updated copy | same |
| 5 | `stage <files>` | `stage <files>` (`svn add` for a new file) |
| 6 | `diff --cached <files>` | `diff <files>` |
| 7 | `commit -m "<message>"` | `commit -m "<message>"` — this publishes |
| 8 | `push <remote> <branch>` | — |

With no working copy yet, the proposal is the single `checkout` command; the change is proposed on the next sync.
After the commit (and the push on Git) succeeds, sync posts a status comment with the `advisory-records v1` marker and the ticked security-pages checklist item.
Committing or pushing needs the user's credentials for the site repository; under the [secure agent setup](../setup/secure-agent-setup.md) the user may have to run those commands from their own terminal.

## Publishing through a pull request

Many site repositories take changes only through reviewed pull requests, and a site that builds its security section from one JSON file per CVE
gets each record the same way.
With `publish: pull-request`, the person who runs sync (the operator, not the release manager) commits the record on a new branch,
pushes that branch to their own fork of the site repository, and opens a pull request against the configured `branch`.
Nothing is ever pushed to the site repository itself.

### Configuration in pull-request mode

| Key | Default | Meaning |
|---|---|---|
| `publish` | `direct` | `pull-request` turns the mode on; a Subversion working copy refuses it |
| `branch` | `main` | the base branch the pull request targets (and the branch the working copy is kept on) |
| `pull_request.repo` | derived from a GitHub `repository` URL | the site repository as `owner/name`, for `gh pr create --repo` |
| `pull_request.branch` | `advisory-records/{cve_id}` | the branch the record is committed on, in the working copy and on the fork |
| `pull_request.title` | `commit_message` | one line; placeholder `{cve_id}` |
| `pull_request.fork` | — | the operator's fork, `owner/name`; per user, so `user.md → environment.advisory_records_fork` wins |
| `pull_request.fork_remote` | `fork` | the working copy's remote for that fork; `user.md → environment.advisory_records_fork_remote` wins |

The fork differs per operator, like the working copy, so both fork keys normally live in `user.md` only.
The operator adds the fork as a remote of the working copy once (`git remote add fork <fork URL>`); the planner never configures remotes.

### The commands in pull-request mode

| Step | Command | |
|---|---|---|
| 1 | `clean` | stop on unrelated changes |
| 2 | `branch` | must print the base branch |
| 3 | `update` | `pull --ff-only` of the base branch |
| 4 | `new-branch <pull-request branch>` | local only |
| 5 | the planner again with `--apply` | writes the change on the new branch, and the pull-request body file beside the record |
| 6 | `stage <files>` | |
| 7 | `diff --cached <files>` | |
| 8 | `commit -m "<message>"` | local |
| 9 | `push <fork remote> <pull-request branch>` | publishes the branch on the operator's fork |
| 10 | `switch <base branch>` | local only: the next run starts from the base branch again |
| 11 | `MAGPIE_ALLOW_SECURITY_LANG=1 gh pr create --repo <site repo> --base <base> --head <fork owner>:<branch> --title "<title>" --body-file <file>` | publishes the pull request |

Steps 1 to 10 are [`magpie-vcs`](../../tools/vcs/README.md) commands; step 11 is a plain `gh` command.
Between steps 8 and 9 sync runs the configured [adversarial review](../../tools/adversarial-review/README.md), as every pull-request-opening skill does;
it sees only the record, the title and the body the pull request publishes.
The body names the changed file(s), the public announcement URL and, once cve.org lists the record, the date it published it; no tracker text goes into it.
Once the pull request is open, sync posts the `advisory-records v1` status comment with the pull request's URL.
The security-pages checklist item stays unticked: the record is not on the site until the pull request merges.

### Following the pull request

The planner cannot see an open pull request, since the base branch does not hold the record until it merges, so the tracker's comments carry the state:

| What the tracker holds | What sync does |
|---|---|
| no `advisory-records v1` comment | looks for a pull request from the configured branch (`gh pr list --repo <site repo> --head <branch> --state all`); open or merged → proposes only the status comment that records it, never a second pull request; none, or only a closed one → runs the planner, and the proposal names the closed one |
| an `advisory-records v1` comment with a pull-request URL | reads that pull request's state (`gh pr view <url> --json state`) |
| … still open | notes *"advisory records: `<URL>` open"*; proposes nothing |
| … merged | proposes a status comment opening with `<!-- apache-magpie: advisory-records-merged v1 -->` and the ticked security-pages checklist item |
| … closed without merging | a blocker naming the pull request; nothing is re-proposed until the team decides how to record the CVE (to try again, a team member deletes the status comment, and the operator the branch on the fork and in the working copy) |
| an `advisory-records-merged v1` comment (or a direct-mode `advisory-records v1` comment), cve.org not `PUBLISHED` yet | done for now |
| … and cve.org lists the CVE `PUBLISHED` | reads the site's copy of the record from the forge (`vetted-op-read … repo-file <path> <base>` with `--save`) and runs the planner against it (`--from-saved`) with `--recheck` and the record regenerated now, which compares contents (a JSON file with the rendered record, a page entry with the entry rendered from it): `unchanged` → one closing `advisory-records-recheck v1` comment, so the site is read once; a difference → proposes a refresh, the same publication on a `advisory-records/<CVE-ID>-refresh` branch; a page entry that does not match → a blocker for the team to compare by hand, never reported as matching; a failed read → try again next sync |
| an `advisory-records-refresh v1` comment naming a pull request | follows it like the first one: open → waits; merged → proposes the `advisory-records-refresh-merged v1` comment; closed without merging → proposes the refresh again, on `advisory-records/<CVE-ID>-refresh-<N>` |
| an `advisory-records-recheck v1` or `advisory-records-refresh-merged v1` comment | done |

Both lookups are read-only `gh` calls; a failed lookup proposes nothing and is retried on the next sync.

### Publishing through `vetted-op-git`

Under the [secure agent setup](../setup/secure-agent-setup.md) the site checkout is out of the sandbox's reach
(only the tracker and framework checkouts are granted), so the `magpie-vcs` commands above can only be handed to the user.
[`vetted-op-git`](../../tools/vetted-ops/README.md#git-operations-the-sandbox-blocks) runs the same publication outside the sandbox,
one confirmed operation at a time, from a linked worktree of the site checkout.
No sandboxed command reads the site checkout: what sync needs to know about the site comes from the forge or from a vetted operation.

The proposal is planned from the forge. For each file the record touches (the JSON file, or each release-line page),
sync reads the site's copy at the base branch with `uvx --from ~/.claude/magpie/vetted-ops vetted-op-read --caller security-issue-sync --policy-from <site checkout> --save <name> repo-file <path> <base>`
and runs the planner with `--vetted-git --from-saved <path>=<saved file>`, or `--site-absent <path>` for a 404 (the file is new);
the planner refuses a path answered by neither, so an unread file is never taken as absent.
`--policy-from` accepts only a checkout the operator's own `operator-git.toml` lists for the site repository:
the read dispatcher runs without a prompt, so it cannot be pointed at any other directory;
`repo-file` saves the forge's base64 content, which the planner decodes.
A backfill lists the site's files instead (`… --save <name> repo-tree <base>`) and passes the listing as `--site-listing`.
Then, on confirmation:

| Step | Command | Where |
|---|---|---|
| 1 | `git-fetch <site checkout> <base>` | outside the sandbox: prints the fetched commit, `<start-sha>` |
| 2 | `git-worktree-add <site checkout> <worktree> <branch> <start-sha>` | outside |
| 3 | the planner again with `--apply`, recomputing the change on `<worktree>` and writing it there, and the paths list, the commit message and the body into the policy's workspace | in the sandbox |
| 4 | `vetted-op-checks <worktree> <paths file>` | in the sandbox, see below |
| 5 | `git-stage <worktree> <paths file>` | outside |
| 6 | `git-commit <worktree> <message file>` | outside |
| 7 | `git-push-branch <worktree> <branch> fork <branch> new` | outside: publishes the branch on the operator's fork |
| 8 | `git-pr-create <worktree> <branch> "<title>" <body file>` | outside: publishes the pull request |

The commit message file ends with the attribution trailer [`commit-attribution.md`](../setup/commit-attribution.md) resolves:
the project's convention (`--commit-trailer`, or `--no-commit-trailer` for none), else the framework's own `Generated-by: <agent name and version>` (`--agent`);
the site repository has not adopted Magpie, so the tracker project's convention is the one that applies.
The planner prints these with `--vetted-git`; every `vetted-op-git` call is spelled
`uvx --from ~/.claude/magpie/vetted-ops vetted-op-git --caller security-issue-sync --policy-from <site checkout> …`.
Between steps 6 and 7 sync runs the adversarial review, as in the table above.
After the pull request merges, `git-worktree-remove <worktree>` and `git-delete-fork-branch <site checkout> <branch> <head-sha>` clean up, each confirmed.

What makes it possible, and what it keeps apart:

- **The site repository has its own policy.** The project's policy names one `upstream` repository, the source repository the security fix flow publishes to;
  widening it to the site would let every caller push there. Instead the site checkout carries its own policy in its personal layer
  (`<site checkout>/.git/apache-magpie/tools/vetted-ops/config.toml`), with the site repository as `[repos] upstream`,
  `security-issue-sync` as its only caller and the git steps above as its only grants
  ([the example](../../tools/vetted-ops/README.md#configuration)); the user approves it like any policy.
  `--policy-from <site checkout>` selects it without leaving the tracker session's working directory.
- **The operator's own values** for the site repository are a `["<site repo>"]` table in `~/.config/apache-magpie/vetted-ops/operator-git.toml`:
  `checkouts` (the site checkout), `fork` and `worktree_roots`.
- **The worktree is sandbox-writable; the checkout is never read from the sandbox.** The planner's `--apply` and `vetted-op-checks` run in the sandbox,
  so the worktree root must be one the sandbox writes: a directory under `~/.cache/`, which the secure setup grants
  (for example `~/.cache/apache-magpie/worktrees/<site name>`, created with `mkdir -m 700`, as `vetted-op-git` requires).
  The `--apply` run reads and writes only the worktree's files.
  Git itself cannot run there from the sandbox: a linked worktree keeps its index and objects in the site checkout's `.git`, which the sandbox denies.
  So `vetted-op-checks` computes the checked files' blob ids itself (SHA-1, as `git hash-object` would; a SHA-256 repository never matches, so `git-commit` refuses rather than commit unchecked content).
  A site repository with a hook configuration (`.pre-commit-config.yaml`) cannot be checked this way, since `prek` runs git:
  by default sync reads `.pre-commit-config.yaml` from the forge first and, when the site has one, hands over the `magpie-vcs` commands from the start.
  If the checks still refuse once the worktree exists, the hand-over is the planner's `fallback_commands`:
  remove the worktree (`git worktree remove --force`, since it holds the uncommitted change) and delete its never-pushed branch, then the `magpie-vcs` commands,
  which make the same branch again, the one later syncs find the pull request by.
  A site may opt in to skipping its own hooks on this route with `[git] site_hooks = "skip"` in its policy
  (only a records-site policy, one with `published_paths`, may set it): the checks are then recorded as skipped, `git-commit` accepts that,
  and the pull request's body says *"Hooks were not run locally; the repository's CI checks this PR."*
  The pull request changes only the records files, and the site's own CI runs the hooks on it.
  `git-fetch`, `git-worktree-add`, `git-stage` and `git-commit` read and write the checkout outside the sandbox.
- **The published identifier passes `git-pr-create`'s scan, nothing else does.** That scan refuses every term the publication guard keeps back before disclosure.
  The site policy sets `[git] published_terms = ["CVE id", "CVE"]`, which only a policy can set and which names nothing beyond the record's identifier,
  so the title and body may name the published CVE while every other term stays refused.
  The exemption is bound to the records: the policy must also set `[git] published_paths` (the records directory, e.g. `content/security/json`),
  and `git-pr-create` applies it only when the forge reports that every file the pushed branch changes against the base lies under one of those paths.
  A branch that touches anything else, as a source-repository change would, gets the normal scan.

`setup config` proposes the operator table and the site policy
([Step 3a.3](../../plugins/magpie-setup/skills/setup/config.md#step-3a3--your-git-values-for-publishing-secure-setup-only)),
and `setup reconcile` reports them missing.
Until both are there, `vetted-op-git` refuses and sync hands over the `magpie-vcs` commands of the table above, as before.

### The publication guards

The pull request is opened only after the planner's gate (the confirmed announcement URL as the record's `vendor-advisory` reference, or cve.org `PUBLISHED` and a `vendor-advisory` reference), so naming the CVE is right.
Four guards look at publishing commands; each was checked against the commands above:

- **agent-guard's `security-language` guard** refuses a CVE ID in the title or body of any `gh pr create`, whatever the repository.
  Its documented exemption for a disclosure that is already public is the inline `MAGPIE_ALLOW_SECURITY_LANG=1`,
  so the planner puts it on step 11, where the user sees it in the command they confirm.
  Without it the default title (`Add {cve_id} to the security pages`) is refused.
- **The `public-surface-scrub` hook** (the `magpie-security` plugin's mod) scrubs only commands aimed at the project's `upstream_repo`, a repository of the same name, or an undetermined one.
  `gh pr create --repo <site repo>` names its target, so a site repository named differently from the source repository passes.
  A project whose site lives in the source repository itself, or that has no `upstream_repo` configured, is refused (`CVE`, `CVE id`);
  that hook honours only `MAGPIE_ALLOW_EMBARGO_TERMS=1` set before the session starts, never an inline one, so such a project should keep the direct mode or have a maintainer open the pull request.
- **`magpie-vcs`** scrubs a commit message or a branch name only with `--scrub`, which the planner does not pass,
  and the hook does not inspect `magpie-vcs` commands, so the commit message and the `advisory-records/<CVE-ID>` branch name are not refused.
- **`vetted-op-git git-pr-create`** refuses every never-publish term in the title and body, except those its policy's `[git] published_terms` names.
  The site policy names the record's identifier only (`CVE id`, `CVE`), so the default title and the body pass, and a body that strayed into any other term
  (`vulnerability`, `advisory`, a vulnerability class) is still refused. Neither agent-guard nor the hook inspects `vetted-op-git` commands,
  and a project whose site lives in the source repository cannot use this route either: its one policy must not let the identifier through.

## Backfilling records published earlier

A project that starts recording after some advisories have shipped can add the missing ones in one change.
Generate each published record into one directory (`generate-cve-json <N> --output <dir>/<CVE-ID>.json` for each closed `announced` tracker),
save each one's cve.org state beside it (`cve-check-published <CVE-ID>` as `<dir>/<CVE-ID>.cve-org.json`),
and run the planner with `--backfill <dir>` instead of `--record` (the `cve-json-file` layout only).
It lists the records that pass the cve.org gate and that the site does not hold yet, skips the others with a reason
(not public yet, already on the site, on the site with other content), and proposes one change, one commit and, in pull-request mode, one pull request
(`advisory-records/backfill`, titled `Add <N> published records to the security pages`), with the same commands as a single record, `--vetted-git` included.
A record on the site with other content is left alone; the post-publication check of each tracker proposes its refresh.
For one pull request per record instead, run the planner once per record.

## Safety properties

- **Never before publication.** Refused unless the record carries the public advisory as a `vendor-advisory` reference and either that is the announcement URL the user confirmed in the same sync pass or cve.org reports `PUBLISHED`, in every publishing mode.
- **Idempotent.** A re-run finds the entry (the CVE ID as an element's whole text or attribute value, or in the Markdown section) and proposes nothing.
  A CVE recorded under a different release is refused, not duplicated.
  In pull-request mode the status comment and the branch lookup stand in for the entry until the pull request merges.
- **Nothing reaches the site repository unreviewed in pull-request mode.** The only push goes to the operator's fork, and the site's own review merges the change.
- **External content is escaped.** Title, description, product and affected-versions text come from the tracker;
  they are escaped for the page format, and identifiers (CVE ID, versions, dates, commit hashes) are validated.
- **Pages are spliced, not rewritten.** The planner refuses a page that is not well-formed XML, never fetches external entities,
  and keeps the page's formatting, comments, entity references and line endings.
- **No unconfirmed VCS command.** The planner runs none; sync runs the confirmed ones one by one and stops at the first failure.

## Limits

- The first page of a new release line is not created; the planner refuses and asks for it to be added by hand.
- Inputs the record does not carry come from the tracker, the release train or the user:
  the release date (only to create a section), the date the report arrived, and fix commits when no `patch` reference is a commit URL.
- The default *Affects* text is the record's version range (`>= 9.0.0, < 9.0.99`); a project that writes it differently passes `--affects`.
- Pull-request mode opens the pull request with `gh`, so the site repository has to be on GitHub; it needs a Git working copy with the operator's fork as a remote.
- A site that lives in the source repository itself cannot use pull-request mode from an agent session: the `public-surface-scrub` hook refuses the pull request's text there (see [The publication guards](#the-publication-guards)).
