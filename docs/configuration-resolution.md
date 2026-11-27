<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Configuration resolution](#configuration-resolution)
  - [`user.md` resolution order](#usermd-resolution-order)
  - [Configuration resolution order](#configuration-resolution-order)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Configuration resolution

Where a skill finds `user.md`, and the order in which configuration keys and per-skill overrides resolve. The repository-wide [`AGENTS.md`](../AGENTS.md) points here before a task that resolves or changes configuration.

## `user.md` resolution order

The file can live in one of three locations. Skills resolve in this
order, **first match wins** — do **not** merge across locations:

| # | Location | When to use |
|---|---|---|
| 1 | Path in `$APACHE_MAGPIE_USER_CONFIG` (env var) | Power-user / CI / isolated test setups that need a specific config. Wins over both defaults below. |
| 2 | `~/.config/apache-magpie/user.md` | **Recommended default.** One per-user, OS-conventional file shared across every worktree of every adopter project on the machine. |
| 3 | `<project-config>/user.md` | Per-project fallback for adopters who set up `user.md` inside their tracker repo before `~/.config/apache-magpie/` existed. Future adopters should prefer (2). |

When this document or a skill says *"`user.md`"* unqualified, it means
*the resolved file* per the order above; the legacy phrasing
*"`<project-config>/user.md`"* is location (3), read as "… or whichever
location wins". The cross-worktree story falls out of (2): every
worktree resolves to the same file, so per-user fields (apache_id,
GitHub handle, governance membership, local clone path) stay coherent without
symlinks or per-worktree bootstrap. The framework does not manage the
file — adopters create / edit it directly; see
[`setup/install.md`](../plugins/magpie-setup/skills/setup/install.md).

When this document (or any skill) says *"the tracker repo"*, *"the
security list"*, *"the canned responses"*, it means the value declared
in `<project-config>/project.md` and its siblings. *"The user's GitHub
handle"*, *"governance membership"*, *"the local upstream clone"* mean the value in
the resolved `user.md`. Truly project-agnostic facts (a lifecycle rule,
a confidentiality principle, a brevity rule) live in this file or in
[`README.md`](../README.md).

## Configuration resolution order

A project may belong to an **organization** (a foundation, company, or
maintainer collective) that supplies shared defaults via an
[organization](../organizations/README.md). `project.md` names it
once:

```yaml
organization: ASF      # default: independent
```

Every placeholder and dotted config key then resolves in this order,
**first hit wins**:

```text
<project-config>/project.md
  →  organizations/<org>/organization.md            (in-tree org)
  →  <project-config>/.apache-magpie-overrides/organizations/<org>/organization.md   (adopter-local / external org)
    →  framework default
```

The chain above resolves placeholders and dotted config keys from the
shared project configuration. It is distinct from the per-skill override
chain used when an adopter tailors a framework workflow:

```text
<personal-layer>/<skill>.md          <git-common-dir>/apache-magpie/ (installed only)
                                     or .apache-magpie-local/ (adopted)
  →  <main-checkout>/.apache-magpie-local/<skill>.md   (adopted, linked worktree only)
  →  .apache-magpie-local/<skill>.md                   (unadopted, legacy in-tree only)
    →  .apache-magpie-overrides/<skill>.md
      →  framework default
```

There is no organization layer in the per-skill chain: an organization
supplies config-key defaults to the chain above, not skill overrides.

The personal layer is never committed — inside the git directory, or
gitignored — and takes precedence over the committed `.apache-magpie-overrides/` layer when both
provide the same setting. Both override surfaces are additive only: they
may provide adopter-specific paths, wording, or capability/MCP enablement,
but they cannot weaken the safety, confidentiality, privacy, or
external-content-as-data baseline. See
[`docs/setup/agentic-overrides.md`](setup/agentic-overrides.md) for
the per-skill contract. The per-skill chain does not replace the
`<project-config>/project.md` key-resolution chain above; a skill resolves
configuration keys through that chain and then applies matching overrides.

The organization an `organization:` value names need **not** be in-tree.
The framework ships `organizations/ASF/` and `organizations/independent/`,
but an organization Magpie does not ship is resolved from an
adopter-local copy under `.apache-magpie-overrides/organizations/<org>/`
— maintained in the adopter's repo or vendored from the organization's
own repo (discovery, never auto-fetch, per
[`PRINCIPLES.md` §14](../PRINCIPLES.md#14-one-easy-install-that-upgrades-and-reconciles-never-vendored-copies)).
See [`docs/extending.md`](extending.md) for the full extension model.

A project declares only what differs from its organization; an
organization declares only what differs from the framework baseline
(`organizations/independent/` is that baseline). This is the only
inheritance in the config model — skills never branch on the
organization; they read a key and take the first value the chain
yields. When this document says a value comes from
`<project-config>/project.md`, read it as "from `project.md`, else the
project's organization, else the framework default".

A project may also **pull skills from a trusted external source**. The
committed `<project-config>/skill-sources.md` file is the install gate: it
lists the source ids the adopter trusts and commits each pin (method + URL
+ ref + verification anchor). Where a skill directory would sit, a
`skills/<name>/source.md` redirect (frontmatter `source:` / `organization:`
/ `skill_path:` / `evals_path:`, **not** a `SKILL.md`) names the source;
`/magpie-setup` fetches it into the gitignored snapshot and wires it in like
a framework skill. Per [`PRINCIPLES.md` §14](../PRINCIPLES.md#14-one-easy-install-that-upgrades-and-reconciles-never-vendored-copies)
this is the one external home that *installs* rather than being merely
referenced — pinned, verified, and adopter-vouched. See
[`docs/skill-sources/`](skill-sources/README.md).
