<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Assess

**All contribution tracks carry equal weight.** The Apache Way
recognises code, code review, documentation, testing, community
support, release management, mentoring, and mailing-list
participation as fully valid paths to committership and PMC
membership. A contributor can be nominated with zero code
contributions. This skill does not privilege any track over
another — it reports evidence across all tracks and lets the
PMC judge.

**Merit is project-specific and earned, not imported.**
Two anti-patterns the PMC should be on guard against:

- **Title-based nomination**: giving committership to someone
  because of their job title (CEO, CTO, VP, Distinguished
  Engineer, etc.) rather than their contributions to *this*
  project. External seniority does not transfer. A technical
  luminary who has not yet contributed meaningfully to this
  community has not yet earned merit in it.
- **Reputation import**: nominating someone on the strength
  of their broader technical standing or their contributions
  to *other* projects. The Apache Way evaluates what someone
  has done for *this* project and *this* community.

Neither pattern is compatible with the Apache meritocracy
model. The PMC guide is explicit: PMCs should "review
productive contributors *to their project*" when considering
nominations (pmc policy, "Project committer management").
If the nomination brief cannot point to concrete contributions
to this project — across any valid track — the PMC should
ask whether the nomination is premature.

Assessment draws on two sources:

1. **GitHub activity** — collected automatically in
   [`fetch.md`](fetch.md). Covers code, review, and issue tracks
   only. It is not a complete picture of contribution.
2. **Off-GitHub signal** — gathered interactively in Step 3 of
   [`SKILL.md`](SKILL.md). Covers mailing list, documentation,
   community support, talks, release management, mentoring, and
   anything else the maintainer supplies. For many contributors
   this will be the primary evidence.

These two sources are what populate the contribution tracks. The
community-interaction assessment (Part 1a — tone, welcoming
newcomers, conflict handling) describes *how* the candidate works,
not *what* they contributed; do not re-count it as a contribution
track. Mentoring, for instance, counts as a mentoring track only
when the nominator supplies it as off-GitHub signal, not because
"welcoming to newcomers" was noted under community interaction.

**Committership is about trust, not just output.** When a PMC
votes to add a committer, it is extending trust — write access
to the repository and the right to act as a steward of the
project. The question is not only "has this person done
enough?" but "do we trust this person to act in the project's
best interests?" Contribution volume is evidence toward that
question; it is not the answer.

**Community over Code.** The ASF's central principle is that
a healthy, sustainable community matters more than any
individual's technical output. A contributor who builds
community — welcoming newcomers, resolving conflict
constructively, helping users, sustaining the mailing list —
may be more valuable to the project than a prolific committer
who drives contributors away. This brief should reflect that
priority, not subordinate it to line counts.

**There are no universal thresholds.** The bar varies enormously
across ASF projects — by project size, velocity, culture, and
the candidate's specific track. The skill reports raw numbers
and nominator-supplied context, and lets the PMC judge against
the project's own bar. Ratings are only applied when the
project's `contributor-nomination-config.md` explicitly
declares thresholds calibrated to that project.

---

## Part 1 — GitHub activity summary

Report the raw counts from [`fetch.md`](fetch.md) without
applying ratings unless thresholds are declared in
`<project-config>/contributor-nomination-config.md`:

| Area | Count | Rating (if configured) |
|---|---|---|
| PRs opened | N | — or configured rating |
| PRs merged | N | — or configured rating |
| Reviews given | N | — |
| Substantive reviews | N | — |
| Issues filed | N | — |
| Issue / PR comments | N | — |

If the config declares thresholds, apply them and show the
rating. If not, apply the **low-bar defaults** below — clearly
labelled in the brief as defaults, not project-specific
standards — alongside the project-context note from Step 3:

| Area | Default low bar (committer) | Default low bar (PMC) |
|---|---|---|
| PRs merged | ≥ 5 | ≥ 10 |
| Reviews given | ≥ 3 | ≥ 8 |
| Substantive reviews | ≥ 2 | ≥ 4 |
| Comments | ≥ 5 | ≥ 10 |

