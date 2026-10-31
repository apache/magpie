# SPDX-License-Identifier: Apache-2.0
# https://www.apache.org/licenses/LICENSE-2.0
"""Fetch backends: `github` answers the code host and the tracker; others answer one side."""

from contributor_metrics.backends.common import CODE_HOST, TRACKER, BackendError

__all__ = ["CODE_HOST", "TRACKER", "BackendError"]
