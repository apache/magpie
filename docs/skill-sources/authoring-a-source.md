<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Authoring a trusted skill source](#authoring-a-trusted-skill-source)
  - [Step 1 — Lay out the repo in the two-tree shape](#step-1--lay-out-the-repo-in-the-two-tree-shape)
  - [Step 2 — Author each skill in the Magpie shape](#step-2--author-each-skill-in-the-magpie-shape)
  - [Step 3 — Keep the eval binding resolvable](#step-3--keep-the-eval-binding-resolvable)
  - [Step 4 — Pick your organization identity](#step-4--pick-your-organization-identity)
  - [Step 5 — Choose a distribution method + verification anchor](#step-5--choose-a-distribution-method--verification-anchor)
  - [Step 6 — Write your source descriptor](#step-6--write-your-source-descriptor)
  - [Step 7 — Get listed for discovery (optional, recommended)](#step-7--get-listed-for-discovery-optional-recommended)
  - [Step 8 — Validate before you publish](#step-8--validate-before-you-publish)
  - [Step 9 — Tell adopters how to pull it](#step-9--tell-adopters-how-to-pull-it)
  - [Step 10 — Maintain the source](#step-10--maintain-the-source)
  - [See also](#see-also)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Authoring a trusted skill source

A step-by-step guide for a **third-party repository or organization** that
wants Apache Magpie adopters to be able to pull *its* skills. It is the
source-repo counterpart of [`README.md`](README.md), which describes the
same feature from the *adopter's* side.

**Mental model.** Your repo becomes a **trusted skill source**. Adopters do
not copy your files. They add your [source
descriptor](README.md#source-descriptor) to their trust list, commit a
**pin** (method + URL + ref + a verification anchor), and run
`/magpie-setup skill-sources`
([`skills/setup/skill-sources.md`](../../skills/setup/skill-sources.md)),
which fetches a **verified, gitignored snapshot** of your repo and symlinks
your skills in so they run exactly like in-tree Magpie skills. Your job is
to lay the repo out the way Magpie expects and to publish a descriptor plus
a verifiable release. Per
[`PRINCIPLES.md` §13](../../PRINCIPLES.md#13-snapshot-plus-override-never-vendored-copies)
nothing installs until an adopter vouches for you — being listed is
discovery, never installation.

## Step 1 — Lay out the repo in the two-tree shape

Magpie binds a skill to its eval suite by path, so keep the two roots it
uses itself:

```text
skills/<skill-name>/SKILL.md            # the skill body (+ any helper files)
tools/skill-evals/evals/<skill-name>/   # that skill's eval suite
tools/<tool>/tests/                     # unit tests, if a skill ships a tool
```

These are the defaults. If you must use different roots, declare them in the
descriptor's `layout:` block (Step 5) — but keeping the defaults is the
low-friction path.

## Step 2 — Author each skill in the Magpie shape

Every `SKILL.md` must carry these **required** frontmatter keys — the
[skill validator](../../tools/skill-and-tool-validator/) enforces them:

```yaml
---
name: <skill-name>
description: <what it does / when to invoke it>
license: Apache-2.0        # only Apache-2.0 is accepted
capability: capability:<triage | resolve | …>
---
```

Optional keys: `when_to_use`, `mode`, `status` (and `organization` /
`source`, which the framework fills in). Follow the framework authoring
conventions in [`docs/extending.md`](../extending.md) and
[`AGENTS.md`](../../AGENTS.md) — injection guards, the placeholder
convention, no ASF-only coupling. **Skill directory names must be globally
unique:** each becomes a `magpie-<name>` symlink in the adopter, so it must
not collide with a framework skill or another source's skill.

## Step 3 — Keep the eval binding resolvable

Each eval step's `fixtures/step-config.json` uses a repo-relative
`skill_md:` path. As long as `skills/` and `tools/skill-evals/evals/` stay
sibling trees, the binding resolves after a fetch — the fetch pulls **both**
trees plus any tool `tests/` a skill depends on. See the
[layout contract](README.md#layout-contract--skills-evals-tests).

## Step 4 — Pick your organization identity

The descriptor's `organization:` must name a directory under
`organizations/` **in `apache/magpie`**. Two paths:

- **`organization: independent`** — the catch-all. Works out of the box,
  no change to Magpie.
- **Register your org** — open a PR to `apache/magpie` adding
  `organizations/<your-org>/organization.md` (mirror
  [`organizations/_template/`](../../organizations/_template/organization.md)),
  optionally with a `skill-sources.md` that curates your sources. Choose
  this if you want org-level branding and to vouch for your own sources at
  the org layer. See [`organizations/README.md`](../../organizations/README.md).

## Step 5 — Choose a distribution method + verification anchor

| Method | What adopters pin | Use when |
|---|---|---|
| **`git-tag`** *(recommended)* | `ref: <tag>` + `commit: <SHA>` | Normal releases. Cut an **immutable** tag — never move a published tag; a moved tag fails the adopter's re-fetch guard as a supply-chain signal. |
| **`svn-zip`** | `ref: <version>` + `sha512: <hash>` | You publish a released archive (optionally GPG-signed against a `KEYS` file). |
| **`git-branch`** | `ref: <branch>` (no anchor) | WIP / preview only — no frozen anchor, tip-tracking. |

The fetch reuses the framework
[install recipes](../setup/install-recipes.md) verbatim, so these are the
same three methods and anchors the framework snapshot uses for itself.

## Step 6 — Write your source descriptor

This is the block an adopter (or your org's `skill-sources.md`) carries.
Required keys: `id`, `organization`, `name`, `method`, `url`, `ref`,
`provides`.

```yaml
- id: acme-security-skills          # unique, kebab-case — the handle pointers reference
  organization: independent         # or your registered org
  name: "Acme Security Skills"
  maintainer: "Acme Sec Team / @acme-handle"
  method: git-tag
  url: https://github.com/acme/magpie-skills
  ref: v1.0.0
  commit: <SHA the tag resolves to>   # git-tag anchor (or sha512: <hash> for svn-zip)
  layout:                            # omit when you use the defaults
    skills_root: skills
    evals_root: tools/skill-evals/evals
  provides:
    - skill: acme-secret-scan        # one skill…
    - family: acme-audit-*           # …or a whole prefix-family
```

Full field reference: [`README.md` §
Source descriptor](README.md#source-descriptor).

## Step 7 — Get listed for discovery (optional, recommended)

Open a PR to `apache/magpie` adding:

- a row to [`registry.md`](registry.md) — the discovery index; and/or
- your descriptor to `organizations/<your-org>/skill-sources.md` — org
  curation.

**Listing is discovery only — it never triggers an install.** The adopter's
`<project-config>/skill-sources.md` trust list is always the gate.

## Step 8 — Validate before you publish

Run Magpie's own validator against your repo so your skills and descriptor
pass the same checks an adopter's CI runs:

```bash
git clone --depth=1 https://github.com/apache/magpie /tmp/magpie
# from your source repo root:
uv run --project /tmp/magpie/tools/skill-and-tool-validator skill-and-tool-validate
```

It checks `SKILL.md` frontmatter / naming / injection guards, descriptor
shape (required keys, a supported `method`, a known `organization`), and
flags any skill directory missing an eval suite.

## Step 9 — Tell adopters how to pull it

An adopter adds your descriptor to `<project-config>/skill-sources.md` — by
`id` alone if your org curates it, or in full otherwise — commits the pin,
and runs:

```text
/magpie-setup skill-sources
```

That fetches + verifies your source into `.apache-magpie-sources/<id>/` and
symlinks the skills you `provide`. The adopter side is documented in
[`README.md` § How a trusted skill is
installed](README.md#how-a-trusted-skill-is-installed).

## Step 10 — Maintain the source

- **New release** → cut a **new** tag and publish its `commit` (or the new
  `sha512`). Adopters bump their pin deliberately; the bump shows up in
  their PR diff, exactly like a framework-lock bump.
- **Keep the two-tree layout stable** so eval bindings keep resolving after
  a fetch.
- **Additions to `provides`** reach adopters on their next
  `/magpie-setup upgrade`, which re-fetches per the committed pin and
  refreshes the symlinks.

## See also

- [`README.md`](README.md) — the feature from the adopter's side (formats, trust model, security model).
- [`registry.md`](registry.md) — the discovery index of known sources.
- [`RFC-AI-0006`](../rfcs/RFC-AI-0006.md) — the design, trust, and threat model.
- [`skills/setup/skill-sources.md`](../../skills/setup/skill-sources.md) — the `/magpie-setup skill-sources` fetch/pin/symlink flow.
- [`docs/extending.md`](../extending.md) — the full extension model (what / where / who).
