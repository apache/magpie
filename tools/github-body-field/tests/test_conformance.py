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
"""The body-field contract's conformance suite, run against every implementation.

The cases are language-neutral (tools/body-field-contract/conformance/cases.jsonl);
each implementation is reached through a thin adapter that turns a case into a
call and the call's outcome into the case's ``expect`` shape. See
tools/body-field-contract/contract.md, "Conformance suite".
"""

from __future__ import annotations

import importlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from github_body_field import parser

TOOLS = Path(__file__).resolve().parents[2]
CASES_FILE = TOOLS / "body-field-contract" / "conformance" / "cases.jsonl"
CASES: list[dict[str, Any]] = [
    json.loads(line) for line in CASES_FILE.read_text(encoding="utf-8").split("\n") if line.strip()
]
ERROR_KINDS = {
    "FieldNotFoundError": "not_found",
    "DuplicateFieldError": "duplicate",
    "AmbiguousFieldError": "ambiguous",
}


@dataclass(frozen=True)
class Adapter:
    """One implementation: the operations it provides (None for one it does not), and how it
    differs where the contract allows."""

    list_fields: Callable[[str], list[str]] | None = None
    extract: Callable[[str, str], str | None] | None = None
    replace: Callable[[str, str, str], str] | None = None
    normalise: Callable[[str, list[str] | None, dict[str, int] | None], Any] | None = None
    escape_text: Callable[[str], str] | None = None
    escape_body: Callable[[str], str] | None = None
    lenient_names: bool = False  # BF-NAME-2's lenient lookup: skips the exact-name cases
    stripped_values: bool = False  # extract returns the value stripped
    escapes_loose: bool = True  # BF-WRITE-1's SHOULD: escapes heading-shaped lines behind containers too
    lf_only: bool = False  # the writer normalises line endings to LF before escaping


def _module_from_file(name: str, path: Path) -> ModuleType:
    if not path.is_file():
        pytest.skip(f"source tree absent: {path}")
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module  # dataclasses resolve annotations through sys.modules
    spec.loader.exec_module(module)
    return module


def _module_from_package(src: Path, name: str) -> ModuleType:
    if not (src / name.replace(".", "/")).with_suffix(".py").is_file():
        pytest.skip(f"source tree absent: {src}")
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))
    return importlib.import_module(name)


def _parser_adapter(module: Any) -> Adapter:
    return Adapter(module.list_fields, module.extract_field, module.replace_field, module.normalise)


def _tracker_adapter(
    module: Any, fields: Any, write: Callable[[str, str, str], str], **writer: Any
) -> Adapter:
    def replace(body: str, name: str, value: str) -> str:
        # The trackers' writers append a missing field; the contract's replace does not.
        if module.get_field(body, name) is None:
            raise fields.FieldNotFoundError(name)
        return write(body, name, value)

    return Adapter(
        module.list_fields if hasattr(module, "list_fields") else fields.list_fields,
        module.get_field,
        replace,
        fields.normalise,
        lenient_names=True,
        stripped_values=True,
        **writer,
    )


def _inert_text(body_module: Any) -> Callable[[str], str]:
    def escape(text: str) -> str:
        block = body_module.inert_block(text)
        assert block["ok"], block
        # The block's own fence wraps the escaped text: drop its first and last line.
        return str(block["text"]).split("\n", 1)[1].rsplit("\n", 1)[0] + "\n"

    return escape


def _adapters() -> dict[str, Callable[[], Adapter]]:
    def vetted_ops() -> Adapter:
        path = TOOLS / "vetted-ops" / "src" / "vetted_ops" / "body_field_format.py"
        return _parser_adapter(_module_from_file("_conformance_vetted_ops", path))

    def local_tracker() -> Adapter:
        sections = _module_from_package(TOOLS / "local-tracker" / "src", "magpie_local_tracker.sections")
        return _tracker_adapter(
            sections,
            sections.fields,
            lambda b, n, v: sections.set_field(b, n, v, 3)[0],
            escape_text=sections.escape_field_lines,
            escape_body=sections.escape_quoted_fields,
        )

    def jira() -> Adapter:
        markup = _module_from_package(TOOLS / "jira" / "src", "jira_bridge.markup")
        return _tracker_adapter(
            markup,
            markup.fields,
            lambda b, n, v: markup.set_field(b, n, v)[0],
            escape_body=markup.escape_quoted_fields,
        )

    def security_management() -> Adapter:
        body = _module_from_package(TOOLS / "security-management" / "src", "security_management.shared.body")
        return Adapter(escape_text=_inert_text(body), lf_only=True)

    return {
        "github-body-field": lambda: _parser_adapter(parser),
        "vetted-ops": vetted_ops,
        "local-tracker": local_tracker,
        "jira": jira,
        "security-management": security_management,
    }


