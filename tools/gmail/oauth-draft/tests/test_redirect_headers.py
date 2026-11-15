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
"""The Authorization header stays on the URL that was requested.

``urllib`` copies a request's ordinary headers onto the new request it
builds when it follows a redirect. Every Gmail API call here adds its
Bearer header with ``add_unredirected_header`` instead, which ``urllib``
leaves off a redirected request.
"""

from __future__ import annotations

import http.client
import io
import urllib.request
from collections.abc import Callable
from typing import Any
from unittest.mock import patch

import pytest

from oauth_draft import create_draft, fetch_message, mark_threads_read, message_id


class _Captured(Exception):
    """Stops the call once the outgoing request has been recorded."""


CALLS: list[tuple[str, Callable[[], Any]]] = [
    ("oauth_draft.create_draft", lambda: create_draft.api_get("tok", "/threads/t1")),
    ("oauth_draft.create_draft", lambda: create_draft.api_post("tok", "/drafts", {"message": {}})),
    ("oauth_draft.fetch_message", lambda: fetch_message.fetch_raw("tok", "m1")),
    ("oauth_draft.mark_threads_read", lambda: mark_threads_read.list_thread_ids("tok", "is:unread")),
    ("oauth_draft.mark_threads_read", lambda: mark_threads_read.modify_thread("tok", "t1", [], ["UNREAD"])),
    ("oauth_draft.message_id", lambda: message_id.root_message_id("tok", "t1")),
]
IDS = ["api_get", "api_post", "fetch_raw", "list_thread_ids", "modify_thread", "root_message_id"]


def _request_sent_by(module: str, call: Callable[[], Any]) -> urllib.request.Request:
    sent: list[urllib.request.Request] = []

    def record(req: urllib.request.Request, *args: Any, **kwargs: Any) -> Any:
        sent.append(req)
        raise _Captured

    with patch(f"{module}.urllib.request.urlopen", side_effect=record), pytest.raises(_Captured):
        call()
    assert len(sent) == 1
    return sent[0]


@pytest.mark.parametrize(("module", "call"), CALLS, ids=IDS)
def test_the_requested_url_gets_the_bearer_header(module: str, call: Callable[[], Any]) -> None:
    req = _request_sent_by(module, call)
    assert req.get_header("Authorization") == "Bearer tok"


@pytest.mark.parametrize(("module", "call"), CALLS, ids=IDS)
def test_a_redirected_request_carries_no_authorization(module: str, call: Callable[[], Any]) -> None:
    req = _request_sent_by(module, call)
    redirected = urllib.request.HTTPRedirectHandler().redirect_request(
        req,
        io.BytesIO(b""),
        302,
        "Found",
        http.client.HTTPMessage(),
        "https://elsewhere.example/landing",
    )
    assert redirected is not None
    assert redirected.get_header("Authorization") is None
    assert not any(name.lower() == "authorization" for name, _ in redirected.header_items())
