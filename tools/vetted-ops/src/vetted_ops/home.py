#
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
"""
The account's home directory.

A leaf module: it imports nothing from the package, so `config` and `cve_tool`
can both use it without `ops → cve_tool → config → tracker_backends → ops`
becoming an import cycle.
"""

from __future__ import annotations

import os
import pwd
from pathlib import Path


def account_home() -> Path:
    """The account's home directory from the password database, never `$HOME`,
    which whoever runs the command can set."""
    return Path(pwd.getpwuid(os.getuid()).pw_dir)
