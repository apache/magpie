<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [TODO: `<Project Name>` — trusted skill sources](#todo-project-name--trusted-skill-sources)
  - [Trusted sources](#trusted-sources)
  - [Selecting what to pull](#selecting-what-to-pull)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# TODO: `<Project Name>` — trusted skill sources

**This file is the install gate.** It lists the external
[skill sources](../../docs/skill-sources/README.md) this project trusts and
pins. Per [`PRINCIPLES.md` §13](../../PRINCIPLES.md#13-snapshot-plus-override-never-vendored-copies),
`/magpie-setup` fetches a source **only if it is listed here** — an
organization curating a source, or the registry listing one, never triggers
an install on its own. Committing this file is the adopter's explicit act of
vouching for each source.

Leave the list empty (the default) to run only in-tree framework skills.

## Trusted sources

Each entry is a [source descriptor](../../docs/skill-sources/README.md#source-descriptor).
You may **reference** a source your organization curated in
`organizations/<org>/skill-sources.md` by `id` alone (the descriptor is
inherited), or declare a full descriptor here for a source your org does
not curate. Either way the pin — `method` + `url` + `ref` + the per-method
verification anchor — must be committed.

```yaml
# Reference an org-curated source by id (descriptor inherited from
# organizations/<org>/skill-sources.md), still pinning the ref you trust:
# - id: <org-curated-source-id>
#   ref: <tag | version>
#   commit: <SHA>        # git-tag anchor  (or sha512: <hash> for svn-zip)

# ...or trust a source your organization does not curate, in full:
# - id: <source-id>
#   organization: <org>            # must name a directory under organizations/
#   name: "<human-readable name>"
#   maintainer: "<who>"
#   method: <git-tag | git-branch | svn-zip>
#   url: <repo or archive URL>
#   ref: <tag | branch | version>
#   commit: <SHA>                  # git-tag; or  sha512: <hash>  for svn-zip
#   layout:
#     skills_root: skills
#     evals_root: tools/skill-evals/evals
#   provides:
#     - skill: <name>
#     - family: <prefix>-*
```

`git-branch` (branch-tip tracking, no cryptographic anchor) is WIP-only —
prefer `git-tag` or `svn-zip` for anything you depend on, exactly as for the
framework snapshot pin in [`.apache-magpie.lock`](../../skills/setup/SKILL.md).

## Selecting what to pull

Running `/magpie-setup skill-sources` (or the source pass folded into
`/magpie-setup` adoption) reads this file, fetches + verifies each trusted
source into the gitignored `.apache-magpie-sources/<id>/`, writes the
committed [`.apache-magpie.sources.lock`](../../docs/skill-sources/README.md#how-a-trusted-skill-is-installed)
pin, and symlinks in the `provides` skills exactly like framework-family
skills. From then on each pulled skill behaves like an in-tree one — same
`magpie-` relay, same override layer under `.apache-magpie-overrides/`, same
eval binding.
