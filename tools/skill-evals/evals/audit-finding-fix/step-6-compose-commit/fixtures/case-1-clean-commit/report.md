<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

fix(models): address ruff findings in xcom.py and helpers.py

Ran ruff on the models package; cleared 4 findings: removed
unused `os` import (F401), wrapped two long lines (E501), and
replaced an assigned-but-unused local with `_` (F841). No
behaviour change.

Generated-by: Claude (Opus 4.7)
