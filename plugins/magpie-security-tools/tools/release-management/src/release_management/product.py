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
"""The `<product-name>` placeholder, as the release renderers substitute it.

`<product-name>` is the canonical spelling: the value of
`release-management-config.md → product_name`, else the project's display
name (`<PROJECT>`). The renderers also accept the two older spellings an
adopter's subject templates may still carry, so an existing config keeps
rendering unchanged.
"""

from __future__ import annotations

PRODUCT_NAME = "<product-name>"
PRODUCT_NAME_SPELLINGS = (PRODUCT_NAME, "<Product Name>", "<product_name>")


def fill_product(text: str, product: str) -> str:
    """`text` with every spelling of `<product-name>` replaced by `product`."""
    for spelling in PRODUCT_NAME_SPELLINGS:
        text = text.replace(spelling, product)
    return text


def has_product(text: str) -> bool:
    """Whether `text` still holds an unrendered `<product-name>` in any spelling."""
    return any(spelling in text for spelling in PRODUCT_NAME_SPELLINGS)
