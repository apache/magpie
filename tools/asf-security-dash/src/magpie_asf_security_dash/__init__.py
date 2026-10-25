# SPDX-License-Identifier: Apache-2.0
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

"""Read-only bridge to the ASF Security dashboard for Apache Magpie."""

from __future__ import annotations

import sys
from collections.abc import Sequence

__all__ = ["main"]


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point."""
    from magpie_asf_security_dash.cli import main as cli_main
    from magpie_asf_security_dash.client import DashError, NotAsf

    try:
        return cli_main(argv)
    except NotAsf as exc:
        print(f"magpie-asf-security-dash: {exc}", file=sys.stderr)
        return 3
    except DashError as exc:
        print(f"magpie-asf-security-dash error: {exc}", file=sys.stderr)
        return 1
