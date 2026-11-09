<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# `path-denied` — a consequential file

A changed file matches `deny_globs`: a migration, a dependency manifest, CI configuration, core runtime or security code.
**Deny wins at any size and over any allow match** — a one-line change to the scheduler is not trivial; a forty-line docs change is. The `drop_reasons` entry names the file and the glob.
Reported with its number, for `pr-management-code-review` ([`actions/hand-off.md`](../actions/hand-off.md)).
