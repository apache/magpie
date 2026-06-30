<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Review criteria — pointers to source

This file is a **navigation map** for the project's review
criteria. It does not restate the rules — those live in the
source files below and are the single source of truth. The
skill's review pass reads them at session start (and re-reads
the per-area `AGENTS.md` files as PRs route into different
trees) and quotes the **source rule verbatim** in any finding
it raises.

If you find yourself wanting to "summarise the rule" in this
file or in a finding body, **stop and link to the source line
or section instead**. Summaries drift; links don't.

---

## Source files

| File | What it covers |
|---|---|
| (read from `<project-config>/pr-management-code-review-criteria.md` → `repo_wide_source_files`) | The rule set every <PROJECT> PR is reviewed against. |

The concrete list of source files is project-specific and lives in
the adopter's `<project-config>/pr-management-code-review-criteria.md`.
The table below shows the **shape** of a typical configuration;
see `projects/_template/pr-management-code-review-criteria.md` for
a concrete example.

| File | What it covers |
|---|---|
| `<repo_wide_review_criteria>` | The rule set every PR is reviewed against (typically architecture / DB / quality / testing / API / UI / generated files / AI-generated-code signals / quality signals). |
| `AGENTS.md` | Repo-wide AI/agent instructions (architecture boundaries, security model, coding standards, testing standards, commits & PR conventions). |
| `<area>/AGENTS.md` | Per-area rules (e.g. tree-specific or subsystem-specific overlays). |
| `<security-model-doc>` | The documented security model — what *is* and *isn't* a vulnerability. |

The per-PR review flow re-runs `git ls-files` against the
touched paths to discover any other `AGENTS.md` not in this
table; see [`review-flow.md#area-specific-overlay`](review-flow.md).

---

## Categories — link out to the source section

The list below is the **abstract canonical category list** the
skill uses when grouping findings. The concrete review-doc URL
for each category lives in the adopter's
`<project-config>/pr-management-code-review-criteria.md` →
`Section anchors` table; the skill resolves a category to its
URL at finding time by matching the category name verbatim
against that table's `Section` column. If a category has no
anchor row, the skill falls back to a plain reference (no
clickable link) and surfaces the missing anchor as a one-line
warning at the top of the review.

The canonical category list:

- Architecture boundaries
- Database / query correctness
- Code quality
- Third-party license compliance
- License headers
- Testing
- API correctness
- UI (React/TypeScript)
- Generated files
- AI-generated code signals
- Quality signals to check
- Commits and PRs (newsfragments, commit messages, tracking issues)
- Security model

