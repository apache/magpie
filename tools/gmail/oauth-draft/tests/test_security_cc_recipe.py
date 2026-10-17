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
"""Exercise the documented security draft recipes, without Gmail or credentials.

Regression coverage: https://github.com/apache/magpie/issues/181
"""

from __future__ import annotations

import email
import email.policy
import inspect
from pathlib import Path

import pytest

from oauth_draft import mcp_server
from oauth_draft.create_draft import build_mime

# The MCP tool name is not a Python identifier; the recipe is exec'd with it
# swapped for one.
PLAINTEXT_TOOL = "mcp__gmail-plaintext__create_draft"
PLAINTEXT_TOOL_PY = "mcp__gmail_plaintext__create_draft"


def run_oauth_curl_recipe(recipient):
    repo = Path(__file__).resolve().parents[4]
    doc = (repo / "tools/gmail/operations.md").read_text()
    section = doc.split("### Create draft — `oauth_curl` backend", 1)[1]
    recipe = section.split("```text\n", 1)[1].split("```", 1)[0]
    assert PLAINTEXT_TOOL in recipe
    recipe = recipe.replace(PLAINTEXT_TOOL, PLAINTEXT_TOOL_PY)
    calls = []
    namespace = {
        "security_cc": recipient,
        PLAINTEXT_TOOL_PY: lambda **kwargs: calls.append(kwargs),
    }
    exec(recipe, namespace)
    return calls


@pytest.mark.parametrize("recipient", [None, "", "   "])
def test_unresolved_security_cc_stops_before_backend(recipient):
    with pytest.raises(ValueError, match="security CC"):
        run_oauth_curl_recipe(recipient)


@pytest.mark.parametrize(
    "recipient", ["security@project.example", "security@apache.org", "security@acme.example"]
)
def test_resolved_security_cc_reaches_mcp_tool_and_mime(recipient):
    calls = run_oauth_curl_recipe(recipient)
    assert len(calls) == 1
    kwargs = calls[0]
    assert kwargs["cc"] == [recipient]
    assert kwargs["thread_id"]
    # Every argument the recipe passes is one the MCP tool accepts.
    assert set(kwargs) <= set(inspect.signature(mcp_server.create_draft).parameters)
    raw = build_mime(
        "triager@example.com", kwargs["to"], kwargs["cc"], [], kwargs["subject"], "Body", None, None
    )
    msg = email.message_from_bytes(raw, policy=email.policy.default)
    assert str(msg["Cc"]) == recipient


@pytest.mark.parametrize("recipient", [None, "", "   ", "security@project.example", "security@apache.org"])
def test_mcp_recipe_validates_and_passes_resolved_cc(recipient):
    repo = Path(__file__).resolve().parents[4]
    doc = (repo / "tools/gmail/operations.md").read_text()
    section = doc.split("### Create draft — `claude_ai_mcp` backend", 1)[1]
    recipe = section.split("```text\n", 1)[1].split("```", 1)[0]
    # Ellipsis denotes optional additional recipients in the catalogue.
    recipe = recipe.replace(", ...", "")
    calls = []

    def record_read(**kwargs):
        calls.append(("read", kwargs))

    def record_draft(**kwargs):
        calls.append(("create_draft", kwargs))

    namespace = {
        "security_cc": recipient,
        "mcp__claude_ai_Gmail__get_thread": record_read,
        "mcp__claude_ai_Gmail__create_draft": record_draft,
    }
    if recipient is None or not recipient.strip():
        with pytest.raises(ValueError, match="security CC"):
            exec(recipe, namespace)
        assert calls == []
    else:
        exec(recipe, namespace)
        assert [name for name, _ in calls] == ["read", "create_draft"]
        assert calls[-1][1]["cc"] == [recipient]
        assert "htmlBody" not in calls[-1][1]
