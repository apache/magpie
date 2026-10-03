<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# security-issue-import-from-pr — tracker body template

The Step 7a body file, written per PR with every `<…>` placeholder filled.

```bash
cat > <scratch>/import-pr-<N>-body.md <<'EOF'
### The issue description

> **Imported from public PR <upstream>#<N>** — there is no inbound `security@` report; the PR description below is the public statement of the vulnerability.

<verbatim PR body>

### Short public summary for publish

_No response_

### Affected versions

<per-scope shape>

### Security mailing list thread

N/A — opened from public PR <pr.url>; no security@ thread

### Public advisory URL

_No response_

### Reporter credited as

<proposed reporter>

### PR with the fix

<pr.url>

### Remediation developer

<proposed remediation developer>

### CWE

_No response_

### Severity

<proposed severity>

### CVE tool link

_No response_
EOF
```
