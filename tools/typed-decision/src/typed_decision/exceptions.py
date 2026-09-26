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

"""Exceptions for typed decision operations."""

from __future__ import annotations


class TypedDecisionUnavailable(Exception):
    """Raised when a typed decision backend is unavailable or fails.

    Under the fail-open contract, on missing configuration, timeout,
    network error, provider error, or privacy gate rejection, every
    operation raises this exception — never a fabricated answer —
    so callers can catch it and fall back to their own reasoning.
    """
