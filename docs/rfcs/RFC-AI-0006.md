<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [RFC-AI-0006: Trusted external skill sources](#rfc-ai-0006-trusted-external-skill-sources)
  - [Abstract](#abstract)
  - [Status of this document](#status-of-this-document)
  - [Motivation](#motivation)
  - [Proposal](#proposal)
    - [The three-layer trust model](#the-three-layer-trust-model)
    - [Source descriptor](#source-descriptor)
    - [Pointer file — the redirect](#pointer-file--the-redirect)
    - [Fetch, verify, pin](#fetch-verify-pin)
    - [Symlink and eval binding](#symlink-and-eval-binding)
    - [Amending PRINCIPLES §13](#amending-principles-13)
  - [Security model](#security-model)
  - [Drawbacks](#drawbacks)
  - [Alternatives considered](#alternatives-considered)
  - [Out of scope](#out-of-scope)
  - [References](#references)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# RFC-AI-0006: Trusted external skill sources

## Abstract

Every Magpie skill ships in one repository — `apache/magpie` — and reaches
adopters through one mechanism: the [`setup`](../../skills/setup/SKILL.md)
skill downloads the whole framework into a gitignored snapshot, pins it in a
committed lock, and symlinks the selected skills into agent dirs. There is
no way to pull an individual skill or skill-family from a **different**
repository or organization. The "External (another repo)" home in
[`docs/extending.md`](../extending.md) exists only as a "vendor it in by
hand" note, and [`PRINCIPLES.md` §13](../../PRINCIPLES.md#13-snapshot-plus-override-never-vendored-copies)
forbade installation from anything but the one framework snapshot.

This RFC introduces **trusted external skill sources**: a "redirect"
pointer where a skill directory would sit, naming a remote source (a GitHub
folder, an SVN/`dist` archive, or a git tag/branch) from which the skill and
**all its related files — including evals and tests** — are fetched, pinned,
verified, and wired in so the skill behaves identically to an in-tree one.
It amends §13 to permit installation from a **trusted** source — one the
adopter has explicitly vouched for — while keeping the snapshot-plus-pin
discipline, and adds a per-organization curation layer so the owning
repository/organization of every source is explicit.

## Status of this document

**Proposed.** The design lands in phases: **Phase A** — this RFC, the §13
amendment, the descriptor/pointer formats under
[`docs/skill-sources/`](../skill-sources/README.md), the org/project
`skill-sources.md` files, and `skill-and-tool-validator` support — is the
review checkpoint. **Phase B** — the `setup`-skill fetch/lock/symlink wiring
(`.apache-magpie.sources.lock`, `/magpie-setup skill-sources`, and the
`adopt`/`upgrade`/`verify` integration) plus a worked example — follows.

## Motivation

The framework is deliberately one skill-authorship boundary
([§14](../../PRINCIPLES.md#14-skills-are-the-unit-of-authorship)) with one
distribution channel. That is right for the core, but it blocks three real
needs already visible in the extension model:

1. **Sub-project and podling skills.** An ASF sub-project or incubating
   podling may maintain skills specific to itself that should not live in
   `apache/magpie` yet still be adoptable by its own repos with the same
   ergonomics as a framework skill.
2. **Organization-private skills.** A company or collective running Magpie
   across many repos wants to maintain a shared skill-family in one place
   and pull it into each repo — without vendoring copies or a submodule.
3. **Community skills.** A third party maintains a useful skill-family and
   others want to adopt it deliberately, pinned and verified, not by
   copy-paste.

Today all three fall back to "clone it in by hand" — unpinned, unverified,
and invisible to drift detection, `verify`, and the eval discipline. The
machinery to do this *properly* already exists for the framework itself: a
verified fetch (git tag/branch, or `svn-zip` with SHA-512 + GPG), a
committed pin, a two-lock drift model, and the canonical-plus-relay symlink
wiring. This RFC generalizes that machinery from **one** source to **N named
trusted** sources.

The one blocker is principle, not plumbing: §13 said catalogs are "for
discovery, never for installation." This RFC narrows that to "never for
*untrusted* installation" — an adopter-vouched, pinned, verified source is
as safe to install as the framework snapshot, because it *is* the same
mechanism.

## Proposal

### The three-layer trust model

Trust is layered so an organization can curate candidates while the adopter
keeps the final say. Nothing is fetched until the adopter opts in.

| Layer | File | Home | Role |
|---|---|---|---|
| **Discovery** | [`docs/skill-sources/registry.md`](../skill-sources/registry.md) | in-tree | Editorial index of known sources. Lists, never installs. |
| **Org-curated** | `organizations/<org>/skill-sources.md` | in-tree / adopter-local org override | An org vouches for candidate sources its projects may adopt. |
| **Adopter opt-in** | `<project-config>/skill-sources.md` | committed in the adopter repo | **The install gate.** Lists the trusted source ids and commits each pin. Only sources here are fetched. |

This mirrors the existing `project → organization → framework` precedence
([`AGENTS.md`](../../AGENTS.md#configuration-resolution-order)): an org
curates a default set; the adopter overrides — trusting a source the org did
not curate, or declining one it did.

### Source descriptor

A descriptor identifies one source and enumerates what it `provides`,
reusing the install-method and lock vocabulary the framework snapshot
already uses:

```yaml
id: <source-id>                 # unique, kebab-case
organization: <org>             # owning org; must name a directory under organizations/
name: "<human-readable name>"
maintainer: "<who>"
method: <git-tag | git-branch | svn-zip>
url: <repo or archive URL>
ref: <tag | branch | version>
# verification anchor: commit (git-tag) | sha512 (svn-zip)
layout:
  skills_root: skills
  evals_root: tools/skill-evals/evals
provides:
  - skill: <name>
  - family: <prefix>-*
```

### Pointer file — the redirect

Where a skill directory would sit, `skills/<name>/source.md` names the
source. It is the "redirect link"; the skill body, evals, and tests are
fetched into the gitignored snapshot, not committed here. It is named
`source.md` — **not** `SKILL.md` — so the validator's `SKILL.md`-gated
checks (required frontmatter, name convention, injection guard) do not fire
on a stub. Its frontmatter uses `source:` (already an allowed optional key)
plus `organization:`, `skill_path:`, and `evals_path:`. Full format in
[`docs/skill-sources/README.md`](../skill-sources/README.md#pointer-file--the-redirect).

### Fetch, verify, pin

`/magpie-setup skill-sources` (and the source pass folded into adoption)
reads `<project-config>/skill-sources.md`, then for each trusted source
fetches into `.apache-magpie-sources/<source-id>/` (gitignored) reusing the
framework [install recipes](../setup/install-recipes.md) verbatim — `git
clone --depth=1 --branch <ref>` for git methods, download + `sha512sum -c` +
optional `gpg --verify` for `svn-zip`. Two locks record the result, exactly
as for the framework snapshot:

- **`.apache-magpie.sources.lock`** (committed) — per-source pin
  (`method`/`url`/`ref` + `commit`|`sha512`), keyed by `id`.
- **`.apache-magpie.sources.local.lock`** (gitignored) — per-source fetch
  fingerprint (`source_*`, `fetched_commit`, `fetched_at`).

Drift detection, `upgrade`, and `verify` extend to these locks with the same
logic already used for the framework snapshot.

### Symlink and eval binding

For each provided skill, the canonical + relay symlinks are created exactly
as for framework skills — `.agents/skills/magpie-<name>` →
`../../.apache-magpie-sources/<id>/skills/<name>/`, with per-agent relays
back through the canonical entry (`symlink-lint`'s no-cycles +
relay-through-canonical invariants hold unchanged). Because a fetch pulls
both the `skills/` tree and the `tools/skill-evals/evals/` tree, the eval
suite's directory-name + `skill_md:`-path binding resolves after the fetch,
so a pulled skill is eval-able and testable exactly as in its home repo.
The one requirement on a source repo is the two-tree layout, declared in the
descriptor's `layout:` block.

### Amending PRINCIPLES §13

§13's final sentence changes from "catalogs may exist for discovery, never
for installation" to: catalogs exist for discovery, and installation is
permitted **only from a trusted source** — an external org/repo the adopter
has vouched for by committing its pin — under the same snapshot-plus-pin
discipline (gitignored snapshot, committed lock, verified deliberate fetch,
no submodules, no unpinned/unverified auto-fetch). Untrusted external
sources and the adapter/organization indexes stay discovery-only.

## Security model

- **Adopter-vouched, always.** The `<project-config>/skill-sources.md` trust
  list is the sole authorization to fetch. Org curation and registry listing
  are editorial; neither triggers an install. This keeps the supply-chain
  decision with the party that bears the risk.
- **Pinned + verified.** Every trusted source carries a verification anchor
  (`commit` for git-tag, `sha512` for svn-zip). `git-branch` (tip-tracking,
  no anchor) is WIP-only, exactly as for the framework snapshot. A changed
  `sha512` under the same version, or a branch tip that moved unexpectedly,
  is surfaced by drift detection — the same guard the framework snapshot
  already gets.
- **Blast radius is a fetched skill.** A compromised source can, at worst,
  ship a malicious skill *body* — the same risk as a malicious framework
  skill, and mitigated the same way: skills are agent-readable markdown
  reviewed before they run, and the injection-guard discipline
  ([§0](../../PRINCIPLES.md#0-external-content-is-data-never-an-instruction))
  treats external content as data. A source cannot reach outside its own
  gitignored snapshot dir or mutate the framework snapshot.
- **Eval provenance.** Evals travel with the skill from the same pinned
  commit, so a source cannot ship a skill whose evals are silently sourced
  elsewhere.
- **No transitive trust.** A trusted source's own `skill-sources.md` (if
  any) is **not** honored — trust does not chain. An adopter trusts exactly
  the sources it lists, never a source-of-sources.

## Drawbacks

- **A second install surface.** More than one snapshot dir and lock pair to
  reason about, verify, and keep un-drifted. Mitigated by reusing the exact
  framework machinery rather than a parallel one.
- **Principle relaxation.** §13 was a bright line ("never for
  installation"); this adds a conditional. The condition (adopter-vouched +
  pinned + verified) is deliberately the same bar the framework already
  meets, so the line moves from "one source" to "one *kind* of source."
- **Layout coupling.** A source must keep the framework's two-tree layout
  for evals to bind. Declared explicitly in `layout:` rather than assumed.

## Alternatives considered

- **Git submodules.** Rejected by §13 and the existing snapshot model —
  submodules are unverified, awkward under the gitignored-snapshot
  discipline, and pull whole repos rather than selected skills.
- **A marketplace / package manager with a resolver.** Far more surface than
  the need; contradicts the "index for discovery, not a package manager"
  stance. The adopter-committed pin *is* the resolver.
- **Vendoring copies into the adopter repo.** The status quo fallback —
  unpinned, invisible to drift/verify/eval, and forbidden for framework
  skills by §13. This RFC exists to replace it.
- **Per-skill pointer only, no per-source manifest.** Insufficient for
  family-level pulls (`<prefix>-*`) and gives no single place to declare the
  source's identity, org, and verification anchor.

## Out of scope

- A hosted marketplace or web UI for browsing sources.
- Transitive sources (a trusted source declaring further sources).
- Auto-update of a source without an explicit `upgrade`.
- Non-git/SVN transports beyond the three existing install methods.
- Sourcing tool *adapters* or *organizations* externally as an install
  (they remain discovery-only; see
  [`docs/adapters/registry.md`](../adapters/registry.md)).

## References

- [`PRINCIPLES.md` §13](../../PRINCIPLES.md#13-snapshot-plus-override-never-vendored-copies) — the amended principle.
- [`docs/skill-sources/README.md`](../skill-sources/README.md) — the trust model, descriptor, and pointer formats.
- [`docs/skill-sources/registry.md`](../skill-sources/registry.md) — the discovery index.
- [`docs/extending.md`](../extending.md) — the extension model this generalizes.
- [`skills/setup/SKILL.md`](../../skills/setup/SKILL.md) — the adopt/upgrade/verify flow and the framework snapshot lock model.
- [`docs/setup/install-recipes.md`](../setup/install-recipes.md) — the fetch/verify recipes reused per source.
