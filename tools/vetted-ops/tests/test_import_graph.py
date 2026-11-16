#
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
"""The package's module-level imports form no cycle.

A cycle makes a name undefined when the modules load in another order (CodeQL's
"module-level cyclic import"); `ops → cve_tool → config → tracker_backends → ops`
was one. Imports inside a function run later and cannot cause it, so only the
top-level ones count.
"""

from __future__ import annotations

import ast
from pathlib import Path

import vetted_ops

PACKAGE = Path(vetted_ops.__file__).parent


def _graph() -> dict[str, set[str]]:
    modules = {path.stem for path in PACKAGE.glob("*.py")}
    graph: dict[str, set[str]] = {}
    for path in PACKAGE.glob("*.py"):
        deps: set[str] = set()
        for node in ast.parse(path.read_text(encoding="utf-8")).body:
            if not (isinstance(node, ast.ImportFrom) and node.level == 1):
                continue
            if node.module:
                deps.add(node.module.split(".")[0])
            else:
                deps.update(alias.name for alias in node.names)
        graph[path.stem] = deps & modules
    return graph


def _cycles(graph: dict[str, set[str]]) -> list[list[str]]:
    found: list[list[str]] = []
    done: set[str] = set()
    stack: list[str] = []

    def visit(module: str) -> None:
        if module in stack:
            found.append([*stack[stack.index(module) :], module])
            return
        if module in done:
            return
        stack.append(module)
        for dep in sorted(graph[module]):
            visit(dep)
        stack.pop()
        done.add(module)

    for module in sorted(graph):
        visit(module)
    return found


def test_the_cycle_check_finds_a_cycle() -> None:
    assert _cycles({"a": {"b"}, "b": {"c"}, "c": {"a"}}) == [["a", "b", "c", "a"]]


def test_module_level_imports_form_no_cycle() -> None:
    assert _cycles(_graph()) == []
