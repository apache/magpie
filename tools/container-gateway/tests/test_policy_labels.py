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
"""decide(): deny lists, filter merging, label injection, act-by-name checks."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from container_gateway.labels import LABEL_KEY
from container_gateway.policy import Allow, Deny, PolicyContext, Request, decide


@pytest.fixture
def ctx(tmp_path: Path) -> PolicyContext:
    return PolicyContext("-p", tmp_path, (tmp_path,), None, "off")


def req(method: str, path: str, query: dict[str, list[str]] | None = None, body: object = None) -> Request:
    return Request(method, path, query or {}, {}, body)


@pytest.mark.parametrize(
    "path", ["/v1.45/auth", "/v1.45/swarm/init", "/v1.45/secrets", "/v1.45/images/x/push", "/v1.45/plugins"]
)
def test_denied_families(ctx: PolicyContext, path: str) -> None:
    d = decide(req("POST", path), ctx)
    assert isinstance(d, Deny) and d.reason.startswith("denied-endpoint")


def test_unknown_path_is_denied_not_forwarded(ctx: PolicyContext) -> None:
    d = decide(req("GET", "/v1.45/frobnicate"), ctx)
    assert isinstance(d, Deny) and d.reason.startswith("unknown-endpoint")


def test_list_gets_label_filter(ctx: PolicyContext) -> None:
    a = decide(req("GET", "/v1.45/containers/json", {"all": ["1"]}), ctx)
    assert isinstance(a, Allow)
    f = json.loads(a.request.query["filters"][0])
    assert f["label"] == [f"{LABEL_KEY}=-p"]
    assert a.request.query["all"] == ["1"]
    assert a.label_check is None


def test_events_and_prune_get_label_filter(ctx: PolicyContext) -> None:
    for path in ("/v1.45/events", "/v1.45/volumes/prune", "/v5.0.0/libpod/pods/prune"):
        a = decide(req("GET" if "events" in path else "POST", path), ctx)
        assert isinstance(a, Allow), path
        assert f"{LABEL_KEY}=-p" in json.loads(a.request.query["filters"][0])["label"]


def test_container_create_is_labelled(ctx: PolicyContext) -> None:
    a = decide(req("POST", "/v1.45/containers/create", body={"Image": "alpine"}), ctx)
    assert isinstance(a, Allow)
    assert a.request.body["Labels"][LABEL_KEY] == "-p"


def test_container_create_privileged_is_denied(ctx: PolicyContext) -> None:
    d = decide(
        req("POST", "/v1.45/containers/create", body={"Image": "a", "HostConfig": {"Privileged": True}}), ctx
    )
    assert isinstance(d, Deny) and d.reason.startswith("privileged")


def test_volume_and_network_create_are_labelled(ctx: PolicyContext) -> None:
    v = decide(req("POST", "/v1.45/volumes/create", body={"Name": "v"}), ctx)
    n = decide(req("POST", "/v5.0.0/libpod/networks/create", body={"name": "n"}), ctx)
    assert isinstance(v, Allow) and v.request.body["Labels"][LABEL_KEY] == "-p"
    assert isinstance(n, Allow) and n.request.body["labels"][LABEL_KEY] == "-p"


def test_build_labels_query(ctx: PolicyContext) -> None:
    a = decide(req("POST", "/v1.45/build", {"t": ["img:1"], "labels": ['{"a":"b"}']}), ctx)
    assert isinstance(a, Allow)
    assert json.loads(a.request.query["labels"][0]) == {"a": "b", LABEL_KEY: "-p"}


def test_act_by_name_carries_label_check(ctx: PolicyContext) -> None:
    a = decide(req("POST", "/v1.45/containers/web1/start"), ctx)
    assert isinstance(a, Allow) and a.label_check == "web1"
    e = decide(req("POST", "/v1.45/exec/abc123/start", body={}), ctx)
    assert isinstance(e, Allow) and e.label_check == "abc123"


def test_ping_and_version_pass_through(ctx: PolicyContext) -> None:
    for path in ("/_ping", "/v1.45/version", "/v1.45/info"):
        a = decide(req("GET", path), ctx)
        assert isinstance(a, Allow) and a.label_check is None


def test_raw_target_round_trips_query() -> None:
    r = Request("GET", "/v1.45/containers/json", {"all": ["1"], "filters": ['{"label":["a=b"]}']}, {}, None)
    assert r.raw_target() == "/v1.45/containers/json?all=1&filters=%7B%22label%22%3A%5B%22a%3Db%22%5D%7D"
