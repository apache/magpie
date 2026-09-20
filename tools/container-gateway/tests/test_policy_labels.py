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

from container_gateway.decisions import Allow, Request, decide
from container_gateway.labels import LABEL_KEY
from container_gateway.policy import Deny, PolicyContext
from container_gateway.routes import _VERBS, Family


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


def test_raw_target_with_empty_query_value_list_is_bare_path() -> None:
    # A query dict like {"a": []} is a non-empty dict with nothing to
    # render; raw_target() must not append a bare "?".
    r = Request("GET", "/v1.45/info", {"a": []}, {}, None)
    assert r.raw_target() == "/v1.45/info"


# --- Fix round 1 additions below (review findings) ---


@pytest.mark.parametrize(
    ("path", "body"),
    [
        # C1: second spelling of the label field lets a foreign slug win
        ("/v1.45/volumes/create", {"Name": "v", "labels": {}, "Labels": {LABEL_KEY: "-other"}}),
        ("/v1.45/volumes/create", {"Labels": {"a": "b"}, "LABELS": {LABEL_KEY: "-other"}}),
        ("/v5.0.0/libpod/networks/create", {"name": "n", "Labels": {}, "labels": {LABEL_KEY: "-other"}}),
        ("/v5.0.0/libpod/networks/create", {"name": "n", "labels": {"a": "b"}, "LABELS": {"a": "c"}}),
    ],
)
def test_resource_create_label_spelling_collision_is_denied(
    ctx: PolicyContext, path: str, body: dict[str, object]
) -> None:
    d = decide(req("POST", path, body=body), ctx)
    assert isinstance(d, Deny) and d.reason.startswith("ambiguous-field")


def test_resource_create_non_dict_body_is_denied(ctx: PolicyContext) -> None:
    v = decide(req("POST", "/v1.45/volumes/create", body=["x"]), ctx)
    n = decide(req("POST", "/v5.0.0/libpod/networks/create", body="not-a-dict"), ctx)
    assert isinstance(v, Deny) and v.reason.startswith("malformed")
    assert isinstance(n, Deny) and n.reason.startswith("malformed")


@pytest.mark.parametrize(
    ("path", "query"),
    [
        ("/v1.45/containers/json", {"filters": ["notjson"]}),
        ("/v1.45/containers/json", {"filters": ["[1,2]"]}),
        ("/v1.45/build", {"labels": ["notjson"]}),
        ("/v1.45/build", {"labels": ["5"]}),
    ],
)
def test_malformed_query_values_deny_instead_of_raising(
    ctx: PolicyContext, path: str, query: dict[str, list[str]]
) -> None:
    d = decide(req("POST" if "build" in path else "GET", path, query), ctx)
    assert isinstance(d, Deny) and d.reason.startswith("malformed")


@pytest.mark.parametrize(
    "path",
    [
        "/v1.45/images/../swarm/init",
        "//v1.45/info",
        "/v1.45/images/alpine%2f..%2fswarm/init",
        "/v1.45/images/alpine/..\\swarm",
        "/v1.45/images/\x00json",
    ],
)
def test_unnormalised_paths_are_denied_before_routing(ctx: PolicyContext, path: str) -> None:
    d = decide(req("POST", path), ctx)
    assert isinstance(d, Deny) and d.reason.startswith("malformed")


def test_container_create_non_dict_body_is_denied(ctx: PolicyContext) -> None:
    d = decide(req("POST", "/v1.45/containers/create", body=["x"]), ctx)
    assert isinstance(d, Deny) and d.reason.startswith("malformed")


# Verbs `decide()` refuses outright (C4) or that carry a body of their own
# (C3), so "every remaining named verb is label-checked" stays exact.
_DENIED_VERBS = frozenset({"checkpoint", "restore", "generate", "play"})
_BODY_VERBS: dict[str, object] = {"exec": {"Cmd": ["sh"]}, "update": {"Memory": 1}}


@pytest.mark.parametrize("verb", sorted(_VERBS - {"push"} - _DENIED_VERBS))
@pytest.mark.parametrize(
    ("path_prefix", "name"),
    [("/v1.45/containers/web1", "web1"), ("/v5.2.0/libpod/pods/p1", "p1")],
)
def test_every_named_verb_route_carries_a_label_check(
    ctx: PolicyContext, path_prefix: str, name: str, verb: str
) -> None:
    a = decide(req("POST", f"{path_prefix}/{verb}", body=_BODY_VERBS.get(verb)), ctx)
    assert isinstance(a, Allow), (path_prefix, verb)
    assert a.label_check == name


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("POST", "/v5.2.0/libpod/pods/p1/init"),
        ("GET", "/v1.45/containers/web1/get"),
        ("POST", "/v1.45/networks/n1/exists"),
        ("GET", "/v1.45/volumes/myvol"),
        ("POST", "/v1.45/exec/abc123/resize"),
        ("GET", "/v1.45/images/alpine:3/json"),
        ("GET", "/v1.45/images/alpine:3/history"),
    ],
)
def test_no_named_route_is_fail_open_except_image_reads(ctx: PolicyContext, method: str, path: str) -> None:
    a = decide(req(method, path), ctx)
    assert isinstance(a, Allow), (method, path)
    if a.route.family is Family.IMAGES and a.route.action in ("inspect", "history"):
        return  # image reads are explicitly exempt from the label check
    assert a.route.name is not None
    assert a.label_check == a.route.name


