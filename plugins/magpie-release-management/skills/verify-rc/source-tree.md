<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Step 7 — Source-tree integrity (dangling symlinks + broken references)

A signed, checksummed, licence-clean archive can still be broken:
a symlink whose target `export-ignore` stripped, a symlink pointing out of the archive,
or a shipped file linking to a path the release no longer contains.
Catch that **in the unpacked archive**, before the `[VOTE]`, with `commands.symlinks`
(each command of `release-build.md § Source-tree validators`, the adopter's own, is a `--validator`; the framework assumes none).

A symlink in `dangling_symlinks` (target missing) or `outside_symlinks` (an absolute path, `..` past the root, or a chain through either, even to an existing target) is a final `FAIL`.
`PASS` means no validators are declared; `SKIP` (no symlinks, no validators) is stated explicitly.
On `REVIEW`, run each validator in `paste_recipe` from `<unpacked-dir>` (or, when it is not shippable, from a checkout of the *same tag* against the unpacked dir, and say so),
then resolve it, one `--validator-result` per validator in `validators_to_run` order:

```bash
<verify-rc> source-tree --symlinks <symlinks.json> --validator-result <exit-code>[:<broken link / missing target>] …
```

A non-zero exit is one `validator_failures` entry and `FAIL`s the step; all zero is `PASS`.

Return ONLY its JSON (`step`: `source-tree-integrity`, `status`, `dangling_symlinks`, `outside_symlinks`, `validator_failures` of `{validator, detail}`, `paste_recipe`).
