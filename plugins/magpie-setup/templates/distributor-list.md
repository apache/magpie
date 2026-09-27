<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Embargo distributor list](#embargo-distributor-list)
  - [The list](#the-list)
  - [What a pre-announcement may contain](#what-a-pre-announcement-may-contain)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Embargo distributor list

Where a pre-announcement goes when the project notifies downstream
distributors ahead of public disclosure. Read by `security-issue-sync` when a
tracker is marked `distributor_notify_pending` and the fix is about to ship.

**This file is optional, and most projects will not need it.** Create it only
if your project actually operates an embargo distributor list. When it is
absent, `security-issue-sync` says so and does not propose a
pre-announcement — it will not guess a recipient for an embargoed report.

Fill in the `TODO` fields. Keep this file in the *adopter's* config directory,
not in a public repository, if the list membership is itself confidential.

---

## The list

- **Address:** TODO — the list address a pre-announcement is sent to.
- **Where membership is documented:** TODO — the URL or internal page that
  records who is on the list and how they joined.
- **Who may send to it:** TODO — typically the security team only.

## What a pre-announcement may contain

TODO — the project's own rule. The framework's default, which
`security-issue-sync` follows unless this says otherwise: the CVE ID, the
affected product and versions, and the expected disclosure date. Nothing
beyond the advisory's short public summary, and no patch, no reproducer, and
no reporter identity.
