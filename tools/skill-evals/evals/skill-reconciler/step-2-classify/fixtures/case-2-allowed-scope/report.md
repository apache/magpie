<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Comparing skills/security-cve-allocate/SKILL.md (ASF variant)
         vs non-asf-adopter/security-cve-allocate/SKILL.md (generic variant)

== Frontmatter ==
description:
  ASF variant:     "Walks an ASF PMC member or security team through allocating
                    a CVE identifier via the ASF CVE tool at cveprocess.apache.org,
                    normalises the title, and hands off to security-issue-sync."
  Generic variant: "Walks a project security team through allocating a vulnerability
                    identifier via the project's CNA allocation tool, normalises the
                    title, and hands off to security-issue-sync."

All other frontmatter fields (capability, license) are identical.

== Section headings ==
Identical section sets in the same order.

== Step content ==
Step 1 (open allocation form):
  ASF variant:     "Open https://cveprocess.apache.org/cve5/ in a browser. Log in
                    with your ASF LDAP credentials."
  Generic variant: "Open <cve-tool-url> in a browser. Log in with your project's
                    CNA account."

Step 3 (submit CNA record):
  ASF variant:     "Submit the record. The ASF PMC contact listed in
                    <project-config>/project.md is cc'd automatically."
  Generic variant: "Submit the record. The CNA contact at <cna-contact> is
                    cc'd per the project configuration."

Step 4 teaching note:
  ASF variant:     "PMC members may allocate CVEs directly; committers must request
                    allocation from a PMC member."
  Generic variant: "Allocation eligibility depends on the project's CNA agreement;
                    see <project-config>/project.md for the declared model."

== Hard rules block ==
Identical between both copies (5 bullets, same wording).

== Safety-baseline mentions ==
Both copies carry identical injection-guard callout paragraphs.
Both copies carry the same collaborator-trust gate wording.
Both copies carry identical confidentiality-posture statements.
