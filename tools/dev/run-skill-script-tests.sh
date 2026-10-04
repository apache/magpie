#!/usr/bin/env bash
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

# Run the stdlib unittest suites that sit next to skills' sibling scripts
# (plugins/*/skills/*/tests). Those scripts are not workspace members, so
# the workspace pytest hook never sees them.
set -euo pipefail
cd "$(dirname "$0")/../.."
status=0
shopt -s nullglob
for dir in plugins/*/skills/*/tests; do
    if ! PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s "$dir" -q; then
        echo "FAILED: $dir" >&2
        status=1
    fi
done
exit "$status"
