<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [TODO: `<Organization Name>` — curated skill sources](#todo-organization-name--curated-skill-sources)
  - [Curated sources](#curated-sources)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# TODO: `<Organization Name>` — curated skill sources

The external [skill sources](../../docs/skill-sources/README.md) this
organization **vouches for**. A project that sets `organization: <org>`
sees these as candidate sources it *may* adopt — curation is **not**
installation. The project still opts each one in by committing its pin to
[`<project-config>/skill-sources.md`](../../projects/_template/skill-sources.md).

Leave the list empty if the organization curates none; projects can still
trust a source directly in their own `skill-sources.md`.

## Curated sources

Each entry is a [source descriptor](../../docs/skill-sources/README.md#source-descriptor).
Declare only sources this organization stands behind for every project
under it.

```yaml
# - id: <source-id>                 # unique, kebab-case
#   organization: <org>            # must match this directory's name
#   name: "<human-readable name>"
#   maintainer: "<who>"
#   method: <git-tag | git-branch | svn-zip>
#   url: <repo or archive URL>
#   ref: <tag | branch | version>
#   # verification anchor: commit (git-tag) | sha512 (svn-zip)
#   layout:
#     skills_root: skills
#     evals_root: tools/skill-evals/evals
#   provides:
#     - skill: <name>
#     - family: <prefix>-*
```

Also add a row to the *Org-curated sources* table in
[`docs/skill-sources/registry.md`](../../docs/skill-sources/registry.md)
so the source is discoverable.