These defaults represent a reasonable low bar for a mid-size
active project — not a universal standard. Two important
caveats:

- **Some projects set much higher bars.** Large, high-velocity
  projects may expect significantly more before nominating.
  Always calibrate against the project's own recent nominations.
- **Some projects give committership more freely.** A few ASF
  projects nominate contributors after very small contributions
  as a welcoming gesture. If that is this project's culture,
  set thresholds accordingly in
  `<project-config>/contributor-nomination-config.md` — do not
  let framework defaults imply the project is doing it wrong.

When the brief is rendered, label any rating drawn from defaults
with *(framework default — calibrate for your project)* so the
PMC knows not to treat it as the project's own standard.

---

## Part 1a — Community interaction (nominator-supplied)

Contribution volume is visible from GitHub. *How* someone
interacts is not. A contributor with dozens of merged PRs who
is dismissive in reviews, abrasive on the mailing list, or
unwelcoming to new contributors may be a poor choice for
committership regardless of their output. Conversely, someone
with modest GitHub activity who consistently helps others and
builds community trust may be exactly what the PMC needs.

This section is nominator-supplied and cannot be automated.
Ask the nominator to assess the following from their own
observation and knowledge:

- **Response to feedback**: when their own contributions
  receive critical review, do they engage constructively or
  defensively? Do they update work based on feedback?
- **Quality of reviews given**: are their reviews of others'
  work helpful and collegial, or nitpicky and discouraging?
- **Mailing list and discussion tone**: do they participate
  in disagreements constructively? Do they help resolve
  conflict or escalate it?
- **Welcoming to newcomers**: do they help new contributors
  find their footing, or ignore or dismiss them?
- **Any known incidents**: has the nominator *directly
  observed or seen documented evidence of* behaviour that
  would concern the PMC — e.g. harassment, sustained
  abrasiveness, bad-faith arguments, or conduct that drove
  contributors away? Do not relay rumour or second-hand
  accounts; if the nominator has not witnessed it or seen
  it on a public or private archived list, it should not
  appear in the brief.

Record responses verbatim. If the nominator has no concerns,
say so explicitly — silence looks like an omission. If there
are concerns, record them plainly and let the PMC decide; do
not soften or omit them.

If the nominator cannot assess community interaction — for
example, they only know the contributor through code — note
this explicitly in the brief. The PMC should know that
community behaviour was not evaluated.

---

## Part 2 — Off-GitHub signal (nominator-supplied)

