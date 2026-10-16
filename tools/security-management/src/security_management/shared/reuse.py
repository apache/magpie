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
"""Typed entry points into the workspace members this package reuses rather than copies.

- `github_body_field.parser` (tools/github-body-field) owns what a `### Field`
  section is; `fields` checks a rendered body the way every later
  body-field read will parse it.
- `generate_cve_json.cve_json.is_bot_credit` (tools/cve-tool-vulnogram) owns the
  bot/AI credit policy; `is_bot_credit` answers it for a credit placeholder.
"""

from __future__ import annotations

from generate_cve_json.cve_json import is_bot_credit as _is_bot_credit
from github_body_field.parser import list_fields as _list_fields


def fields(body: str) -> list[str]:
    """The `### Field` headings of `body`, in order, as github-body-field parses them."""
    return [str(name) for name in _list_fields(body)]


def is_bot_credit(name: str) -> bool:
    """Whether `name` matches the bot/AI credit policy (credited with `type: "tool"`)."""
    return bool(_is_bot_credit(name))
