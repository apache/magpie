<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# security-issue-import-from-pr — the mixed-scope blocker

`security-management issue-import-from-pr scope` printed `stop: true` and `scope: mixed_scope_blocker`:
the production files (tests stripped) match more than one *scope's* `path_prefix` (one file under `^<scope-b>/` and one under `^<scope-a>/`).
**Stop**, create nothing, and surface the blocker with `<N>` and the labels from `mixed_scopes` filled in:

> PR <N> changes files across more than one scope (`<scope-A>`,
> `<scope-B>`). One tracker maps to one CVE container. Either
> split the report into per-scope trackers manually, or
> re-confirm with the team which scope the CVE should be
> allocated against, and re-invoke with that decision noted.

This is the per-scope split rule in [`scope-labels.md`](../../../../../<project-config>/scope-labels.md).
Several sub-packages of the *same* scope are not mixed: `scope` names the one scope and `sub_packages` lists each.

## The scope mapping

The scope labels and their `path_prefix` regexes come from `scope_detection.labels` in
[`<project-config>/project.md`](../../../../../<project-config>/project.md#scope-detection);
the label whose regex matches `pr.files[].path` becomes the tracker's scope.

An illustrative mapping, with placeholder scope labels:

| `path_prefix` match | Scope | Notes |
|---|---|---|
| `^<scope-b>/` (with `<name>` segment, e.g. `<scope-b>/<name>/`) | `<scope-b>` | Capture `<name>` — used for the `packageName` substitution in `scope_detection.labels.<scope-b>.packageName` and the *Affected versions* field. |
| `^<scope-c>/` | `<scope-c>` | Single-component changes. |
| `^<scope-a>/` (or whatever the project's `<scope-a>`-equivalent label declares) | `<scope-a>` | Core / shared. |

The tool captures `<name>` as the regex's first group when it has one,
else as the path segment right after the match when `packageName` holds a `<…>` substitution;
`packages` is `packageName` with each captured name substituted.

When `scope_detection.enabled` is `false`, every PR maps to the
single product declared in the `product` block of `project.md` —
skip the matching step and apply the default scope label (if any).
The tool then prints that `default_label` as `scope`.
