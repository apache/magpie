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

import functools
import importlib.util
import re
import sys
from collections import Counter
from collections.abc import Callable
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


def _load_from_package(src: Path, name: str) -> ModuleType:
    """``name`` imported from the package source tree ``src`` (it imports its siblings)."""
    if not (src / name.replace(".", "/")).with_suffix(".py").is_file():
        pytest.skip(f"source tree absent: {src}")
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))
    return importlib.import_module(name)


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
    local = _load_from_package(TOOLS / "local-tracker/src", "magpie_local_tracker.sections")
    jira = _load_from_package(TOOLS / "jira/src", "jira_bridge.markup")

    readers = {
        "github-body-field": list_fields(text),
        "vetted-ops": vendored.list_fields(text),
        "local-tracker": local.fields.list_fields(text),
        "jira": jira.list_fields(text),
    }
    for reader, fields in readers.items():
        assert fields == TEMPLATE, reader
    # A reader that ignores fences still finds each known field exactly once.
    assert Counter(_naive_known_fields(text)) == Counter(TEMPLATE), "naive"
    assert extract_field(text, "Severity") == "Low"
    assert extract_field(text, "CWE") == "CWE-79"
    assert local.get_field(text, "Severity") == "Low"
    assert jira.get_field(text, "Severity") == "Low"


# Bodies on which a field read or write must come out the same through every
# implementation: fenced, Jira-macro and unclosed blocks, duplicates, CRLF,
# two-space and closing-hash headings, container headings, private-field
# merge attempts.
BODIES = [
    "### Severity\n\nLow\n\n### CWE\n\nCWE-79\n",
    "###  Severity\r\n\r\nLow\r\n\r\n### CWE ##\r\n\r\nCWE-79\r\n",
    "### A\n\n```\n### Severity\nCritical\n```\n\n### Severity\n\nLow\n",
    "### A\n\n{code}\n### Severity\nCritical\n{code}\n\n### Severity\n\nLow\n",
    "### A\n\n{code:java}\n### Severity\n{code}\n\n### CWE\n\nx\n",
    "### A\n\n```\n### Severity\nCritical\n```\n",
    "### A\n\n```\n\n### Severity\n\nLow\n\n### CWE\n\nx\n",
    "### A\n\n{noformat}\n### Severity\n\nHigh\n",
    "### Severity\n\nLow\n\n### Severity\n\nHigh\n",
    "### Severity\n\nLow\n\n### Severity\n\nLow\n",
    "### A\n\n> ### Severity\n\n### B\n\nb\n",
    "### A\n\n- item\n   ### Severity\n   High\n\n### Severity\n\nLow\n",
    "### Summary\n\n```\n### Security mailing list thread\nfake\n```\n\n### Security mailing list thread\n\nprivate\n",
    "### Summary\n\n~~~\nsee\n\n### Security mailing list thread\n\nprivate\n\n~~~\n",
    "### A\n\n````\n```\n### Severity\n```\n````\n\n### Severity\n\nLow\n",
]
NAMES = ["Severity", "CWE", "A", "B", "Summary", "Security mailing list thread"]


def _outcome(call: Callable[[], str | None], *, strip: bool = True) -> tuple[str, str]:
    """``("value", v)``, ``("missing", "")`` or ``("error", <exception class name>)``."""
    try:
        value = call()
    except LookupError as exc:
        if type(exc).__name__ == "FieldNotFoundError":
            return ("missing", "")
        return ("error", type(exc).__name__)
    if value is None:
        return ("missing", "")
    return ("value", value.strip() if strip else value)


def _implementations() -> dict[str, tuple[Callable[[str, str], str | None], Callable[[str, str, str], str]]]:
    """Each implementation's (read, write) of one field, write returning the new body."""
    from github_body_field import parser

    vendored = _load("_vetted_body_field_format", TOOLS / "vetted-ops/src/vetted_ops/body_field_format.py")
    local = _load_from_package(TOOLS / "local-tracker/src", "magpie_local_tracker.sections")
    jira = _load_from_package(TOOLS / "jira/src", "jira_bridge.markup")
    return {
        "github-body-field": (parser.extract_field, parser.replace_field),
        "vetted-ops": (vendored.extract_field, vendored.replace_field),
        "local-tracker": (local.get_field, lambda b, n, v: local.set_field(b, n, v, 3)[0]),
        "jira": (jira.get_field, lambda b, n, v: jira.set_field(b, n, v)[0]),
    }


@pytest.mark.parametrize("text", BODIES)
def test_every_implementation_reads_and_writes_a_field_the_same(text: str) -> None:
    implementations = _implementations()
    for name in NAMES:
        reads = {
            impl: _outcome(functools.partial(read, text, name)) for impl, (read, _) in implementations.items()
        }
        assert len(set(reads.values())) == 1, (name, reads)
        if reads["github-body-field"][0] == "missing":
            continue
        writes = {
            impl: _outcome(functools.partial(write, text, name, "New\n"), strip=False)
            for impl, (_, write) in implementations.items()
        }
        assert len(set(writes.values())) == 1, (name, writes)


def test_the_bodies_cover_values_and_refusals() -> None:
    read, _ = _implementations()["github-body-field"]
    kinds = Counter(_outcome(functools.partial(read, text, name))[0] for text in BODIES for name in NAMES)
    assert kinds["value"] and kinds["error"] and kinds["missing"]
