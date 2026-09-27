<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# security-model-verify — PR and mail templates

## Templates

### Template 1 — PR: wire the discoverability chain

**Title**: `Link the project's security model for agent discoverability`

**Body**:

```markdown
**This is a proposal for the maintainers to review — please correct,
reject, or discuss as needed.** Nothing here is a requirement.

This wires the conventional `AGENTS.md` → `SECURITY.md` → threat-model
chain so an automated agent can mechanically find the security model
this project already publishes at <path or URL>. It changes no model
content and edits no existing prose — it adds one section to each file
(creating the file where absent).

Why it matters: a scanner that cannot locate the model has to treat
every component as in scope and every property as unclaimed, which is
how a review turns into a hundred findings the maintainers have to
read. Finding the model first is what keeps the output small enough to
be worth your time.

Happy to adjust the wording or move the section if the project has a
house style for these files.
```

### Template 2 — PR: propose draft sections

**Title**: `SECURITY.md: draft additions for <section list>`

Append the generated sections; group every inferred claim into §1.18 open
questions. The body says, in order: this is a proposal; every claim carries a
provenance tag and the inferred ones are guesses to confirm or strike; here are
the sections and why each helps; what is needed back is a one-line
confirm/correct/strike per question, not composed prose; this PR edits no
existing content, and closing it is a fine answer.

### Template 3 — Mail: model gaps, maintainers drive

Recipients follow the project's configured security-list conventions. Plain
text. Signed by the human who sends it — this skill does not sign for anyone.

```text
Hi <name>,

Where the pre-flight on <PROJECT>'s security model stands:

- Discoverability: <passes, with a one-line note on how / addressed in
  <PR URL>, which wires AGENTS.md -> SECURITY.md -> your existing model
  at <path>. Adjust or close it as you see fit.>

- Completeness: your model is substantive on <the sections that landed
  well>. Measured against the Alpha-Omega threat-model rubric
  (https://github.com/alpha-omega-security/threat-model) we noticed a
  few gaps. None of these block anything; closing them mostly reduces
  the noise an automated review sends back to you:

    * §<NN> <name> — <what is missing, and what it would let a triager
      decide. Be specific and cite the section.>
    * §<NN> <name> — ...

Two ways forward, both fine by us:

  1. You drive — work through the gaps and ping us for a re-check.
  2. We draft — we run the model producer against your public
     artefacts, open a PR with tagged draft sections, and collect the
     open questions at the end, so you react to something concrete
     instead of composing from scratch. Usually faster.

No deadline attached.

<signature>
```

### Template 4 — Mail: the chain does not resolve

Same conventions. Says: discoverability currently fails, here is exactly where
the chain breaks, this is the one hard gate because an agent that cannot find the
model cannot use it — and then hands the decision back: the model can live in
`SECURITY.md`, in an in-repo file, on the project site, or in an umbrella repo,
and the maintainers pick. Offer the wiring PR once they have. Do not touch the
repository before they answer.
