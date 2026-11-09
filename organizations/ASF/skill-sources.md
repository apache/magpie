<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Apache Software Foundation — curated skill sources](#apache-software-foundation--curated-skill-sources)
  - [Curated sources](#curated-sources)
    - [Apache Incubator](#apache-incubator)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Apache Software Foundation — curated skill sources

The external [skill sources](../../docs/skill-sources/README.md) the ASF
organization **vouches for**. A project that sets `organization: ASF` sees
these as candidate sources it *may* adopt — curation is **not**
installation. The project still opts each one in by committing its pin to
[`<project-config>/skill-sources.md`](../../plugins/magpie-setup/templates/skill-sources.md).

## Curated sources

Each entry is a [source descriptor](../../docs/skill-sources/README.md#source-descriptor).
To add another, declare it here and add a row to the *Org-curated sources*
table in [`docs/skill-sources/registry.md`](../../docs/skill-sources/registry.md).

### Apache Incubator

Skills the Incubator PMC maintains in
[`apache/incubator`](https://github.com/apache/incubator) under
[`tools/skills/`](https://github.com/apache/incubator/tree/HEAD/tools/skills)
for podlings, mentors and the IPMC.
There are two ways to install them, and they do not conflict:

- **Through Magpie, for any agent.**
  A project that trusts the source gets each pinned skill with
  `/magpie-setup:setup skill-sources`, wired into `.agents/skills/` and relayed
  to every agent's skills directory like a framework skill.
  This is the path for an adopted repo, and the only one for agents with no
  marketplace (OpenCode, Pi, Goose).
- **From the Incubator's own marketplaces, without Magpie.**
  The repo carries a plugin catalog per agent; the *Marketplaces* column below
  says which ones list a skill:

  | Marketplace | Add it | Catalog in `apache/incubator` |
  |---|---|---|
  | `claude-code` | `/plugin marketplace add apache/incubator` | `.claude-plugin/marketplace.json` |
  | `codex` | `codex plugin marketplace add apache/incubator` | `.agents/plugins/marketplace.json` |
  | `copilot` | add `apache/incubator` as a VS Code / GitHub Copilot plugin marketplace | `marketplace.json` |

  Updates then arrive through the agent's own plugin update.

**Pinning and updates.**
The Incubator versions each skill on its own, tagging it `<skill>-<version>`
(for example `releasecheck-0.5.1`), so each skill is curated as its own
descriptor pinned to its own tag: `apache-incubator` for `releasecheck`, and
`apache-incubator-<skill>` for each skill pinned after it.
A skill kept as a plugin directory (`tools/skills/<skill>/skills/<skill>/SKILL.md`,
the layout Codex needs to find it) is pinned with
`skills_root: tools/skills/<skill>/skills`; the drift check still scans
`tools/skills/` for its siblings.
A pin moves only when it is updated here, and an adopter's committed pin moves
only when the adopter bumps it; `/magpie-setup:setup skill-sources` then
re-fetches and re-verifies the new tag.

#### What the Incubator ships

Every skill in `tools/skills/`, and how it can be installed today.
Most of these skills read the Incubator's own MCP servers (reports, podlings,
health, mail archives); each skill names the ones it needs, and the
[Incubator skills README](https://github.com/apache/incubator/blob/HEAD/tools/skills/README.md)
says how to set them up.

<!-- BEGIN SKILL-SOURCE CATALOGUE: apache-incubator -->
| Skill | What it does | Install through Magpie | Marketplaces |
|---|---|---|---|
| `releasecheck` | Checks a podling release candidate before or during its vote; findings for a person to review, never a vote. | `pinned` | `claude-code`, `codex` |
| `maturity-model-assessment` | Builds an evidence pack against the 38 items of the Apache Project Maturity Model, marking each evidenced, proxy or human; never a score. | `untagged` | — |
| `graduation-self-assessment` | Compares the `ipmc` MCP's graduation-readiness verdict with what the podling says in its own reports, checked against the mail archives. | `single-file` | — |
| `graduation-packet-builder` | Assembles a podling's graduation case and drafts the DISCUSS email and the board resolution. | `single-file` | — |
| `retirement-shepherd` | Assesses whether a stalled podling should retire and drafts the discussion, the announcement and the shutdown checklist. | `single-file` | — |
| `monthly-report-review` | The monthly IPMC report review: who has not filed, narratives against health data, draft shepherd comments. | `single-file` | — |
| `release-vote-reviewer` | Walks a release vote thread on general@ and drafts the +1 or the -1 with reasons. | `single-file` | — |
| `board-report` | Drafts the VP Incubator's quarterly report to the ASF board. | `single-file` | — |
| `branding-sweep` | Trademark and branding check across all current podlings, as a ranked fix list. | `single-file` | — |
| `podling-onboarding` | Reviews a new podling's proposal against the checklist and bootstraps its tracking. | `single-file` | — |
| `podling-name-clearance` | Runs the podling name search end to end and writes it up in the required format. | `single-file` | — |
| `asf-list-archaeology` | Not yet published (kept in `tools/skills/draft/`). | `draft` | — |
<!-- END SKILL-SOURCE CATALOGUE: apache-incubator -->

What *Install through Magpie* means:

- **`pinned`** — in a descriptor's `provides` below.
  An adopter that trusts that descriptor gets it with
  `/magpie-setup:setup skill-sources`.
- **`untagged`** — already a `<skill>/SKILL.md` directory, which is the layout
  Magpie fetches, but there is no release tag to pin yet.
  It moves to `pinned` once the Incubator tags it.
- **`single-file`** — a single `<skill>.md` with its supporting files kept in
  shared `scripts/`, `templates/` and `references/` directories.
  Magpie wires a skill directory, and a marketplace installs one, so neither
  can install these as they are; moving each into its own directory, as
  `releasecheck` already is, is proposed to the Incubator.
  Until then, build one with the Incubator's own packager and unpack it:
  `python3 tools/skills/package-skills.py <skill>` in an `apache/incubator`
  checkout, then `unzip dist/<skill>.skill -d ~/.claude/skills/`.
- **`draft`** — not published by the Incubator; listed so it is not missed
  when it is.

The table is checked against `apache/incubator` every week by the
[`skill-source-drift`](../../.github/workflows/skill-source-drift.yml)
workflow, which runs
[`tools/dev/check-skill-source-drift.py`](../../tools/dev/check-skill-source-drift.py)
and opens an issue when a skill was added, removed, re-laid-out or tagged,
when a marketplace catalog gained or lost it, or when a newer tag exists for a
pin — which is when a maintainer moves the pin here.

**Podlings: prefer `releasecheck` over `release-verify-rc`.** Magpie's
`release-verify-rc` does not distinguish a podling release from a TLP one, so
it does not check the things that make a podling RC valid — `incubating` in
the archive names, a present `DISCLAIMER`, the two-stage PPMC-then-IPMC vote.
`releasecheck` is the IPMC's own check, maintained by the body that sets those
rules. A podling verifying an RC should run it instead; a TLP has no reason to.
This is a recommendation, not wiring — nothing resolves it automatically today.
Making the choice follow from `stage: podling` is part of
[body-owned configuration layers](../../docs/designs/2026-09-17-body-owned-config-layers.md#worked-example-the-podling-release-procedure),
which is proposed and not built.

```yaml
- id: apache-incubator
  organization: ASF
  name: "Apache Incubator skills"
  maintainer: "Apache Incubator PMC"
  method: git-tag
  url: https://github.com/apache/incubator
  ref: releasecheck-0.5.1
  commit: 876cf205869a9e12aa55ad070efae65658c8a34e
  layout:
    skills_root: tools/skills
    evals_root: tools/skills/evals
  provides:
    - skill: releasecheck
```
