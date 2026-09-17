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
[`<project-config>/skill-sources.md`](../../projects/_template/skill-sources.md).

## Curated sources

Each entry is a [source descriptor](../../docs/skill-sources/README.md#source-descriptor).
To add another, declare it here and add a row to the *Org-curated sources*
table in [`docs/skill-sources/registry.md`](../../docs/skill-sources/registry.md).

### Apache Incubator

Skills the Incubator PMC maintains in
[`apache/incubator`](https://github.com/apache/incubator) for podlings,
mentors and the IPMC. The first is `releasecheck`, which checks a podling
release candidate before or during its vote. The same repo is also a plugin
marketplace, so the skills install without Magpie too:
`claude plugin marketplace add apache/incubator`.

The source is pinned to a tag, because the rest of the Incubator repo
changes often. A new skill version gets a new `releasecheck-<version>` tag,
and this pin moves only when the tag is updated here.

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
