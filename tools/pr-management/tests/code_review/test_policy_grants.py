# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
"""Every read code review asks for is granted to its caller in the policies.

`pr-management code-review` lists the reads it still needs under `needs`, and the
agent runs each one as `vetted-op-read --caller pr-management-code-review`.
Adopters and `setup config` derive their policy from the `[callers]` example in
the vetted-ops README, so an op missing there is refused on every adopter
(#2072 added `check-runs` to disposition without granting it there).
Magpie's own policy is checked the same way, since it reviews its own PRs.
"""

from __future__ import annotations

import ast
import re
import tomllib
from pathlib import Path

from pr_management.code_review import cli

CALLER = "pr-management-code-review"
REPO_ROOT = Path(__file__).resolve().parents[4]
README = REPO_ROOT / "tools" / "vetted-ops" / "README.md"
OWN_POLICY = REPO_ROOT / ".apache-magpie-overrides" / "tools" / "vetted-ops" / "config.toml"


def _needed_ops() -> set[str]:
    """Every op name `cli._need(...)` can be called with."""
    ops: set[str] = set()
    for node in ast.walk(ast.parse(Path(cli.__file__).read_text(encoding="utf-8"))):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "_need"):
            continue
        first = node.args[0]
        if isinstance(first, ast.Constant) and isinstance(first.value, str):
            ops.add(first.value)
        elif isinstance(first, ast.Subscript) and ast.unparse(first.value) == "CODEOWNERS_OPS":
            ops.update(cli.CODEOWNERS_OPS)
        else:
            raise AssertionError(f"cannot resolve the op of `{ast.unparse(node)}`; extend this test")
    return ops


def _template_grants() -> list[str]:
    blocks = re.findall(r"```toml\n(.*?)```", README.read_text(encoding="utf-8"), re.S)
    for block in blocks:
        callers = tomllib.loads(block).get("callers", {}) if "[callers]" in block else {}
        if CALLER in callers:
            return list(callers[CALLER])
    raise AssertionError(f"no [callers] example for {CALLER} in {README}")


def test_the_scan_finds_the_disposition_read() -> None:
    needed = _needed_ops()
    assert "check-runs" in needed
    assert set(cli.CODEOWNERS_OPS) <= needed


def test_the_readme_template_grants_every_needed_read() -> None:
    missing = sorted(_needed_ops() - set(_template_grants()))
    assert not missing, f"{README.relative_to(REPO_ROOT)} does not grant {CALLER}: {missing}"


def test_magpies_own_policy_grants_every_needed_read() -> None:
    grants = tomllib.loads(OWN_POLICY.read_text(encoding="utf-8"))["callers"][CALLER]
    missing = sorted(_needed_ops() - set(grants))
    assert not missing, f"{OWN_POLICY.relative_to(REPO_ROOT)} does not grant {CALLER}: {missing}"
