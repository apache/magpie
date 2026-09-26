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

"""TypeSafe Jev provider import alias."""

from typed_decision.providers.jev import (
    DEFAULT_BACKOFF_SECONDS,
    DEFAULT_ENDPOINT,
    DEFAULT_TIMEOUT_SECONDS,
    JEV_MODEL,
    JevProvider,
)

__all__ = [
    "DEFAULT_BACKOFF_SECONDS",
    "DEFAULT_ENDPOINT",
    "DEFAULT_TIMEOUT_SECONDS",
    "JEV_MODEL",
    "JevProvider",
]
