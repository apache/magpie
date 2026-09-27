<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Security screening

Companion to [`SKILL.md`](SKILL.md). The security-signal screen applied
before proposing any stale comment (Golden rule 6).

Before proposing a stale comment on any issue, check the issue body for
signals that the report may describe a security vulnerability (RCE, auth
bypass, privilege escalation, CVE / CVSS references, injection,
coordinated-disclosure language). If any signal is found, **skip that
issue entirely** and surface a warning to the user: the issue should be
routed privately to `security@<project>.apache.org` rather than managed
via a public stale comment.
