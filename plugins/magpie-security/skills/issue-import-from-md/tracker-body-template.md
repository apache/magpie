<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# security-issue-import-from-md — tracker body template

The Step 5a body file, written per finding with every `<…>` placeholder filled.

```bash
cat > <scratch>/import-md-<basename>-<index>-body.md <<'EOF'
### The issue description

> **Imported from markdown file `<basename>` (finding <K>/<N>)** — there is no inbound `<security-list>` report; the markdown sections below are the verbatim source.

**Details:**

<## Details payload, verbatim>

**Impact:**

<## Impact payload, verbatim>

**Reproduction steps:**

<## Reproduction steps payload, verbatim>

### Short public summary for publish

_No response_

### Affected versions

`<owner>/<repo>` @ `<branch>` — versions to be confirmed during triage.

### Security mailing list thread

N/A — imported from markdown file `<basename>`; no <security-list> thread.

### Public advisory URL

_No response_

### Reporter credited as

_No response_

### PR with the fix

<location_url if it points at a <upstream> PR, else _No response_>

### Remediation developer

_No response_

### CWE

<category from metadata; free-text — actual CWE assigned at triage>

### Severity

<severity from metadata>

### CVE tool link

_No response_

<details><summary>Recommended fix (per the source markdown)</summary>

<## Recommended fix payload, verbatim>
</details>
EOF
```
