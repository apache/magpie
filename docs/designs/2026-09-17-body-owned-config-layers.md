<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Body-owned configuration layers](#body-owned-configuration-layers)
  - [What is wrong](#what-is-wrong)
  - [Decisions](#decisions)
    - [What a stage overlay contains](#what-a-stage-overlay-contains)
    - [Graduation](#graduation)
  - [What has to be built](#what-has-to-be-built)
  - [Alternatives considered](#alternatives-considered)
  - [Risks](#risks)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Body-owned configuration layers

| | |
|---|---|
| **Status** | Proposed. Nothing built. Depends on agreement from the Incubator PMC and ComDev, who would own two of the layers. |
| **Created** | 2026-09-17 |
| **Origin** | The question "should podling onboarding move to `apache/incubator`?" — and the discovery that the answer is no, because the thing that should move is not a skill. |

A skill that serves two governance stages does not want splitting. What wants
splitting is **who owns the values it branches on**, and today nobody does:
each project retypes them.

## What is wrong

`committer-onboarding` walks a nominator from a passed vote to a welcomed
committer. It serves both incubating podlings and graduated top-level
projects, and the difference between them is already parameterised:

```yaml
committer_governance_asf_pmc:
  stage: podling | tlp
  whimsy_roster_url: TODO   # .../roster/ppmc/<x>  vs  .../roster/committee/<x>
```

The procedure is one procedure. The branch is data. That much is right.

What is wrong is where the data comes from. `whimsy_roster_url: TODO` is
filled in per project, by hand. So is the PPMC vote bar, and
`private@<podling>.incubator.apache.org`, and every other value that follows
from *being a podling*. This is knowledge the Incubator PMC holds centrally
and every podling copies separately.

Three consequences, in increasing order of seriousness:

- **Retyping.** Every podling writes the same values.
- **Drift.** When the Incubator changes something, forty podlings are wrong
  and nobody knows which.
- **Graduation is a rewrite.** Moving from podling to TLP should be one line.
  Today it means hand-editing every value the stage implies.

The failure mode this design exists to prevent is the second one. A config
value copied from another body is a snapshot of their policy, and it goes
stale silently.

## Decisions

**Four layers, each owned by whoever knows the answer.**

| Layer | Owner | Holds |
|---|---|---|
| Procedure — the skill | Magpie | The steps, in order, and where the decision points are |
| Organization defaults | The organization (`organizations/ASF/`) | ICLA, secretary request, Whimsy, karma — true of every ASF project |
| **Stage overlay** — new | **Incubator PMC** (podling) · **ComDev** (TLP) | What `stage: podling` or `stage: tlp` actually implies |
| Project config | The project | Only what is genuinely this project's |

Resolution is most-specific-wins: **project → stage → organization → framework
default**. A project that needs to differ still can; it just no longer has to
in order to be correct.

**The skill does not move, and does not split.** It stays one procedure with
one branch. Moving it to `apache/incubator` would hand the Incubator PMC
ownership of TLP onboarding, which is not their domain. Splitting it produces
two skills that are ~80% identical and will diverge, in a procedure where
divergence means a committer is onboarded wrongly.

**Each body edits only its own file, in its own repository.** This is the
property that makes the design worth building at all. It follows
[`MISSION.md`](../../MISSION.md) — *"Those teams choose whether to contribute
a skill into Magpie or keep it in their own repository and let Magpie install
it by reference — Magpie does not reach into another team's domain on its own
initiative."* A stage overlay is that sentence applied to configuration rather
than to skills.

**Magpie reconciles; neither body needs to know the other exists.** The
Incubator describes podlings. ComDev describes graduated projects. Magpie
resolves the layers and hands the skill one merged view. Neither overlay
references the other, and neither is aware it is one of two.

### What a stage overlay contains

Incubator-owned, illustrative:

```yaml
# organizations/ASF/stages/podling.md — sourced from apache/incubator
stage: podling
governing_body: PPMC
whimsy_roster_url: https://whimsy.apache.org/roster/ppmc/<project>
private_list: private@<project>.incubator.apache.org
vote_rule: 3 binding PPMC +1s, no binding veto
binding_voters: current PPMC members
```

ComDev-owned, for the other stage: the same keys with TLP values.

Note what is *not* in there: no procedure, no prose, no steps. An overlay is a
value set. That boundary is what stops the layers becoming two forks of the
same document.

### Graduation

```diff
- stage: podling
+ stage: tlp
```

Every value the stage implies swaps with it. Anything the project genuinely
overrode stays overridden, because project beats stage.

## What has to be built

Two mechanisms, neither of which exists:

1. **A stage tier in config resolution.** Today it is organization → project.
   This needs a body-owned tier between them, and a key to select which
   overlay applies.

2. **Sourcing a configuration *fragment* from an external repository.**
   [`skill-sources`](../skill-sources/README.md) can redirect a *whole skill*
   (`skills/<name>/source.md`) to an external, pinned source. There is no way
   to say "this configuration block comes from `apache/incubator` at tag X".

   **The trust and pinning half of this already exists, and already points at
   the Incubator.** `organizations/ASF/skill-sources.md` curates
   `apache/incubator` as an ASF source today:

   ```yaml
   - id: apache-incubator
     organization: ASF
     name: "Apache Incubator skills"
     maintainer: "Apache Incubator PMC"
     method: git-tag
     url: https://github.com/apache/incubator
     ref: releasecheck-0.5.1
     commit: 876cf205869a9e12aa55ad070efae65658c8a34e
   ```

   So the IPMC is already a source Magpie consumes from, by tag, with a
   recorded commit — `releasecheck` arrives that way. This design does not ask
   them to become one; it asks them to publish a second, much smaller kind of
   artefact through the arrangement they already have. The missing piece is
   narrowly that a source can currently only supply a whole skill.

The second is the load-bearing one, and it is why this is a design rather than
a patch. Without it, Magpie would *copy* the Incubator's values into its own
tree — which is the drift this design exists to prevent, reintroduced at the
framework level. Whatever is built must let the overlay be pinned to a ref in
the owning body's repository and updated by moving the pin, exactly as a
sourced skill is.

It generalises past onboarding. ComDev's shared data tools have the same
shape: centrally-known values, consumed by many projects, currently copied.

## Alternatives considered

**Move `committer-onboarding` to `apache/incubator`.** Rejected: it serves
TLPs too, so the Incubator PMC would own a procedure for projects outside
their remit. It also inverts the dependency — Magpie would consume its own
contributor-growth family from another PMC's release cadence.

**Split into `podling-onboarding` and `tlp-onboarding`.** Rejected: ~80%
duplicate, and the duplicated part is the substance (ICLA, account request,
karma, welcome). Two copies of a governance procedure drift, and the cost of
drift here is landed on a new committer.

**Leave it as project config and document the values well.** Rejected as the
status quo: it is exactly what produces `whimsy_roster_url: TODO` in every
podling's config. Better documentation makes the retyping more accurate; it
does not stop it, and it does not fix drift.

**Ship the overlays inside Magpie, maintained by us.** Tempting, and cheap,
and wrong. Magpie would be asserting what the Incubator's policy is. When it
changed we would find out late, from a podling that got it wrong. The whole
value is that the body that owns the policy owns the file.

**Put the stage values in `organizations/ASF/organization.md`.** Rejected: one
file cannot have two owners. The ASF organization file is ASF-common; podling
policy is the IPMC's and TLP policy is ComDev's. Merging them would make every
edit a cross-PMC negotiation, which is the thing being avoided.

## Risks

- **It needs two other PMCs to agree.** Neither is obliged to own a file for
  Magpie's benefit. If either declines, the fallback is the status quo for
  that stage, not a broken framework — the layer is optional by construction.
  The ask is smaller for the Incubator, who already publish `releasecheck`
  through the curated source above, than for ComDev, for whom this would be a
  first.
- **A pinned overlay can go stale too**, just visibly rather than silently:
  the pin names a ref and a date. That is the improvement, not a cure.
- **Two overlays invite a third.** The tier should stay narrow —
  organizational *stage*, not arbitrary grouping — or it becomes a second
  project-config layer with no owner.
