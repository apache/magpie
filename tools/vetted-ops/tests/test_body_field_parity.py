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
"""The vendored body-field parser reads every fixture exactly as github-body-field does.

`test_vendored_module_matches_its_source` already pins the copy byte for byte;
this runs both implementations over the same tricky bodies, so a parser
differential (a field one reads and the other does not) fails here even if the
copy rule is ever relaxed.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

from vetted_ops import body_field_format

_SOURCE = (
    Path(__file__).resolve().parents[2] / "github-body-field" / "src" / "github_body_field" / "parser.py"
)

FIXTURES = [
    "### Severity\n\nLow\n",
    "###  Severity\r\n\r\nLow\r\n",
    "   ### Severity ###\n\nLow\n",
    "### A\n\n````\n```\n### Severity\n```\n````\n\n### Severity\n\nLow\n",
    "### A\n\n~~~\n```\n### Severity\n~~~\n",
    "### A\n\n```\ncode\n### B\n",
    "### A\n\n- item\n   ### Severity\n   High\n\n### B\n",
    "### A\n\n> ### Severity\n\n### B\n",
    "### A\n\n1. x\n\n   ### CWE\n\n### B\n",
    "### A\n\n- item\n   ```\n\n### Severity\n\nLow\n",
    "### A\n\n  ```\ncode\n```\n\n### Severity\n\nLow\n",
    "### Severity\n\nLow\n\n### Severity\n\nHigh\n",
    "### Severity\n\nLow\n\n### Severity\n\nLow\n",
    "### A\n\n- item\n  ### Severity\n\n### B\n",
    "### A\n\n>> ### CWE\n\n### B\n",
    "### A\n\ntext\n---\n   ### Severity\n",
    "### A\n\nParagraph\n- ### Severity\n2. ### CWE\n###  Severity\n",
    "### A\n\n" + ">" * 65 + "### Severity\n",
    "### A\n\n" + "- 1. " * 10_000 + "### Severity\n",
    "### Severity\n\nLow\n\n- item\n   ```\n\n###  Severity\n\nHigh\n",
    "### A" + " " * 20_000 + "x\n",
    "### A\n\n{code:java}\n### Severity\n{code}\n\n### Severity\n\nLow\n",
    "### A\n\n```\n### Severity\n```\n\n### Severity\n\nLow\n\n### Severity\n\nHigh\n",
    "### A\n\n{noformat}\n### Severity\n\nHigh\n",
    "### A\n\n```\n\n### B\n\nx\n\n```\n\n### C\n",
]


@pytest.fixture(scope="module")
def source() -> ModuleType:
    if not _SOURCE.is_file():
        pytest.skip(f"source tree absent: {_SOURCE}")
    spec = importlib.util.spec_from_file_location("_github_body_field_parser", _SOURCE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # dataclasses resolve annotations through sys.modules
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("body", FIXTURES)
def test_both_parsers_read_the_same_fields(source: ModuleType, body: str) -> None:
    assert body_field_format.list_fields(body) == source.list_fields(body)
    ours = body_field_format.normalise(body, ["Severity", "CWE"])
    theirs = source.normalise(body, ["Severity", "CWE"])
    assert (ours.text, ours.changes, ours.needs_decision) == (
        theirs.text,
        theirs.changes,
        theirs.needs_decision,
    )
