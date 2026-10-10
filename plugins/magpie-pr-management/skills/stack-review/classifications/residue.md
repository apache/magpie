<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# `residue` — minor, *noticed, not exhaustive*

Collect the tokens the stack retires from the bodies and commit messages (a version string, a removed option, a deleted module, a renamed flag) and every spelling each takes — prose (`<Lang> X.Y`), interpreter or tool (`<tool>X.Y`), image tag (`<image>:X.Y`), identifier (`<lang>XY`), file name (`<name>-X.Y`).
A bare `X.Y` matches package versions: never use it alone.

Build the grep with the tool — it quotes every value and excludes generated output, locks, manifests and release notes, where the same digits mean something else:

```bash
uv run --project <framework>/tools/pr-management pr-management stack-review residue-command \
  --clone <clone> --prefix magpie-stack/<S> --size <size> --variant '<regex>' [--variant …] [--exclude-glob '<project glob>']
```

Report hits in files no layer touches (`ledger.json → touched_files` is the complement) as *residue* and hits in a touched file as *partial update*, both `minor`, prefixed *noticed, not exhaustive* — the token list is a guess, not a census.
Drop hits that are dependency versions, release numbers, deliberately kept historical lists or test fixtures, and say how many were dropped.
Skipped under `no-fetch`.
