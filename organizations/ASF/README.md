<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [ASF organization](#asf-organization)
  - [Using it](#using-it)
  - [What is *not* here](#what-is-not-here)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# ASF organization

The reference [organization](../README.md) for the **Apache
Software Foundation**. [`organization.md`](organization.md) holds the
ASF defaults every Apache project inherits: PMC governance vocabulary,
the Vulnogram CVE authority, the PonyMail archive, the
`apache-projects-mcp` metadata backend, the ASF-security forwarder, and
the `*.apache.org` / `cveprocess.apache.org` / `dist.apache.org`
infrastructure values.

## Using it

In `<project-config>/project.md`:

```yaml
organization: ASF
```

The project then inherits every key in [`organization.md`](organization.md)
and need only declare its **own** per-project values (security-list
address, scope labels, product name, roster handles, tracker labels).

## What is *not* here

Per-project values are not org-level and stay in `project.md`:
the concrete `<security-list>` address, the scope-label → product map,
the product name / package name, the security-team roster, and the
tracker's body-field / label vocabulary.

ASF-specific *process* skills (the `release-management` and
`contributor-growth` families, marked `organization: ASF`) assume this
adapter by default.
