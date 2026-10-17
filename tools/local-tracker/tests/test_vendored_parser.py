# SPDX-License-Identifier: Apache-2.0
# https://www.apache.org/licenses/LICENSE-2.0
"""The vendored body-field parser stays identical to tools/github-body-field's."""

from __future__ import annotations

from pathlib import Path

import pytest

_SOURCE = (
    Path(__file__).resolve().parents[2] / "github-body-field" / "src" / "github_body_field" / "parser.py"
)
_COPY = Path(__file__).resolve().parents[1] / "src" / "magpie_local_tracker" / "body_field_format.py"


def test_vendored_parser_matches_its_source() -> None:
    """This package also ships inside the vetted-ops plugin, without the
    workspace, so it carries a copy of the parser rather than depending on it.
    A copy that drifts would read fields differently from every other reader.
    Skipped in an installed copy, where the source tree is absent."""
    if not _SOURCE.is_file():
        pytest.skip(f"source tree absent: {_SOURCE}")
    assert _COPY.read_bytes() == _SOURCE.read_bytes(), (
        "body_field_format.py differs from tools/github-body-field/src/github_body_field/parser.py; "
        "re-copy it: cp tools/github-body-field/src/github_body_field/parser.py "
        "tools/local-tracker/src/magpie_local_tracker/body_field_format.py"
    )