See
[`projects/_template/pr-management-code-review-criteria.md` § Section anchors](../../projects/_template/pr-management-code-review-criteria.md#section-anchors)
for a worked example.

---

## Third-party license compliance

When the diff adds or modifies a file that contains a non-Apache licence
header (`SPDX-License-Identifier:` value other than `Apache-2.0`, or a
recognised licence block — MIT, BSD, GPL, LGPL, CDDL, MPL, EPL, etc.) or a
third-party copyright line (`Copyright (c) <non-ASF entity>`), classify the
licence against the ASF `resolved_licenses` policy
(`https://www.apache.org/legal/resolved.html`) and apply the following
severity rules:

| Category | Licences (examples) | Severity |
|---|---|---|
| X | GPL, AGPL, LGPL, CDDL, BUSL, SSPL | `blocking` — cannot be included in an ASF release in any form |
| B | MPL, EPL | `blocking` — cannot be included in source form; binary-only inclusion requires explicit justification |
| A | MIT, BSD-2, BSD-3, ISC, Apache 2.0 (other orgs) | `major` if `LICENSE` / `LICENSE.txt` was **not** also updated in this PR — attribution is required before shipping |
| A + LICENSE updated | any Category A | ✅ no finding |

For Category A findings, check whether the same PR modifies `LICENSE`
or `LICENSE.txt` to add an attribution notice for the bundled component.
If it does, the inclusion is correctly attributed and no finding is raised.
Some projects also keep a `licenses/` directory containing the full licence
text of each bundled component — this is a common and good practice, but it
is not required and does not affect the finding: the determining factor is
whether `LICENSE` / `LICENSE.txt` was updated, not whether a `licenses/`
entry exists.

**Relationship to "License headers":** when a new file's header is non-Apache
but not third-party (e.g. a contributor accidentally used the wrong SPDX
identifier), the "License headers" finding applies (see
[§ License headers](#license-headers) below). When the header is
clearly from an upstream library or external author, route to this category
instead — the fix is to preserve the original header and update `LICENSE`,
not to replace it with an Apache header.

Source: `https://www.apache.org/legal/resolved.html` and
`https://www.apache.org/legal/apply-license.html`.

---

## License headers

ASF policy requires every source file in a release to carry the
standard Apache license header
(`https://www.apache.org/legal/src-headers.html`). This is a
**framework-level default** that applies regardless of
adopter-specific rules.

**Defer to the project's header tooling when it exists.** Many ASF
projects enforce headers in CI — `apache-rat`, the pre-commit
`insert-license` hook, `license-eye` / `skywalking-eyes`, or an
equivalent. If such a check appears in the PR's status-check
rollup (the [CI precheck](prerequisites.md) already reads it):

- That tool is **authoritative for the mechanical question** —
  "does this file carry the header" — including which paths are
  in scope. Do **not** raise a duplicate "missing header"
  finding: a real miss already turns the check red, and Golden
  rule 8 already takes `APPROVE` off the table and quotes the
  failing check. Restating it as a review finding is noise and
  risks contradicting the tool's own exclusion list.
- The source of truth for **scope and exemptions** is the
  project's tool config (the `apache-rat` `<excludes>` block,
  `.rat-excludes`, the pre-commit `exclude:` regex, the
  `licenserc.yaml` ignore globs — whatever the project uses),
  **not** the policy page. When reasoning about whether a file
  is in scope, read that config, not a summarised list here.

**Fallback — projects with no header tooling.** If no
license-header check appears in the rollup, the skill **is** the
safety net. Scan every source file the diff **adds** (and any it
materially rewrites) for the Apache header; raise a `major`
finding for each contributor-authored file missing it, quoting
`https://www.apache.org/legal/src-headers.html`. Apply the
exemptions listed in the *Exemptions* paragraph at the end of
this section using judgement, and the *When in doubt — defer*
rule at the end of this file for anything borderline.

**The exclusion-masking case — check even when CI is green.**
Deference above assumes the tool's exclusion list is fixed. It is
not when the **PR itself changes it**. If the same diff both
(a) adds or modifies a header-tool exclusion entry — an
`<exclude>` in `pom.xml` / `build.gradle`, a line in
`.rat-excludes`, an `exclude:` pattern in
`.pre-commit-config.yaml`, an ignore glob in `licenserc.yaml`,
etc. — and (b) adds a file that lacks an Apache header or carries
a third-party header, then the check passes **green by
construction** and CI deference gives no coverage. This is
precisely where the skill earns its place. Raise a `major`
finding asking the maintainer to confirm the exclusion is
appropriate:

- **Legitimately exempt** — generated code, data/test fixtures,
  binary assets, or a genuinely third-party file correctly
  attributed in `LICENSE` (route the third-party part to
  [§ Third-party license compliance](#third-party-license-compliance)).
  If so, the exclusion is fine; note it and move on.
- **Masking a missing header** — a contributor-authored source
  file that simply has no header and was excluded to make CI
  pass. Not acceptable; the fix is to add the header, not to
  exclude the file.
- **Overly broad exclusion pattern** — even if the files added
  in this PR carry correct headers, a glob wider than necessary
  (e.g. `src/**`, `*.java`, a whole subtree containing
  contributor-authored source) silently degrades the tool for
  all future PRs. Raise a `minor` finding asking the maintainer
  to scope the pattern to the specific file or directory it is
  meant to cover.

Quote the added exclusion line and the offending file path in the
finding so the maintainer can adjudicate without digging.

**Judgement cases the tool cannot decide.** Even on a
fully-tooled project, raise a finding for:

- a contributor-authored file with a **mis-applied SPDX
  identifier** or the **wrong license** in an otherwise
  Apache-intended header (the tool sees *a* header and passes;
  the header is still wrong);
- a header that is **clearly third-party / upstream** — do not
  treat as a missing-header miss; route to
  [§ Third-party license compliance](#third-party-license-compliance)
  (the fix there is preserve-and-attribute, not replace).

**Exemptions (no finding).** Generated files; vendored or
third-party files (handled by the third-party category); data and
test-resource fixtures; binary files; trivially short config/data
files where the project conventionally omits headers; files in
formats that do not support comments and therefore cannot carry a
header (e.g. JSON, CSV, most binary data formats); documentation
and plain-text files (`.md`, `.rst`, `.txt`) where ASF projects
are conventionally lenient; `README` files (in any format);
`LICENSE`, `NOTICE`, `DISCLAIMER`, and similar legal declaration
files that are themselves the licence artefact. On a tooled
project the project config is the authority for these; on an
untooled project use judgement and defer when unsure.

| Situation | Severity |
|---|---|
| Missing header, no header tooling in CI | `major` |
| Missing / 3rd-party header + new tool exclusion in same PR | `major` (confirm exclusion is justified) |
| New exclusion pattern is overly broad | `minor` |
| Wrong / mis-applied SPDX on contributor-authored file | `major` |
| Missing header but header tooling is red on the PR | no separate finding — defer to CI (Golden rule 8) |
| Header tooling present, CI green, no exclusion change in this PR | no finding — defer to tooling |
| Header added in this PR alongside the file | no finding |

Source: `https://www.apache.org/legal/src-headers.html` (policy)
and the project's own header-tool configuration (scope and
exemptions).

---

## Per-area / subtree-specific signals

When a PR touches a subtree the adopter listed in
`<project-config>/pr-management-code-review-criteria.md` →
`Per-area source files`, the skill reads (and quotes from) those
per-area files in addition to the repo-wide ones. The skill also
auto-discovers any `AGENTS.md` under the touched paths via
`git ls-files`, so an `AGENTS.md` not listed in the table is
still loaded if the diff touches its tree.

If a touched subtree has no `AGENTS.md` and no entry in the
adopter table, only the repo-wide rules apply.

---

## Security model — calibration

> This category also includes a **public-disclosure signal scan**
> that runs in Step 3 (PR title, body, and commit messages),
> before the diff is examined. See
> [`review-flow.md` § Security-disclosure signal scan](review-flow.md#security-disclosure-signal-scan).

Before flagging anything that looks security-flavoured in the
diff, read the documented security model at the path declared in
`<project-config>/pr-management-code-review-criteria.md` →
`security_model_calibration.file`. The framework's reference
threat model lives at
[`docs/security/threat-model.md`](../../docs/security/threat-model.md);
read both before deciding. Use the calibration to distinguish:

1. an **actual vulnerability** that violates the documented
   model — flag as blocking,
2. a **known limitation** that's already documented as
   intentional — do not flag,
3. a **deployment-hardening opportunity** — belongs in
   deployment guidance, not as a code finding.

When the skill downgrades what looked like a finding because
the documented model permits it, the review body **quotes the
relevant model paragraph** so the contributor sees the
calibration explicitly. Don't paraphrase.

---

## Quality signals to check — image IP

The "Quality signals to check" category is primarily driven by the adopter's
source files. The following is a **framework-level default** that applies
regardless of adopter-specific rules.

When the diff adds one or more binary image files (`.png`, `.jpg`, `.jpeg`,
`.gif`, `.svg`, `.ico`, `.webp`), use judgment rather than raising an
automatic finding:

- **Contributor-created screenshots, diagrams, and documentation graphics**
  are legitimate by default — no finding.
- **Logos, brand assets, or illustrations** that look professionally produced
  warrant a short comment asking the contributor to confirm the source and
  licence: *"Could you confirm this image is original work or confirm its
  licence? If it's from a third-party source, it may need a `LICENSE` entry
  or a different approach."*

Do not flag every image addition. The signal is the visual character of the
asset — a hand-drawn architecture diagram is different from a polished brand
logo. When in doubt, ask rather than block.

## Quality signals to check — compiled artifacts

ASF releases must be source-only. Compiled or binary build artifacts added to
the repository risk ending up in a release, violating the ASF Release Policy
(`https://www.apache.org/legal/release-policy.html`).

When the diff adds any of the following file types, raise a `major` finding:

- **JVM**: `.class`, `.jar` (non-empty), `.war`, `.ear`
- **Python**: `.pyc`, `.pyo`, `.pyd`
- **Native**: `.so`, `.dll`, `.dylib`, `.exe`, `.o`, `.a`
- **Packages**: `.whl`, `.egg`

The finding is `major` with the text: *"Compiled artifacts must not be
committed to the source tree — ASF releases are source-only. Remove this
file and ensure it is generated at build time."* If the file would be
included in a release archive, escalate to `blocking`.

---

## AI-generated code signals — authorship disclosure

The "AI-generated code signals" category is primarily driven by the adopter's
source files. The following is a **framework-level default** that applies
regardless of adopter-specific rules.

Some projects require contributors to **disclose** when generative-AI tooling
helped author a PR — typically a checkbox or `Generated-by:` line in the PR
template, or a rule in the contributing docs. This is project policy, not a
framework universal: this default fires **only when the project itself has
such a requirement**. Where it does not, there is nothing to enforce and no
finding is raised.

**Determine whether the project requires disclosure from the repository
itself, not from a hardcoded list.** Read the repo's
`.github/PULL_REQUEST_TEMPLATE.md` (and any `.github/PULL_REQUEST_TEMPLATE/`
variants) for a generative-AI / authorship disclosure section, or an adopter
`pr-management-code-review-criteria.md` entry that declares one. If neither
exists, skip this check entirely.

**Scan the PR body for AI-authorship signals** (case-insensitive). Any one is
enough to treat the body as likely AI-authored:

- a task-list "Test plan" / "Test Plan" section using `- [x]` / `- [ ]`
  checkboxes;
- structured `## Summary` / `## Changes` / `## Test plan` headings that
  **replace** the project's PR template rather than filling it in;
- an echoed `**Title:**` / `**Summary:**` line restating the PR title;
- a `Generated-by:` / `Co-Authored-By:`-an-AI-tool trailer, a
  "🤖 Generated with …" line, or first-person tool phrasing
  ("I (Claude / Cursor / Copilot / Devin / …) …").

**Raise a `minor` finding** when AI-authorship signals are present **and** the
project requires disclosure **and** the body carries no affirmed disclosure
(the template's disclosure checkbox is absent or left unchecked, and no
`Generated-by:` line is present). Cite the specific signal and quote the
project's own disclosure requirement:

> `minor` — *"This PR looks co-authored with generative-AI tooling
> (cite the signal — e.g. a `Test plan` task-list and a dropped PR template),
> but the project's AI-assistance disclosure is missing or left unchecked.
> The project asks contributors to affirm AI assistance — please tick the
> disclosure box / add the `Generated-by:` line per the project's
> contributing-docs link."*

This is **not** slop and is deliberately **not** a
[`slop-detection.md`](slop-detection.md) signal — a genuine, useful PR can
simply have skipped the disclosure. Keep it a `minor`
contribution-guidelines observation inside the normal review; it must never
gate an otherwise-approvable PR on its own, and it never triggers the slop
early-exit path. The operational scan that produces this finding runs in
[`review-flow.md` § AI-authorship disclosure scan](review-flow.md#ai-authorship-disclosure-scan).

---

## Backports and version-specific PRs

If the adopter's
`<project-config>/pr-management-code-review-criteria.md` declares
a backport branch pattern (see its `Backports / version-specific
PRs` table), PRs whose base branch matches the pattern are
treated as backports of already-merged `main` work and get a
lighter-touch calibration:

- **Diff parity**: does this match what was merged on `main`?
- **Cherry-pick conflicts**: did the resolution introduce new
  changes that need scrutiny?
- **API/migration version markers**: backports should not
  introduce new version bumps in any
  versioning-sensitive subsystem the adopter calls out; if they
  do, cite the relevant `API correctness` anchor from the
  adopter's `Section anchors` table.

For these PRs, prefer `COMMENT` over `REQUEST_CHANGES` unless
the cherry-pick has clearly drifted from the `main` change.

If the adopter config has no backport pattern declared, this
section is a no-op and every PR is reviewed under the same
calibration.

---

## Conflict between source rules

If the per-area `AGENTS.md` rules **conflict** with the
repo-wide ones (rare; usually a more specific override), the
more specific one wins — but the conflict is surfaced to the
maintainer for explicit acceptance during disposition pick
(see [`review-flow.md`](review-flow.md)).

---

## When in doubt — defer

If after reading the diff you're not sure whether something is
a finding or just a style preference, **do not flag it**.
Surface the uncertainty to the maintainer (one line:
*"Hmm — line N does X, which I'm not sure violates the rules;
flagging for your eye."*) and let them decide. The cost of an
over-zealous auto-finding is a contributor who feels
nitpicked; the cost of a missed nit is one round of
back-and-forth a maintainer can catch easily on their own
pass.
