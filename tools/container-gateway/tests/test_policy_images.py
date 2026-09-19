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
"""Images are shared: read freely, remove or tag only what the project built."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from container_gateway.decisions import Allow, Request, decide
from container_gateway.labels import LABEL_KEY
from container_gateway.policy import Deny, PolicyContext


@pytest.fixture
def ctx(tmp_path: Path) -> PolicyContext:
    return PolicyContext("-p", tmp_path, (tmp_path,), None, "off")


def req(method: str, path: str, query: dict[str, list[str]] | None = None) -> Request:
    return Request(method, path, query or {}, {}, None)


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/v1.45/images/json"),
        ("POST", "/v1.45/images/create"),
        ("GET", "/v1.45/images/alpine:3/json"),
        ("GET", "/v1.45/images/alpine:3/history"),
        ("GET", "/v1.45/images/alpine:3/get"),
        ("GET", "/v1.45/images/search"),
        ("POST", "/v1.45/images/load"),
    ],
)
def test_reads_and_pull_need_no_label(ctx: PolicyContext, method: str, path: str) -> None:
    a = decide(req(method, path), ctx)
    assert isinstance(a, Allow) and a.label_check is None


def test_remove_and_tag_need_label(ctx: PolicyContext) -> None:
    rm = decide(req("DELETE", "/v1.45/images/alpine:3"), ctx)
    tag = decide(req("POST", "/v1.45/images/alpine:3/tag", {"repo": ["x"], "tag": ["y"]}), ctx)
    assert isinstance(rm, Allow) and rm.label_check == "alpine:3"
    assert isinstance(tag, Allow) and tag.label_check == "alpine:3"


def test_push_is_denied(ctx: PolicyContext) -> None:
    assert isinstance(decide(req("POST", "/v1.45/images/alpine:3/push"), ctx), Deny)


def test_image_prune_is_dangling_and_labelled(ctx: PolicyContext) -> None:
    a = decide(req("POST", "/v1.45/images/prune"), ctx)
    assert isinstance(a, Allow)
    f = json.loads(a.request.query["filters"][0])
    assert f["dangling"] == ["true"]
    assert f["label"] == [f"{LABEL_KEY}=-p"]