ADAPTERS = _adapters()


def run_case(adapter: Adapter, case: dict[str, Any]) -> dict[str, Any] | None:
    """The case's outcome through ``adapter``, in the ``expect`` shape; None when it lacks the operation."""
    args = case["args"]
    body = case["body"]
    op = getattr(adapter, case["op"])
    if op is None:
        return None
    try:
        if case["op"] in ("list_fields", "escape_text", "escape_body"):
            return {"value": op(body)}
        if case["op"] == "extract":
            value = op(body, args["name"])
            return {"error": "not_found"} if value is None else {"value": value}
        if case["op"] == "replace":
            return {"value": op(body, args["name"], args["value"])}
        result = op(body, args.get("known_fields"), args.get("keep"))
        return {
            "value": {"text": result.text, "changes": result.changes, "needs_decision": result.needs_decision}
        }
    except LookupError as exc:
        kind = ERROR_KINDS.get(type(exc).__name__)
        if kind is None:
            raise
        return {"error": kind}


def _lf(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


@pytest.mark.parametrize("implementation", sorted(ADAPTERS))
@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_conformance(implementation: str, case: dict[str, Any]) -> None:
    adapter = ADAPTERS[implementation]()
    if adapter.lenient_names and {"case-sensitive", "inner-whitespace"} & set(case["tags"]):
        pytest.skip(f"{implementation} documents a lenient name lookup (BF-NAME-2)")
    if not adapter.escapes_loose and "escape-loose" in case["tags"]:
        pytest.skip(f"{implementation} escapes field boundaries only (BF-WRITE-1)")
    if adapter.lf_only and case["op"] == "escape_text":
        case = {**case, "body": _lf(case["body"]), "expect": {"value": _lf(case["expect"]["value"])}}
    got = run_case(adapter, case)
    if got is None:
        pytest.skip(f"{implementation} does not provide {case['op']}")
    expected = case["expect"]
    if adapter.stripped_values and case["op"] == "extract" and "value" in expected and "value" in got:
        expected, got = {"value": expected["value"].strip()}, {"value": got["value"].strip()}
    assert got == expected, f"{case['id']} ({case['clause']})"


GROOVY = shutil.which("groovy")
GROOVY_DIR = TOOLS / "body-field-contract" / "groovy"


@pytest.fixture(scope="module")
def groovy_results() -> dict[str, Any]:
    """Every case's result from the Groovy implementation, in one JVM run."""
    if GROOVY is None:
        pytest.skip("groovy not found on PATH: the Groovy implementation's conformance is not checked here")
    if not (GROOVY_DIR / "BodyFieldParser.groovy").is_file():
        pytest.skip(f"source tree absent: {GROOVY_DIR}")
    proc = subprocess.run(
        [GROOVY, "-cp", str(GROOVY_DIR), str(GROOVY_DIR / "conformance.groovy"), str(CASES_FILE)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=600,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    results: dict[str, Any] = {}
    for line in proc.stdout.split("\n"):
        if line.strip():
            row = json.loads(line)
            results[row["id"]] = row["result"]
    return results


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_groovy_conformance(groovy_results: dict[str, Any], case: dict[str, Any]) -> None:
    """The Groovy implementation (exact names, every operation) passes every case."""
    assert groovy_results.get(case["id"]) == case["expect"], f"{case['id']} ({case['clause']})"


# ------------------------------------------------------------------ format adapters

FORMATS = TOOLS / "body-field-contract" / "formats"


def _format_paths() -> list[Path]:
    """Every adapter in formats/, and any named by BODY_FIELD_FORMAT_ADAPTERS (os.pathsep-separated)."""
    paths = sorted(FORMATS.glob("*.py"))
    extra = os.environ.get("BODY_FIELD_FORMAT_ADAPTERS", "")
    paths += [Path(p).resolve() for p in extra.split(os.pathsep) if p]
    return paths


FORMAT_PATHS = _format_paths()


def _format_module(path: Path) -> ModuleType:
    return _module_from_file(f"_conformance_format_{path.stem.lstrip('_')}_{abs(hash(str(path)))}", path)


@pytest.mark.parametrize("path", FORMAT_PATHS, ids=[p.stem for p in FORMAT_PATHS])
def test_format_adapter_generic_properties(path: Path) -> None:
    """What every layout shares: reads, a rewrite that touches one field only,
    and the refusals (missing, duplicate, a value that would start a field)."""
    f = _format_module(path)
    interface = (
        *("FORMAT", "DESCRIPTION", "boundary_name", "boundary_line", "list_fields", "extract_field"),
        *("replace_field", "append_field", "normalise", "SAMPLE_BODY", "SAMPLE_FIELDS"),
    )
    assert [a for a in interface if not hasattr(f, a)] == [], "BF-FMT-1"
    assert issubclass(f.DuplicateFieldError, f.FieldNotFoundError)
    assert issubclass(f.AmbiguousFieldError, f.FieldNotFoundError)
    body, sample = f.SAMPLE_BODY, f.SAMPLE_FIELDS
    names = list(sample)
    assert f.list_fields(body) == names
    for name, value in sample.items():
        assert f.extract_field(body, name).strip() == value
    first, last = names[0], names[-1]
    assert f.replace_field(body, first, sample[first]) == body  # an unchanged value changes nothing
    new = f.replace_field(body, first, "A new synthetic value")
    assert f.extract_field(new, first).strip() == "A new synthetic value"
    assert all(f.extract_field(new, n).strip() == sample[n] for n in names[1:])
    with pytest.raises(f.AmbiguousFieldError):
        f.replace_field(body, first, "x\n" + f.boundary_line(last) + " forged")
    with pytest.raises(f.FieldNotFoundError) as missing:
        f.extract_field(body, "No such field anywhere")
    assert type(missing.value).__name__ == "FieldNotFoundError"
    duplicate = body + f.boundary_line(first) + " again\n"
    with pytest.raises(f.DuplicateFieldError):
        f.extract_field(duplicate, first)
    assert [d["kind"] for d in f.normalise(duplicate).needs_decision] == ["duplicate"]
    appended = f.append_field(body, "Appended field", "value")
    assert f.extract_field(appended, "Appended field").strip() == "value"
    crlf = body.replace("\n", "\r\n")
    assert f.extract_field(crlf, first).strip() == sample[first]
    assert f.replace_field(crlf, first, "y").count("\r\n") == crlf.count("\r\n")
    result = f.normalise(crlf)
    assert [c["kind"] for c in result.changes] == ["line_endings"]
    assert f.normalise(result.text).changes == []


def _format_cases() -> list[tuple[Path, dict[str, Any]]]:
    out = []
    for path in FORMAT_PATHS:
        fixtures = path.with_name(path.stem + ".cases.jsonl")
        if fixtures.is_file():
            out += [
                (path, json.loads(line))
                for line in fixtures.read_text(encoding="utf-8").split("\n")
                if line.strip()
            ]
    return out


FORMAT_CASES = _format_cases()


@pytest.mark.parametrize("path, case", FORMAT_CASES, ids=[f"{p.stem}-{c['id']}" for p, c in FORMAT_CASES])
def test_format_adapter_fixtures(path: Path, case: dict[str, Any]) -> None:
    adapter = _parser_adapter(_format_module(path))
    assert run_case(adapter, case) == case["expect"], f"{path.stem}: {case['id']}"


def test_every_format_adapter_has_fixtures() -> None:
    for path in FORMAT_PATHS:
        assert path.with_name(path.stem + ".cases.jsonl").is_file(), path


def test_every_operation_has_an_implementation() -> None:
    ops = {c["op"] for c in CASES}
    for op in ops:
        assert any(getattr(factory(), op) is not None for factory in ADAPTERS.values()), op


def test_every_case_names_a_clause_of_the_contract() -> None:
    contract = (TOOLS / "body-field-contract" / "contract.md").read_text(encoding="utf-8")
    ids = [c["id"] for c in CASES]
    assert len(ids) == len(set(ids))
    for case in CASES:
        assert f"**{case['clause']}" in contract, case["id"]


def test_every_must_clause_has_a_case() -> None:
    contract = (TOOLS / "body-field-contract" / "contract.md").read_text(encoding="utf-8")
    clauses = {
        line.split("**")[1].rstrip(".").split(".")[0]
        for line in contract.splitlines()
        if line.startswith("- **BF-")
    }
    tested = {c["clause"] for c in CASES}
    # BF-FMT-* bind format adapters: test_format_adapter_* run them over formats/.
    assert {c for c in clauses if not c.startswith("BF-FMT")} <= tested
    assert {"BF-FMT-1", "BF-FMT-2", "BF-FMT-3"} <= clauses
    assert FORMAT_PATHS, "formats/ holds no adapter (the template is one)"
