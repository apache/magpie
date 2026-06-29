<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Independent organization](#independent-organization)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Independent organization

The [organization](../README.md) for projects with **no formal
governing body** — informal maintainer collectives and single-vendor
teams. It is the baseline a project inherits when it sets:

```yaml
organization: independent
```

[`organization.md`](organization.md) defaults to the fully
GitHub-native, no-foundation path: DCO sign-off, GitHub Security
Advisories intake, MITRE-form CVE allocation, GitHub Releases for
distribution, and no mailing-list / forwarder / project-metadata
backends.

The worked profile [`projects/non-asf-example/`](../../projects/non-asf-example/)
(Velox Stream) inherits from this adapter and demonstrates that a
non-ASF project runs the whole skill catalogue with config only — no
skill edits. Override any key in `project.md` to suit your project.
