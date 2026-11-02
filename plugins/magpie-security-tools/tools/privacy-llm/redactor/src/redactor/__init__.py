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
"""PII redactor for the apache-magpie privacy-llm tool.

Three console scripts:

- ``pii-redact`` (:mod:`redactor.redact`) — replace declared PII
  values in stdin with hash-prefixed identifiers; updates the
  local mapping file in place.
- ``pii-reveal`` (:mod:`redactor.reveal`) — replace identifiers
  in stdin with their stored real values from the local mapping.
- ``pii-list`` (:mod:`redactor.list_cmd`) — print the current
  mapping for debugging.

The contract these implement is documented in
``tools/privacy-llm/pii.md``.
"""
