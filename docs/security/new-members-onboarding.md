<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Welcome](#welcome)
- [How the team is composed](#how-the-team-is-composed)
- [Where things happen](#where-things-happen)
- [Your first week](#your-first-week)
- [Picking up a role](#picking-up-a-role)
- [Using the agent skills](#using-the-agent-skills)
- [Proactive work and process improvements](#proactive-work-and-process-improvements)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

# Welcome

Hello, new member of the adopting project's security team. This
repository hosts a project-agnostic framework for handling security
issues; the adopting project's per-project layer lives in
[`<project-config>/`](<project-config>/) (i.e. `.apache-magpie/` at
the root of the adopter's tracker repo). This document
is the soft-landing guide — it tells you how the team works, where
the action happens, and what is expected of you in the first few
weeks.

Read this end-to-end once, then use [`README.md`](../../README.md) as the
operational reference when you start actually handling issues. The
README is organised by role (triager / remediation developer / release
manager); pick the role that matches what you are about to do and jump
into its section.

# How the team is composed

The security team is a group of people — mostly members of the
project's governance body and committers of the adopting project
(for the ASF/Airflow named example: PMC members and committers of
`apache/airflow`), but we also have security researchers and people
who are not yet committers but aspire to be, and who are already
active and known in the community. The exact governance body the
team draws from is declared in
`<project-config>/project.md → governance.cve_allocation_gate`. We
also have members of the security teams of stakeholders who deal
with the project's security outside of the community project itself
— for example, when they provide the project as a service.

The team works on a voluntary basis. We understand that people have
other commitments and lives, and we do not expect them to be available
24/7 or to take part in every discussion. However, we do expect some
level of involvement and commitment — at least participating in
discussions, providing feedback, and voting on issues when needed.

Being a member of the security team is not a permanent assignment; we
rotate the team periodically (so far we have only rotated members once,
after about 8 months, but we expect shorter rotation periods in the
future). We are also open to new members joining the team at any
time — especially when people who satisfy the project's
`governance.cve_allocation_gate` wish to join (for the ASF/Airflow
named example: PMC members of `apache/airflow`).

We will likely re-evaluate the team composition and process in a few
months, taking into account the involvement of people and their
willingness to continue to be part of it.

All release managers are members of the security team by default, as
they are responsible for publishing CVE (Common Vulnerabilities and
Exposures) information about issues when affected software is released
with the fixes.

The authoritative source for who is currently on the team is the
collaborator list of the tracker repository (`<tracker>`) —
everyone listed, regardless of permission level. For the active
project, see
[`<project-config>/release-trains.md` — Security team roster](<project-config>/release-trains.md#security-team-roster)
for the lookup command and the latest snapshot.

# Where things happen

- **The project's `<security-list>`** — see
  `<project-config>/project.md → Mailing lists` for the concrete
  address. You are subscribed automatically when you join the
  security team. This is where external reporters land their reports
  and where we reply to keep them informed.
- **`<tracker>` GitHub repository** — the private tracker. Every
  valid report becomes a tracking issue here. Everything that
  happens on an issue is automatically mirrored to the security
  mailing list so people who prefer email stay in the loop.
- **Security-issues board** — each project runs its own Projects V2
  board. See `<project-config>/project.md → GitHub project board`
  for the URL. If you want one thing to bookmark for the adopting
  project, bookmark that board.
- **Private PRs on the `<tracker>` `main` branch** — an exceptional
  path used for highly-critical fixes that need private code review
  before going public. See
  [Step 9](../security/process.md#step-9--open-a-private-pr-exceptional-cases) of
  the process.

Some discussions with an obvious answer can be handled on the mailing
list without creating a tracker, but in general we prefer having issues
and discussions in the repository so they are searchable and
discoverable for everyone else on the team.

# Your first week

Take the pressure off. You do not have to drive any issue in your first
week. A good starting routine:

1. **Read [`README.md`](../../README.md) once, skim the role sections.** Pick
   the role you think you are most likely to take on first, and read it
   in full.
2. **Open the adopting project's board** — its URL is in
   `<project-config>/project.md → GitHub project board`. Get a
   feel for what states issues sit in and how they flow across
   columns.
3. **Subscribe to a few open issues** and read along. The mailing-list
   mirror means you will see new activity in your inbox. Seeing a few
   issues move from `needs triage` to `cve allocated` and onwards is
   the fastest way to internalise the process.
4. **Read [`<project-config>/canned-responses.md`](<project-config>/canned-responses.md).** These are the
   reply templates we send to reporters. They shape most of the tone
   you will eventually need to match when you draft a reply yourself.
5. **Read [`AGENTS.md`](../../AGENTS.md) at least the
   [Confidentiality](../../AGENTS.md#confidentiality-of-the-tracker-repository)
   section.** The rule of thumb: nothing about the tracker repository
   (`<tracker>`) — issue numbers, labels, discussions, even the repo
   name — leaves the private channels.
6. **Set up your per-user config** if (and only if) you plan to run
   the agent skills. Copy
   `.apache-magpie-overrides/user.md` (scaffolded automatically when
   the project adopts Magpie) and fill in your GitHub handle, email,
   governance-gate status (whatever
   `<project-config>/project.md → governance.cve_allocation_gate`
   declares — for the ASF/Airflow named example: PMC membership),
   and (for remediation-developer work) the path to your local
   `<upstream>` clone. You can skip this step on day one;
   skills fall back to runtime prompts when
   `.apache-magpie-overrides/user.md` is missing.

You can start commenting on issues on day one. Just commenting,
voting on validity, suggesting severity — those are valuable
contributions and do not require you to pick up a role or to set up
any per-user config.

# Picking up a role

Once you have observed the process for a while, you can start taking
on more of the work. The three rotating roles — issue triager,
remediation developer, release manager — are defined in
[`README.md`](../../README.md),
which describes the step ranges each role owns. From the onboarding
perspective:

- **Issue triager** is the natural first role: it's the one you can
  step into as soon as you're comfortable with the tone of the
  canned responses and the shape of the triage loop.
- **Remediation developer** suits team members who are already regular
  contributors to the adopting project — the role owns a fix PR in
  `<upstream>` and is easiest to pick up when you already know that
  codebase.
- **Release manager** is usually inherited rather than volunteered for:
  when you cut a release that contains a security fix,
  `security-issue-sync` hands those trackers to you with
  `fix released` and you own them through the advisory + `<cve-tool>`
  steps (for the ASF/Airflow named example: the Vulnogram instance at
  `cveprocess.apache.org`, declared in
  `<project-config>/project.md → cve_authority.record_url_template`).

You can volunteer to provide a fix for a specific issue even before
formally taking on the remediation-developer role — just comment on
the tracker and self-assign. You can also ask whether it makes sense
to involve someone else to provide the fix (see
[Step 7](../security/process.md#step-7--self-assign-and-implement-the-fix) for the
delegation rules).

# Using the agent skills

A lot of the repetitive work on this team has been automated into
agent skills that live under
[`.claude/skills/`](../../skills/). They are plain `SKILL.md`
files with YAML frontmatter, so Claude Code picks them up
automatically and other agents that follow the emerging skill
convention can use them too.

You do **not** need an agent to participate on the team. For commenting
and discussing on the board, a browser is enough.

If you do use an agent, the three commands a rotational triager runs
a few times a week are:

- **`import new reports`** — converts un-imported security-list
  threads into trackers and drafts the receipt-of-confirmation reply.
  See [Step 2](../security/process.md#step-2--import-the-report).
- **`sync all issues`** — reconciles every open tracker with its mail
  thread, its fix PR, the release train, and the users-list archive.
- **`allocate CVE for issue #N`** — when a report is assessed as valid.
  See [Step 6](../security/process.md#step-6--allocate-the-cve).

There is also a fourth command for anyone willing to take on a
remediation-developer turn:

- **`try to fix issue #N`** —
  [`security-issue-fix`](../../skills/security-issue-fix/SKILL.md)
  attempts to land the fix for a triaged tracker in one go. It runs a
  pre-fix sync, reads the discussion on the tracker to build a fix
  plan, shows you the plan, and — only after you confirm — writes the
  change in your local `<upstream>` clone (path from
  `.apache-magpie-overrides/user.md → environment.upstream_clone`), runs the local
  checks and tests, and opens a public `gh pr create --web` PR from
  your fork. Every public surface (commit message, branch name, PR
  title, PR body, newsfragment) is scrubbed for CVE / the tracker
  repo slug / `vulnerability` / `security fix` leakage before being
  written or pushed. The skill refuses to operate on reports that are still being
  assessed, or on issues that need the private-PR fallback of
  [Step 9](../security/process.md#step-9--open-a-private-pr-exceptional-cases). See
  [Steps 7–11 in the process reference](../security/process.md#step-7--self-assign-and-implement-the-fix)
  for the full expectations around a fix PR.

Every skill is a **proposal engine**, not an auto-pilot — it reads the
world, proposes changes, and waits for your explicit confirmation
before applying anything. This is deliberate: you stay in the loop
for every label change, every body edit, every email draft, and
every line of code the fix skill writes.

The full list of skills, and what each one does, is in
[`AGENTS.md` — Reusable skills](../../AGENTS.md#reusable-skills).

# Proactive work and process improvements

Beyond reacting to inbound reports, you are also welcome to
proactively look for security improvements in the adopting project.
Take a look at the tracker's Discussions tab
(`https://github.com/<tracker>/discussions`) — we occasionally start
a discussion there when we see we can improve something, process-wise
or tooling-wise. Join those discussions,
share your perspective, or start new ones if you see something
worth fixing.

PRs against any part of our process are welcome. The documents that
shape the team are small enough to read in one sitting:

- [`README.md`](../../README.md) — the end-to-end handling process.
- [`<project-config>/canned-responses.md`](<project-config>/canned-responses.md) — reply templates.
- [`AGENTS.md`](../../AGENTS.md) — agent-facing conventions and confidentiality rules.
- `.apache-magpie-overrides/user.md` — per-user configuration
  (governance-gate status per
  `<project-config>/project.md → governance.cve_allocation_gate`,
  local clone paths, optional tool backends) scaffolded during adoption.
- [`<project-config>/`](<project-config>/) — project-specific content
  (roster, release trains, security model, scope labels, milestones,
  canned responses, fix-workflow specifics) — lives in the adopter's
  tracker repo.
- [`how-to-fix-a-security-issue.md`](how-to-fix-a-security-issue.md) —
  high-level fix workflow.
- [`new-members-onboarding.md`](new-members-onboarding.md) — this
  document.

**That's about it. Welcome to the team!**
