<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Confidentiality — drafting elaboration](#confidentiality--drafting-elaboration)
  - [Sharing a tracker URL with someone who cannot access it](#sharing-a-tracker-url-with-someone-who-cannot-access-it)
  - [Where the tracker URLs are routinely OK to use](#where-the-tracker-urls-are-routinely-ok-to-use)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Confidentiality — drafting elaboration

Agentic Drafting-time elaboration of the tracker-confidentiality rules. The
load-bearing rules — the three-layer model (identifiers public, contents
private, security-framing embargoed), the "what public surfaces must not
contain" checklist, the content scrub, and "other ASF projects" — live
inline in
[`AGENTS.md`](../AGENTS.md#confidentiality-of-the-tracker-repository).
This file holds the two how-to elaborations that an agent loads when it
is actually composing reporter-facing or public text.

## Sharing a tracker URL with someone who cannot access it

When the recipient is an external reporter, a public-PR reviewer who is
not on the security team, or any other audience without read access to
`<tracker>`, **pair the URL with a one-line note** that the link is an
identifier only:

> Tracking this internally as
> `https://github.com/<tracker>/issues/NNN` (private — you will not
> be able to view the page; included as a stable identifier so we
> both reference the same issue across messages).

Wording is not load-bearing; the load-bearing element is that the
recipient knows the link will 404 for them and that this is expected.
The note can be omitted on surfaces where every viewer is a
security-team member (the tracker itself, `<security-list>` threads
restricted to the team, internal docs, rollup entries).

## Where the tracker URLs are routinely OK to use

- **Reporter emails** — *may* include the tracker URL in any status
  update, paired with the explanatory note above. This makes
  cross-message threading much cleaner for the reporter and gives
  them a stable identifier to file the report under.
- **Public `<upstream>` PR descriptions and commit messages** —
  *may* include the tracker URL as a cross-reference, **so long as
  the surrounding text does not characterise the PR as a security
  fix** (no CVE ID, no *"vulnerability"*, no *"security advisory"*
  framing). The URL alone is opaque to non-team viewers.
- **Public CVE records and archived advisories** — the tracker URL
  may appear in `references[]` once the advisory ships. For
  records still in DRAFT / REVIEW state it stays internal-only.
- **`gh issue comment` calls inside the tracker repository** — fine,
  they land on private issues.
- **`<security-list>` private mail threads** — fine.
- **`<private-list>` PMC escalation mails** — fine.
