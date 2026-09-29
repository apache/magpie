<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# License normalization

Companion to [`SKILL.md`](SKILL.md). The raw-string → SPDX normalisation table and the normalisation rules applied before classification.

## License normalization

Ecosystem tools report license names as free text, legacy labels, or
classifier strings. Normalise each to a canonical SPDX identifier from the
SPDX License List (<https://spdx.org/licenses/>) **before** classifying. Maven
`<name>` fields and Python trove classifiers are the least consistent, so
expect to normalise those most.

Common raw strings and their SPDX identifiers:

| Raw string(s) | SPDX identifier |
|---|---|
| `MIT`, `MIT License`, `Expat` | `MIT` |
| `Apache 2`, `Apache License 2.0`, `ASL 2.0`, `The Apache Software License, Version 2.0` | `Apache-2.0` |
| `New BSD`, `BSD 3-Clause`, `BSD-3` | `BSD-3-Clause` |
| `Simplified BSD`, `BSD 2-Clause`, `FreeBSD` | `BSD-2-Clause` |
| `ISC License (ISCL)` | `ISC` |
| `MPL 2.0`, `Mozilla Public License 2.0 (MPL 2.0)` | `MPL-2.0` |
| `EPL 2.0`, `Eclipse Public License - v 2.0` | `EPL-2.0` |
| `CDDL 1.1`, `Common Development and Distribution License` | `CDDL-1.1` |
| `PSF`, `Python Software Foundation License` | `PSF-2.0` |
| `GPLv3`, `GNU General Public License v3` | `GPL-3.0-only` |
| `LGPLv2.1`, `GNU Lesser General Public License v2.1` | `LGPL-2.1-only` |
| `Public Domain` | `LicenseRef-Public-Domain` (flag for review) |

Normalization rules:

- **"or later" matters.** `... v3 or later` / `GPLv3+` maps to the
  `-or-later` suffix (`GPL-3.0-or-later`); a bare version maps to `-only`.
  The two are distinct SPDX identifiers, so do not collapse them.
- **Do not guess ambiguous strings.** A bare `BSD`, `GNU`, `Creative
  Commons`, or `Apache` with no version resolves to no single SPDX
  identifier. Treat it as unresolved and apply `unknown_license_action`
  rather than assuming the most common variant.
- **Preserve the operators.** When a tool reports a compound expression
  (`Apache-2.0 OR MIT`, `MIT AND BSD-3-Clause`, `GPL-2.0 WITH
  Classpath-exception-2.0`), normalise each operand but keep the `OR` /
  `AND` / `WITH` structure for the classification step below.

