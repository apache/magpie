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

In the [Step 1g](../../skills/security-issue-sync/gather.md#1g-recently-closed-trackers--check-cveorg-publication-state) closed-bucket scan,
for a closed `announced` tracker, once cve.org reports the CVE `PUBLISHED` —
the same condition sync uses for the final *"CVE is live"* reporter email.
The planner checks the condition itself and refuses before it, so a mistaken run cannot record an embargoed CVE:
it needs cve.org's `PUBLISHED` state *and* a `vendor-advisory` reference in the record (the archived public advisory).

A tracker whose CVE is already recorded gets no proposal, and neither does one that carries the `advisory-records v1` marker comment sync posts after a successful run.

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
The working copy is a per-user path, so `user.md → environment.advisory_records_clone` overrides `working_copy`.

Leave the block out and nothing changes: sync notes *"advisory records: not configured — skipped"* and keeps the checklist reminder.

## What the user confirms

One numbered item in sync's Step 2b proposal: the diff, and the [`magpie-vcs`](../../tools/vcs/README.md) commands in order.

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

## Safety properties

- **Never before publication.** Refused unless cve.org reports `PUBLISHED` and the record carries the public advisory.
- **Idempotent.** A re-run finds the entry (the CVE ID as an element's whole text or attribute value, or in the Markdown section) and proposes nothing.
  A CVE recorded under a different release is refused, not duplicated.
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
