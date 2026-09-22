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

"""The two orderings a string comparison gets wrong, in both directions."""

from __future__ import annotations

import pytest

from setup_preflight.version import InvalidVersion, below, compare, parse


def test_ten_sorts_above_nine_not_below_it() -> None:
    assert below("0.9.0", "0.10.0")
    assert not below("0.10.0", "0.9.0")


def test_a_dev_build_is_below_the_release_it_leads_to() -> None:
    assert below("0.2.0.dev202609110041", "0.2.0")
    assert not below("0.2.0", "0.2.0.dev202609110041")


def test_two_dev_builds_of_one_release_order_by_their_number() -> None:
    assert below("0.2.0.dev1", "0.2.0.dev2")


def test_a_dev_build_still_outranks_an_older_release() -> None:
    assert not below("0.2.0.dev1", "0.1.9")


def test_missing_trailing_zeros_compare_equal() -> None:
    assert compare("1.2", "1.2.0") == 0
    assert compare("1", "1.0.0") == 0


def test_a_leading_v_is_tolerated() -> None:
    assert compare("v1.2.0", "1.2.0") == 0


@pytest.mark.parametrize("bad", ["", "latest", "1.2.3rc1", "1.2.3-dev", "1.2.3.post1"])
def test_anything_outside_the_subset_raises_rather_than_guessing(bad: str) -> None:
    with pytest.raises(InvalidVersion):
        parse(bad)