Before assessing or rendering anything, ask the nominator for
off-GitHub contributions per the prompt in
[`SKILL.md` § Step 3](SKILL.md#step-3--gather-off-github-signal-and-project-context).

**Do not ask the candidate.** ASF nominations are conducted
privately on the project's private@ list; the candidate is
typically not informed until the vote passes and they accept.
Off-GitHub signal must come from the nominator's own
observations and from publicly searchable sources — mailing
list archives at `lists.apache.org`, public blog posts,
conference talk records, and so on — not from approaching
the candidate directly.

Record responses verbatim. Do not paraphrase. Do not rate or
score off-GitHub contributions — the nominator's words are the
evidence; the PMC draws its own conclusions.

If all areas are left blank, include this warning in the brief:

```text
[WARNING] No off-GitHub signal was provided. The brief below
reflects GitHub activity only. An ASF nomination thread should
address mailing list participation, community involvement, and
other contributions not visible in the repository. The
nominator should supply this context before sending.
```

---

## Part 3 — Project-context calibration (nominator-supplied)

In Step 3, after asking about off-GitHub contributions, ask
the nominator one additional question:

> *What does a typical successful committer nomination look
> like on this project? For example: what contribution tracks
> does your PMC value most, roughly how much activity do they
> look for, and are there any non-code contributions that have
> been decisive in past nominations?*

Record the response verbatim. This appears in the brief as
**"Project bar (nominator-supplied)"** immediately before the
Contributions table, so the PMC reading the brief has the
right frame of reference when they see the numbers.

If the maintainer does not know or leaves this blank, include:

```text
[NOTE] No project-specific bar was provided. The PMC should
interpret the numbers below against their own understanding of
what this project typically expects.
```

If the project's `contributor-nomination-config.md` declares
thresholds, those take precedence and this question can be
skipped (the config is the canonical statement of the bar).

If the nominator's response reveals that the project's bar is
based on job title, external seniority, or imported reputation
rather than demonstrated contribution to the project, note
this in the brief:

```text
[MERIT NOTE] The project bar described by the nominator
appears to weight [title / external reputation] rather than
contribution to this project. The PMC may wish to consider
whether this is consistent with ASF merit principles, which
are project-specific and based on demonstrated contribution.
```

---

## Activity timeline

From the month-bucket map produced in [`fetch.md`](fetch.md),
render a neutral month-by-month bar showing when GitHub
activity occurred across `<window>`. This is a factual record,
not a rating. Do not attach labels like "sustained" or
"sparse" — they imply recency is a virtue, which it is not.

**Merit once gained never expires.** A contributor who did
foundational work and has been less active recently has not
lost their standing. The timeline is context for the PMC, not
a score. A quiet recent period may reflect life circumstances,
a shift to off-GitHub contribution, or simply that the work
is done — none of these diminish prior contributions.

Also fetch and display **lifetime totals** (all-time PR count,
review count, issue count on `<upstream>`, not bounded by
`<window>`) alongside the window counts. A contributor with
significant historical contributions should not appear thin
because the assessment window is short.

If the maintainer's off-GitHub input indicates activity during
months with no GitHub events, note it alongside the relevant
months in the timeline — do not let a GitHub gap imply an
absence from the project.

---

## Quality signals (GitHub-derived)

Report these as plain numbers, not ratings:

| Signal | Value |
|---|---|
| PR merge rate | `merged / (merged + closed_not_merged)` % |
| Substantive review ratio | `substantive / total_reviewed` % |
| Issues that attracted discussion | `issues_with_discussion / total_filed` % |

Do not attach good/bad labels to these values. A low merge rate
may mean the contributor experiments openly; a high one may
mean they only open PRs they are very confident in. Context
from the maintainer matters more than the number alone.

---

## Vendor neutrality

ASF policy requires that committers and PMC members participate
as individuals, not as representatives of their employer.
Two specific policies ground this:

- **`project_independence`**: *"the board may apply extra
  scrutiny to PMCs with low diversity (i.e. PMCs that are
  dominated by individuals with a common employer)"*
- **`board_reporting`**: *"A healthy project should survive
  the departure of any single contributor or employer of
  contributors"*

The PMC should have the employer context before voting —
not because shared employer is itself a problem, but because
ASF values require each member to act as an individual.
A PMC where several members share an employer is fine if
those members vote and participate independently. The board's
concern, per `project_independence`, is PMCs *dominated* in
a way that compromises independence — not mere headcount.

Include an employer context section in every brief:

1. **Candidate employer**: `<employer>` as resolved in Step 0
   and confirmed (or flagged unconfirmed) in Step 3.

2. **Existing members from the same employer** (nominator-
   supplied from Step 3): how many current committers and PMC
   members share the employer. Present this as neutral context,
   not a warning. If the nominator did not know, say so.

3. **Only flag if independence may be at risk**: do not flag
   merely because the number is non-zero or even high. Flag
   only if the nominator has supplied information suggesting
   the employer has coordinated or directed PMC decisions —
   e.g. multiple members voting the same way under apparent
   employer pressure, or a pattern of employer-driven
   decisions. In that case surface it explicitly:

   ```text
   [EMPLOYER CONTEXT NOTE] <N> current PMC members are known
   to work for <employer>. The nominator has noted [specific
   pattern]. The PMC may wish to consider whether independent
   participation is being upheld as required by ASF policy
   (project_independence).
   ```

   If the number is high but there is no evidence of
   coordination, render it as plain context with no flag:

   ```text
   Employer context: <N> current PMC members also work for
   <employer>. No concerns about independent participation
   were noted by the nominator.
   ```

4. **If employer is unconfirmed**: note it without alarm.

   ```text
   Employer context: could not be confirmed. The nominator
   may wish to verify before sending.
   ```
