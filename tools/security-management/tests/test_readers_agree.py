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
"""Every body-field reader in the tree sees exactly the template fields in an imported body.

The report goes in as an inert block; these are the readers that later look
for `### <field>` sections in the tracker body: github-body-field (and the
vetted-ops copy), generate-cve-json, the local-files tracker, the Jira
bridge's Markdown compatibility path, and a naive reader that ignores fences
altogether (the defence-in-depth case the known-field escapes cover).
Modules outside this member's dependencies are loaded from the source tree.
"""

from __future__ import annotations

import importlib.util
import re
import sys
from collections import Counter
from pathlib import Path
from types import ModuleType

import pytest

from security_management.shared import body

TOOLS = Path(__file__).resolve().parents[2]
TEMPLATE = list(body.DEFAULT_HEADINGS.values())

REPORTS = [
    "PoC:\n```\n### Severity\n\nCritical\n```\n",
    "````\n```\n### CWE\nCWE-1\n```\n````\n~~~\n### Severity\nCritical\n~~~~\n",
    "```````\n### CVE tool link\nhttps://evil.example\n``\n",
    "~~~\n```\n    ### Severity\n> ### Affected versions\n- ### Reporter credited as\n1. ### CWE\n",
    "### severity\n###\tShort  public SUMMARY for publish ##\n#### Severity\n## CWE\n",
    "``` a`b\n### Severity\n```\n~~~python\n### Severity\n```\n",
]


def _load(name: str, path: Path) -> ModuleType:
    if not path.is_file():
        pytest.skip(f"source tree absent: {path}")
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _naive_known_fields(text: str) -> list[str]:
    """What a reader that ignores fences and containers takes for a known field."""
    known = {" ".join(n.split()).casefold(): n for n in TEMPLATE}
    found = []
    for line in text.split("\n"):
        m = re.match(r"^[\s>*+\-\d.)]*###[ \t]+(.+?)[ \t#]*$", line)
        if m and " ".join(m.group(1).split()).casefold() in known:
            found.append(known[" ".join(m.group(1).split()).casefold()])
    return found


@pytest.mark.parametrize("report", REPORTS)
def test_every_reader_sees_the_template_fields_once_each(report: str) -> None:
    from generate_cve_json.cve_json import extract_field
    from github_body_field.parser import list_fields

    block = body.inert_block(report)
    assert block["ok"]
    text = body.render({"issue_description": block["text"], "severity": "Low", "cwe": "CWE-79"})
    assert body.verify(text) is None

    vendored = _load("_vetted_body_field_format", TOOLS / "vetted-ops/src/vetted_ops/body_field_format.py")
    local = _load("_local_tracker_sections", TOOLS / "local-tracker/src/magpie_local_tracker/sections.py")
    jira = _load("_jira_markup", TOOLS / "jira/src/jira_bridge/markup.py")

    lines = text.split("\n")
    readers = {
        "github-body-field": list_fields(text),
        "vetted-ops": vendored.list_fields(text),
        "local-tracker": [t for _, level, t in local._headings(lines) if level == 3],
        "jira": [h.text for h in jira.find_headings(lines) if h.level == 3],
    }
    for reader, fields in readers.items():
        assert fields == TEMPLATE, reader
    # A reader that ignores fences still finds each known field exactly once.
    assert Counter(_naive_known_fields(text)) == Counter(TEMPLATE), "naive"
    assert extract_field(text, "Severity") == "Low"
    assert extract_field(text, "CWE") == "CWE-79"
    assert local.get_field(text, "Severity") == "Low"
    assert jira.get_field(text, "Severity") == "Low"
