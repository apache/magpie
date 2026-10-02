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
"""``thread_url`` — human-clickable archive deep-links.

The adopter declares a template per public archive; the adapter only
substitutes the Message-ID. Known shapes (Message-ID with angle brackets
stripped and URL-escaped):

- HyperKitty: ``https://lists.example.org/archives/list/<list>@example.org/message/<MSGID>/``
- Pipermail:  ``https://lists.example.org/pipermail/<list>/<month>/<msgid>.html``
- PonyMail:   ``https://lists.apache.org/thread/<msgid-hash>`` — PonyMail's
  thread id is its own hash, not the raw Message-ID, so adopters on PonyMail
  should prefer the ``ponymail`` backend for ``thread_url`` and leave
  ``IMAP_SOURCE_ARCHIVE_TEMPLATE`` unset.

Without a template the adapter falls back to an ``imap://`` URL that only
resolves for someone holding the same IMAP credentials, exactly as the
capability claim states.
"""

from __future__ import annotations

import urllib.parse

from imap_source.config import ImapConfig

_FALLBACK_SCHEME = "imap://"


def thread_url(config: ImapConfig, root_message_id: str, folder_uid: int | None = None) -> str:
    bare = root_message_id.strip().strip("<>")
    if config.archive_template:
        return config.archive_template.replace("{message_id}", urllib.parse.quote(bare, safe=""))
    location = f"{config.host}/{config.list_folder}"
    uid_suffix = f";UID={folder_uid}" if folder_uid else ""
    return f"{_FALLBACK_SCHEME}{urllib.parse.quote(location, safe='/')};MSGID={urllib.parse.quote(bare, safe='')}{uid_suffix}"
