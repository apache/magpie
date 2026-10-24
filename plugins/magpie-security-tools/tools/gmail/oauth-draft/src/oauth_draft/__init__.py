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
"""Gmail OAuth helpers for threadId-attached drafts and bulk thread modifications.

Four console scripts:

- ``oauth-draft-setup`` — one-time interactive OAuth consent flow that
  writes the credentials JSON.
- ``oauth-draft-create`` — create a Gmail draft attached to a thread by
  ``threadId`` (the claude.ai Gmail MCP cannot do this).
- ``oauth-draft-mark-read`` — bulk-modify Gmail threads matching a
  search query (default: mark as read).
- ``oauth-draft-fetch-message`` — save one message's raw RFC-5322
  source to a file (read-only).

The module-level entry points are re-exported here so callers can do
``from oauth_draft import create_draft_main`` etc. if they prefer over
the console-script form.
"""

from __future__ import annotations

from oauth_draft.create_draft import main as create_draft_main
from oauth_draft.mark_threads_read import main as mark_threads_read_main
from oauth_draft.setup_creds import main as setup_creds_main

__all__ = [
    "create_draft_main",
    "mark_threads_read_main",
    "setup_creds_main",
]
