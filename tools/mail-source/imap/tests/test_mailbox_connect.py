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
"""``Mailbox.connect`` builds the TLS connection with a verifying context."""

from __future__ import annotations

import imaplib
import ssl
from unittest import mock

from conftest import make_config
from imap_source.mailbox import Mailbox


def test_tls_connect_passes_a_verifying_ssl_context() -> None:
    with mock.patch.object(imaplib, "IMAP4_SSL") as imap_ssl:
        Mailbox.connect(make_config())
    imap_ssl.assert_called_once()
    args, kwargs = imap_ssl.call_args
    assert args == ("imap.example.org", 993)
    context = kwargs["ssl_context"]
    assert isinstance(context, ssl.SSLContext)
    assert context.verify_mode == ssl.CERT_REQUIRED
    assert context.check_hostname is True
    imap_ssl.return_value.login.assert_called_once_with("security-triage@example.org", "app-password")


def test_plain_connect_does_not_use_imap4_ssl() -> None:
    with (
        mock.patch.object(imaplib, "IMAP4") as imap_plain,
        mock.patch.object(imaplib, "IMAP4_SSL") as imap_ssl,
    ):
        Mailbox.connect(make_config(use_tls=False, port=143))
    imap_ssl.assert_not_called()
    imap_plain.assert_called_once_with("imap.example.org", 143)
