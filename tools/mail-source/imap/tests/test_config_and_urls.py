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
"""Environment configuration and archive-URL fallback tests."""

from __future__ import annotations

import pytest

from conftest import make_config
from imap_source.archive_url import thread_url
from imap_source.config import ConfigError, ImapConfig

BASE_ENV = {
    "IMAP_SOURCE_HOST": "imap.example.org",
    "IMAP_SOURCE_USER": "security-triage@example.org",
    "IMAP_SOURCE_PASSWORD": "app-password",
}


def test_config_defaults() -> None:
    config = ImapConfig.from_env(dict(BASE_ENV))
    assert config.use_tls is True
    assert config.port == 993
    assert config.list_folder == "INBOX"
    assert config.drafts_folder == "Drafts"
    assert config.sent_folder == "Sent"


def test_config_requires_host_and_user() -> None:
    with pytest.raises(ConfigError):
        ImapConfig.from_env({})
    with pytest.raises(ConfigError):
        ImapConfig.from_env({"IMAP_SOURCE_HOST": "h"})


def test_config_requires_a_password_source() -> None:
    with pytest.raises(ConfigError):
        ImapConfig.from_env({"IMAP_SOURCE_HOST": "h", "IMAP_SOURCE_USER": "u"})


def test_config_folders_can_be_declared_off() -> None:
    config = ImapConfig.from_env(
        {
            **BASE_ENV,
            "IMAP_SOURCE_DRAFTS_FOLDER": "none",
            "IMAP_SOURCE_SENT_FOLDER": "off",
        }
    )
    assert config.drafts_folder is None
    assert config.sent_folder is None


def test_config_plain_port_default_without_tls() -> None:
    config = ImapConfig.from_env({**BASE_ENV, "IMAP_SOURCE_SSL": "0"})
    assert config.use_tls is False
    assert config.port == 143


def test_thread_url_uses_the_template_when_declared() -> None:
    config = make_config(
        archive_template="https://lists.example.org/hyperkitty/list/x@y/message/{message_id}/"
    )
    url = thread_url(config, "<report-1@lists.example.org>")
    assert url == "https://lists.example.org/hyperkitty/list/x@y/message/report-1%40lists.example.org/"


def test_thread_url_falls_back_to_imap_scheme() -> None:
    config = make_config()
    url = thread_url(config, "<report-1@lists.example.org>")
    assert url == "imap://imap.example.org/INBOX;MSGID=report-1%40lists.example.org"
