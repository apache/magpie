<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Security model preparation](#security-model-preparation)
  - [Why a project wants one at all](#why-a-project-wants-one-at-all)
  - [The rubric is external, and stays external](#the-rubric-is-external-and-stays-external)
  - [Discoverability: the one hard gate](#discoverability-the-one-hard-gate)
  - [Why mail, and not a public issue](#why-mail-and-not-a-public-issue)
  - [Public-surface discipline](#public-surface-discipline)
  - [Draft-first, and the provenance tags that make it safe](#draft-first-and-the-provenance-tags-that-make-it-safe)
  - [The asymmetry that governs every judgement call](#the-asymmetry-that-governs-every-judgement-call)
  - [The update loop, and why §1.15 is fenced](#the-update-loop-and-why-115-is-fenced)
  - [Adopter configuration](#adopter-configuration)
  - [Cross-references](#cross-references)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Security model preparation

The three `security-model-*` skills cover one lifecycle: getting a project's
security model **written**, **findable**, and **current**. This page is the
rationale behind them — the decisions that are the same for every adopter, kept
in one place so the skills do not each re-argue them.

| Stage | Skill | Question it answers |
|---|---|---|
| Produce | [`security-model-prepare`](../../skills/security-model-prepare/SKILL.md) | The project has no written model. What does one say, and how does it land without burning maintainer goodwill? |
| Verify | [`security-model-verify`](../../skills/security-model-verify/SKILL.md) | Can an agent find the model, and does it say enough to route a finding? |
| Update | [`security-model-update`](../../skills/security-model-update/SKILL.md) | Six months of triage decisions have happened. What does the model now say that it did not? |

## Why a project wants one at all

A security model is the *implicit contract* between a project and its downstream
users: the assumptions it makes about its environment, callers, and inputs; the
properties it upholds; the properties it explicitly does not; and the misuses
that are syntactically possible but outside the intended use.

It has two readers, and they need different things from the same document:

- The **downstream integrator**, deciding which threats the project has taken on
  and which are left to them.
- The **triager** — maintainer, security team, or automated pipeline — who has to
  classify an inbound report, a scanner finding, or an AI-generated analysis as
  valid, out of model, or disclaimed by design, *and cite the section that
  justifies the call*.

The second reader is why this matters more every year. Automated analysis
produces findings at a rate no maintainer can absorb by hand, and the only thing
that makes that volume survivable is a document the triage step can consult
before a human does. A project without one does not get fewer findings; it gets
the same findings with nobody able to close them cheaply.

## The rubric is external, and stays external

The specification of what a model contains is maintained publicly by
**Alpha-Omega**:

> <https://github.com/alpha-omega-security/threat-model>

That repository ships an orchestrator plus specialists — recon, surface,
interview, authoring, backtest, sidecar, triage — with the section structure
(§1.1–§1.19), the provenance tag set, and the closed disposition set with its
precedence order in `skills/threat-model/references/`.

Magpie **references it by URL and does not vendor, mirror, or fork it.** Two
reasons:

1. **A second copy of a specification is a second specification.** It drifts, and
   the drift shows up as a maintainer being told their model is incomplete
   against a rubric nobody upstream recognises.
2. **The rubric is the part most likely to improve.** Pinning a snapshot of it
   inside Magpie would freeze the least stable and most valuable input.

What Magpie owns is everything *around* the rubric: the consent conversation, the
discoverability chain, the PR mechanics, the confidentiality scrubbing, and the
feedback loop from triage history back into the document. Those are governance
and workflow concerns, which is Magpie's half of the problem.

The skills therefore cite section numbers (§1.15 known non-findings, §1.17
dispositions) as coordinates into the upstream document. When upstream renumbers,
the fix is to update the citing tables — not to start keeping a local copy.

## Discoverability: the one hard gate

An agent finds a project's model by following a fixed chain:

```text
AGENTS.md  ->  SECURITY.md  ->  <the model>
```

Any of four terminations is fine: the model embedded in `SECURITY.md`, an in-repo
file, a project-site URL, or an umbrella model in another repository (the normal
shape for build tooling, language ports, and other satellites).

This is the only check that is allowed to *block*. The reasoning is narrow: a
model an agent cannot reach is not a worse model, it is an absent one — the
scanner has to treat every component as in scope and every property as unclaimed,
and the output is the hundred-finding review the model existed to prevent.
Completeness, by contrast, is graded: gaps are proposals the maintainer decides
on. Nothing in the completeness rubric is a precondition for anything.

The chain is also cheap to fix, which is why it gets a PR rather than a
conversation. Adding one section to `AGENTS.md` needs no maintainer input, and
the diff is small enough to review in the time it takes to read the title.

## Why mail, and not a public issue

Everything substantive — model gaps, missing sections, a broken link the project
owns — goes to the project's private security list, never to a public tracker.
Three independent reasons, any one of which would be sufficient:

1. **Many projects have no usable public tracker.** Issues are disabled on the
   forge, or the project tracks work in a different system entirely. The issue
   cannot be filed.
2. **A public list of a project's threat-model gaps is an inventory.** "The
   maintainers acknowledge they do not check X" is exactly what a hostile
   researcher would mine, and publishing it is a favour to them. The private list
   keeps the same content among people the project has already vetted.
3. **Maintainers who read mail may never see a tracker notification.** The
   conversation almost always starts as mail; continuing it there reaches
   everyone, including the members who never look at the forge.

PRs are the deliberate exception. They need a repository write anyway, the diff
*is* the artefact being ratified, and "add one link line" carries no inventory
worth withholding.

## Public-surface discipline

PR titles, PR bodies, commit messages, and branch names on a target repository
are public forever. Two rules apply to all of them:

- **No scan-programme, vendor, or engagement identity.** The public-facing
  rationale is *"improving the discoverability of the project's security model
  for automated scanners"*. Who is running the review and under what arrangement
  is information the security team controls the disclosure of; putting it in a
  commit message forecloses later choices and hands anyone a single string to
  grep for. On the private list it is fine — that surface is already inside the
  trust boundary.
- **No tracker contents.** A tracker URL or `#NNN` reference is a stable
  identifier and is public-safe; the page behind it stays access-gated. Its
  *contents* — issue bodies, comment text, team debate, labels, assignees — are
  not. See the confidentiality rules in [`AGENTS.md`](../../AGENTS.md).

This bites hardest in `security-model-update`, whose entire input is private
tracker material and whose entire output is a public document. Its scrub step is
not a formality.

## Draft-first, and the provenance tags that make it safe

A blank-page request — *"could you write up your threat model?"* — is an
unbounded ask, and it is why most of these efforts produce nothing. A tagged
draft is a bounded one: the maintainer reads claims someone else wrote and says
yes, no, or *not quite* per line. Reacting is far cheaper than composing, and the
corrections are where the real model surfaces.

That inverts the usual risk, though. A draft written by someone who is not the
maintainer, in the maintainer's voice, is a document that can quietly launder a
guess into the project's official position. The provenance tags are what prevent
it:

| Tag | Means | Licenses closing a report? |
|---|---|---|
| documented | Lifted from a project artefact, cited | Yes |
| maintainer | Stated by a maintainer, dated | Yes |
| assumption | A working premise with an open question | Only under a declared relaxed policy, low blast radius, never security-critical |
| inferred | The drafter's guess, with an open question | **No** — it escalates, never closes |

No hedge variants. Every assumption and inferred claim resolves to a numbered
open question. A first draft with no inferred tags is overclaiming.

## The asymmetry that governs every judgement call

It appears in the backtest, in the update loop's regression check, and in the
rules for what may become a known non-finding. It is one sentence:

> Wrongly escalating a non-finding wastes a maintainer's afternoon. Wrongly
> closing a real vulnerability hands a reporter "not a bug" on a live issue.

So: when the evidence is ambiguous, prefer the wording that leaves reports
escalating. Narrow a claim to resolve a conflict; never widen one. A model that
closes an item the project historically fixed does not ship — that is the single
blocking outcome in both the initial backtest and every later update.

Disclaiming is the cheapest way to make an awkward routing disappear, which makes
it the easiest way to pass a quality gate while making the model worse. A
disclaimer added *because* an item routed badly is reverse-engineered from the
answer; it still has to be true of the project as it is, cite a real source, and
stay inside the scope that source covers.

## The update loop, and why §1.15 is fenced

Known non-findings (§1.15) are the recurring-false-positive list, and the section
an automated triager is fed verbatim as a negative prompt. They are also **first**
in the disposition precedence order, which means an entry there pre-empts every
scope, configuration, dependency, adversary, and property check below it.

A loose entry therefore does not mis-classify one report — it suppresses a class
of them, ahead of every other safeguard the model has. Hence the fence:

- Only two routes feed §1.15: a recurring `BY-DESIGN: property-disclaimed` close,
  and an already-established known non-finding recurring again.
- Nothing under `OUT-OF-MODEL:*` is ever promoted. Those routes sit *below* §1.15
  in the precedence order; relabelling one lifts it above the checks that decided
  it, and the class widens without anyone deciding to widen it.
- Match conditions describe the behaviour of the code, never the quality of the
  report. *No reproducer* is not a disposition — an unreproduced report stays
  open pending a reproducer.
- The discharging claim must exist in the model and must cover the entry's
  component.
- Two independent occurrences minimum. One close is a decision; two with the same
  discharging claim is a pattern.

The other half of the update loop is the **gap list**, and the uncomfortable
entries are the valuable ones. A model that routes an item the opposite way to
how the team actually resolved it, or a rejection a reporter successfully argued
the team out of, is the model failing in the expensive direction under real
conditions with an independent reviewer. Two reversals against the same claim
mean that claim is wrong.

A canned response in
[`<project-config>/canned-responses.md`](../../projects/_template/canned-responses.md)
that cites no model section is a gap by definition — the project is stating a
position in reporter mail that its own model does not hold. That is precisely
what the drafting rule in
[`<project-config>/security-model.md`](../../projects/_template/security-model.md)
warns about, and this loop is what closes it.

## Adopter configuration

The three skills read
[`<project-config>/security-model.md`](../../projects/_template/security-model.md):
the authoritative model URL, the repositories in scope and their shape (in-repo
model or pointer to an umbrella), the private list to route substantive
conversation to, and the branch and license-header conventions the PR helper
needs. Everything else comes from `project.md`.

## Cross-references

- [`README.md`](README.md) — the security skill family index.
- [`process.md`](process.md) — the report-handling lifecycle whose dispositions
  feed the update loop.
- [`confidentiality.md`](../confidentiality.md) — what may cross to a public
  surface.
- [`poc-handling-policy.md`](poc-handling-policy.md) — what an agent may do with
  reporter-supplied proof-of-concept code encountered while mining the corpus.
