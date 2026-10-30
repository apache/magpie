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
"""Approved-LLM gate-check for the apache-magpie privacy-llm tool.

Single console script: ``privacy-llm-check`` (:mod:`checker.check`).

Parses ``<project-config>/privacy-llm.md``, extracts the active LLM
stack and the opt-in third-party-endpoint registry, applies the
approval rules from ``tools/privacy-llm/models.md``, and exits 0
if every entry in the active stack is approved — exit 1 with a
stderr explanation otherwise.

Skills shell out to this command at Step 0 (pre-flight) when they
may read ``<private-list>`` content. The contract is documented
in ``tools/privacy-llm/wiring.md``.

:func:`check_endpoint` is the runtime counterpart for a single
outbound endpoint, used by tools that make their own LLM calls.
"""

from checker.check import Verdict, check_endpoint, check_stack

__all__ = [
    "Verdict",
    "check_endpoint",
    "check_stack",
]
