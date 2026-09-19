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
"""Project identity: the slug, the label, and filter merging."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from container_gateway.labels import (
    LABEL_KEY,
    has_label,
    label_filter_value,
    merge_filters,
    project_slug,
    with_label,
)


def test_slug_is_resolved_path_with_dashes(tmp_path: Path) -> None:
    root = tmp_path / "proj"
    root.mkdir()
    link = tmp_path / "link"
    link.symlink_to(root)
    assert project_slug(link) == str(root.resolve()).replace("/", "-")
    assert project_slug(root).startswith("-")


def test_with_label_overrides_client_value() -> None:
    out = with_label({"a": "b", LABEL_KEY: "spoofed"}, "-x")
    assert out == {"a": "b", LABEL_KEY: "-x"}
    assert with_label(None, "-x") == {LABEL_KEY: "-x"}


def test_has_label() -> None:
    assert has_label({LABEL_KEY: "-x"}, "-x")
    assert not has_label({LABEL_KEY: "-y"}, "-x")
    assert not has_label(None, "-x")
    assert not has_label({}, "-x")


def test_label_filter_value() -> None:
    assert label_filter_value("-x") == "org.apache.magpie.project=-x"


@pytest.mark.parametrize(
    ("raw", "expected_labels"),
    [
        (None, ["org.apache.magpie.project=-x"]),
        ("", ["org.apache.magpie.project=-x"]),
        ('{"status":["running"]}', ["org.apache.magpie.project=-x"]),
        ('{"label":["foo=bar"]}', ["foo=bar", "org.apache.magpie.project=-x"]),
        # docker's older map-of-maps form
        ('{"label":{"foo=bar":true}}', ["foo=bar", "org.apache.magpie.project=-x"]),
        # a client trying to widen to another project is narrowed, not merged away
        (
            '{"label":["org.apache.magpie.project=-other"]}',
            ["org.apache.magpie.project=-other", "org.apache.magpie.project=-x"],
        ),
    ],
)
def test_merge_filters(raw: str | None, expected_labels: list[str]) -> None:
    merged = json.loads(merge_filters(raw, "-x"))
    assert sorted(merged["label"]) == sorted(expected_labels)
    if raw and "status" in raw:
        assert merged["status"] == ["running"]


def test_merge_filters_rejects_garbage() -> None:
    with pytest.raises(ValueError):
        merge_filters("{not json", "-x")
