<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Name→handle map:
  "Alice Smith" → @alice
  "Bob Chen"    → @bob

## Comment body to scrub

**Triage proposal**

The `PostgresOperator` passes a DAG-author-controlled variable directly into
the `sql=` parameter without sanitisation. DAG authors already have
trusted code-execution capability on the worker; this is the documented
boundary per the Security Model.

**Proposed disposition: NOT-CVE-WORTHY.**

Severity: N/A — outside Security Model scope. No CVE warranted.

Canned response: "When someone claims Dag author-provided 'user input' is
dangerous" covers this shape exactly.

@bob — does the canned response need any inline augmentation for the
PostgresOperator-specific framing, or is the standard template sufficient?
