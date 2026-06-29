<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Organization-adapter template](#organization-adapter-template)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Organization-adapter template

Authoring skeleton for a new [organization](../README.md).

1. Copy this directory: `cp -R organizations/_template organizations/<org>`.
2. Fill in [`organization.md`](organization.md) — governance vocabulary
   plus the capability→backend bundle your organization standardizes.
   Omit anything that varies per project; omit anything that matches the
   framework default.
3. Point a project at it: set `organization: <org>` in the project's
   `<project-config>/project.md`.
4. Optionally **contribute it upstream** to `apache/magpie` under
   Apache-2.0 so every project in your organization reuses it, or keep it
   local. See
   [`docs/vendor-neutrality.md` § Authoring your own adapter](../../docs/vendor-neutrality.md#authoring-your-own-adapter).

Start from [`organizations/independent/`](../independent/) (the generic
baseline) and change only what your organization mandates;
[`organizations/ASF/`](../ASF/) is a fully worked example.
