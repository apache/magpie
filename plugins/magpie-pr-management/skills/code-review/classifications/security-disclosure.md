<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Possible undisclosed security fix

[`code-review`](../../../../../tools/pr-management/README.md#code-review--pr-management-code-review) `context` matched security-nature language (`security_disclosure.matches`: location, matched text, context) in the title, body or commit messages.
ASF policy (`https://www.apache.org/security/committers.html`) requires that no reference to the security nature of a commit appear in public-facing content until the vulnerability is formally announced:

> *"Messages associated with any commits should not make any reference to the security nature of the commit."*

Surface the pre-review warning before Step 4 and wait for an explicit acknowledgment:

> ⚠ **Possible undisclosed security fix detected**
>
> The PR title / body / commit messages contain language that may indicate a security vulnerability fix:
>
> - [each match: its location and the quoted context]
>
> ASF policy requires that no reference to the security nature of a commit appear in public-facing content until the CVE is formally announced. See `https://www.apache.org/security/committers.html`.
>
> **Before merging:** verify that the CVE disclosure process for this fix is complete (CVE status `READY`, public announcement sent to the standard destinations). If disclosure is not yet complete, this PR should be closed and the fix applied through the private security channel instead.
>
> *Acknowledge and continue review? `[Y]es` / `[Q]uit`.*

Include the warning as the leading note of the review body whatever the disposition (`render --security-note <file>`): the contributor needs to see it even on `APPROVE`.
