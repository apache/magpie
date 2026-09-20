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
"""The build query is an allow-list, and a build gets the egress proxy (C2)."""

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


@pytest.fixture
def proxied(tmp_path: Path) -> PolicyContext:
    return PolicyContext(
        "-p",
        tmp_path,
        (tmp_path,),
        {"HTTP_PROXY": "http://host.containers.internal:8899"},
        "inject-if-available",
    )


def build(query: dict[str, list[str]], path: str = "/v1.45/build") -> Request:
    return Request("POST", path, query, {}, None)


@pytest.mark.parametrize(
    "query",
    [
        {"networkmode": ["host"]},
        {"volume": ["/:/host"]},
        {"volumes": ["/Users:/host"]},
        {"remote": ["https://evil.example/ctx.tar"]},
        {"extrahosts": ['["h:1.2.3.4"]']},
        {"addhost": ['["h:1.2.3.4"]']},
        {"securityopt": ['["label=disable"]']},
        {"labelopts": ['["disable"]']},
        {"seccomp": ["/tmp/allow-all.json"]},
        {"apparmor": ["unconfined"]},
        {"unmask": ["ALL"]},
        {"addcaps": ['["SYS_ADMIN"]']},
        {"cgroupparent": ["/x"]},
        {"ulimits": ['["nofile=1024"]']},
        {"devices": ["/dev/kvm"]},
        {"device": ["/dev/kvm"]},
        {"unsetenv": ['["PATH"]']},
        {"secrets": ['["id=s,src=/etc/passwd"]']},
        {"ssh": ["default"]},
        {"session": ["abc"]},
        {"sessionid": ["abc"]},
        {"runtime": ["/tmp/evil"]},
        # The host namespace rides in libpod's nsoptions, not in networkmode.
        {"nsoptions": ['[{"Name":"network","Host":true,"Path":""}]']},
        {"nsoptions": ['[{"Name":"pid","Host":true}]']},
        {"nsoptions": ['[{"Name":"user","Host":false,"Path":"/proc/1/ns/user"}]']},
        # An output that names a filesystem destination.
        {"output": ["type=local,dest=/Users/me"]},
        {"outputs": ['[{"Type":"local","Attrs":{"dest=/Users/me":""}}]']},
        # Anything the gateway has not learned.
        {"frobnicate": ["1"]},
    ],
)
def test_denied_build_parameters(ctx: PolicyContext, query: dict[str, list[str]]) -> None:
    d = decide(build(query), ctx)
    assert isinstance(d, Deny), query
    assert d.reason.startswith(("denied-build-parameter", "network")), d.reason


def test_a_real_docker_build_query_passes(ctx: PolicyContext) -> None:
    # What the docker CLI's classic builder sends: every parameter present,
    # most of them empty, including ones the table above refuses when set.
    query = {
        "t": ["img:1"],
        "buildargs": ["{}"],
        "cachefrom": ["[]"],
        "cgroupparent": [""],
        "cpuperiod": ["0"],
        "cpuquota": ["0"],
        "cpusetcpus": [""],
        "cpusetmems": [""],
        "cpushares": ["0"],
        "dockerfile": ["Dockerfile"],
        "labels": ["{}"],
        "memory": ["0"],
        "memswap": ["0"],
        "networkmode": [""],
        "rm": ["1"],
        "shmsize": ["0"],
        "target": [""],
        "ulimits": ["null"],
        "version": ["1"],
    }
    a = decide(build(query), ctx)
    assert isinstance(a, Allow)
    assert json.loads(a.request.query["labels"][0]) == {LABEL_KEY: "-p"}


def test_a_real_podman_build_query_passes(ctx: PolicyContext) -> None:
    # Captured from podman 6.1's remote client on `podman build -t x .`.
    query = {
        "buildargs": ['{"A":"1"}'],
        "compressionFormat": ["gzip"],
        "dockerfile": ['["Containerfile"]'],
        "forceCompressionFormat": ["1"],
        "forcerm": ["1"],
        "httpproxy": ["1"],
        "idmappingoptions": ['{"HostUIDMapping":true}'],
        "inheritannotations": ["1"],
        "isolation": ["0"],
        "jobs": ["1"],
        "layers": ["1"],
        "networkmode": ["0"],
        "nsoptions": ['[{"Name":"user","Host":true,"Path":""}]'],
        "omithistory": ["0"],
        "output": ["x"],
        "outputformat": ["application/vnd.oci.image.manifest.v1+json"],
        "pullpolicy": ["missing"],
        "retry": ["3"],
        "retry-delay": ["2s"],
        "rewritetimestamp": ["0"],
        "rm": ["1"],
        "shmsize": ["67108864"],
        "t": ["x"],
    }
    a = decide(build(dict(query), "/v5.2.0/libpod/build"), ctx)
    assert isinstance(a, Allow)
    # libpod takes `labels` as a JSON array of k=v strings, not an object.
    assert json.loads(a.request.query["labels"][0]) == [f"{LABEL_KEY}=-p"]


def test_build_networkmode_keywords_and_buildah_integers_pass(ctx: PolicyContext) -> None:
    for value in ("", "default", "bridge", "none", "0", "1", "2"):
        a = decide(build({"networkmode": [value]}), ctx)
        assert isinstance(a, Allow), value


def test_build_proxy_goes_into_buildargs(proxied: PolicyContext) -> None:
    a = decide(build({"buildargs": ['{"A":"1","HTTP_PROXY":"http://evil:1"}'], "httpproxy": ["1"]}), proxied)
    assert isinstance(a, Allow)
    args = json.loads(a.request.query["buildargs"][0])
    assert args == {"A": "1", "HTTP_PROXY": "http://host.containers.internal:8899"}
    # podman's own "let the daemon add its proxy variables" is turned off.
    assert a.request.query["httpproxy"] == ["0"]


def test_build_proxy_is_added_when_the_client_sent_no_buildargs(proxied: PolicyContext) -> None:
    a = decide(build({"t": ["x"]}), proxied)
    assert isinstance(a, Allow)
    assert json.loads(a.request.query["buildargs"][0]) == {
        "HTTP_PROXY": "http://host.containers.internal:8899"
    }


def test_build_proxy_is_not_added_when_egress_is_off(ctx: PolicyContext) -> None:
    a = decide(build({"t": ["x"]}), ctx)
    assert isinstance(a, Allow)
    assert "buildargs" not in a.request.query


@pytest.mark.parametrize(
    "query",
    [
        {"buildargs": ["notjson"]},
        {"buildargs": ["[1,2]"]},
        {"nsoptions": ["notjson"]},
        {"nsoptions": ["{}"]},
    ],
)
def test_malformed_build_values_deny_instead_of_raising(
    proxied: PolicyContext, query: dict[str, list[str]]
) -> None:
    d = decide(build(query), proxied)
    assert isinstance(d, Deny) and d.reason.startswith("malformed"), d
