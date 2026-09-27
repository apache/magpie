<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# security-issue-invalidate — examples

## Examples

### Example 1 — `security@`-imported, dag-author-input class

```text
invalidate 244
```

Tracker `<tracker>#244` (*DAG author RCE on webserver via
unrestricted import_string() in BaseSerialization.deserialize()*),
import path: `security@`-imported. Step 3 mines five comments
arguing the dag author is already trusted (with quotes from
two security-team members). Canned: *When someone claims Dag
author-provided "user input" is dangerous*. Email draft created
on thread `<threadId>` with the canned spine + augmentation
quoting the team's specific reasoning. Tracker closed as
`not planned`, `invalid` label applied, scope label removed,
project board item archived. Rollup entry posted with five
verbatim quotes and the draft ID. Hand-off: terminal.

### Example 2 — PR-imported, no email

```text
invalidate 355
```

Tracker `#355` (the public-PR-imported tracker from the test of
`security-issue-import-from-pr` against PR 65703). Suppose the
team later decides the report is not CVE-worthy on its own
merits. Step 2 detects the `N/A — opened from public PR` sentinel;
the email-draft step is skipped. Closing comment notes *"no
reporter notification (PR-imported tracker)"*. Rollup entry
records the `silent` notification path with a link to the
*Reporter credit policy* explaining why. Tracker closed,
archived. PR `<upstream>#65703` is **not** commented on —
the public PR stays unaware of the CVE process per the
import-from-pr skill's golden rules.

### Example 3 — Hard stop: CVE already allocated

```text
invalidate 257
```

Step 0 sees `cve allocated` label and *CVE tool link* populated
with `<cve-tool-url>`. The
skill stops:

> Tracker `#257` has CVE `CVE-2026-XXXXX` allocated.
> Closing as invalid here would orphan a public CVE record.
> Reject the CVE in Vulnogram first
> (<cve-tool-url>), then
> re-invoke `invalidate 257`.

No labels touched, no comments posted, no archive performed.