# --- Final fix wave: exec / update bodies, denied actions, compat commit ---


@pytest.mark.parametrize(
    ("body", "rule"),
    [
        ({"Cmd": ["sh"], "Privileged": True}, "privileged"),
        ({"Cmd": ["sh"], "privileged": True}, "ambiguous-field"),
        ({"Cmd": ["sh"], "CapAdd": ["SYS_ADMIN"]}, "cap-add"),
        ({"Cmd": ["sh"], "Devices": [{"PathOnHost": "/dev/kvm"}]}, "devices"),
        ({"Cmd": ["sh"], "PidMode": "host"}, "namespace"),
        ({"Cmd": ["sh"], "NetworkMode": "host"}, "network"),
        ({"Cmd": ["sh"], "SecurityOpt": ["seccomp=unconfined"]}, "security-opt"),
        ({"Cmd": ["sh"], "Frobnicate": 1}, "unknown-field"),
        ("not-a-dict", "malformed"),
    ],
)
def test_exec_create_body_is_checked(ctx: PolicyContext, body: object, rule: str) -> None:
    d = decide(req("POST", "/v1.45/containers/web1/exec", body=body), ctx)
    assert isinstance(d, Deny), body
    assert d.reason.startswith(rule), d.reason


def test_a_real_exec_create_body_passes(ctx: PolicyContext) -> None:
    # Captured from podman 6.1's `podman exec -i <id> sh -c true`.
    body = {
        "User": "",
        "Privileged": False,
        "Tty": False,
        "AttachStdin": True,
        "AttachStderr": True,
        "AttachStdout": True,
        "DetachKeys": "ctrl-p,ctrl-q",
        "Env": [],
        "WorkingDir": "",
        "Cmd": ["sh", "-c", "true"],
    }
    a = decide(req("POST", "/v5.2.0/libpod/containers/web1/exec", body=body), ctx)
    assert isinstance(a, Allow) and a.label_check == "web1"


@pytest.mark.parametrize(
    ("body", "rule"),
    [
        ({"Memory": 1024, "CpuShares": 2}, None),
        ({"RestartPolicy": {"Name": "no"}}, None),
        ({"Privileged": True}, "unknown-field"),
        ({"Devices": [{"PathOnHost": "/dev/kvm"}]}, "devices"),
        ({"Binds": ["/:/host"]}, "unknown-field"),
    ],
)
def test_container_update_body_is_checked(ctx: PolicyContext, body: object, rule: str | None) -> None:
    verdict = decide(req("POST", "/v1.45/containers/web1/update", body=body), ctx)
    if rule is None:
        assert isinstance(verdict, Allow) and verdict.label_check == "web1"
    else:
        assert isinstance(verdict, Deny) and verdict.reason.startswith(rule)


@pytest.mark.parametrize(
    "path",
    [
        "/v5.2.0/libpod/containers/c1/checkpoint",
        "/v5.2.0/libpod/containers/c1/restore",
        "/v5.2.0/libpod/pods/p1/checkpoint",
        "/v5.2.0/libpod/pods/p1/restore",
        "/v1.45/containers/c1/checkpoint",
    ],
)
def test_checkpoint_and_restore_are_denied_endpoints(ctx: PolicyContext, path: str) -> None:
    d = decide(req("POST", path, {"export": ["/Users/me/x.tar"]}), ctx)
    assert isinstance(d, Deny) and d.reason.startswith("denied-")


@pytest.mark.parametrize("param", ["export", "import", "EXPORT"])
def test_export_and_import_query_parameters_are_denied(ctx: PolicyContext, param: str) -> None:
    d = decide(req("POST", "/v1.45/containers/c1/start", {param: ["/Users/me/x.tar"]}), ctx)
    assert isinstance(d, Deny) and d.reason.startswith("denied-query")


def test_compat_commit_takes_the_container_from_the_query(ctx: PolicyContext) -> None:
    a = decide(req("POST", "/v1.45/commit", {"container": ["web1"], "repo": ["img"]}), ctx)
    assert isinstance(a, Allow)
    assert a.label_check == "web1"
    assert a.name_in_query == "container"
    assert (a.route.family, a.route.action) == (Family.CONTAINERS, "commit")


def test_path_spelling_of_commit_still_label_checks_the_path(ctx: PolicyContext) -> None:
    a = decide(req("POST", "/v1.45/containers/web1/commit"), ctx)
    assert isinstance(a, Allow) and a.label_check == "web1" and a.name_in_query is None


def test_compat_commit_without_a_container_is_denied(ctx: PolicyContext) -> None:
    d = decide(req("POST", "/v1.45/commit", {"repo": ["img"]}), ctx)
    assert isinstance(d, Deny) and d.reason.startswith("malformed")
