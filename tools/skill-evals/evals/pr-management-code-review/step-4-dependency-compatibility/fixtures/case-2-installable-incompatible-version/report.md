<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Title: Add client helper to the widget adapter

Diff:

```diff
--- a/packages/widget-adapter/pyproject.toml
+++ b/packages/widget-adapter/pyproject.toml
@@
 dependencies = [
     "compat-core>=1.8.0",
     "query-base>=1.32.0",
 ]

--- /dev/null
+++ b/packages/widget-adapter/src/widget_adapter/client.py
@@
+from compat_core.exceptions import FeatureUnavailable
+
+def get_client():
+    raise FeatureUnavailable("client support is not installed")
```

Published package metadata:

- `FeatureUnavailable` is first exported by `compat-core` 1.12.0.
- `query-base` 1.32.0 has no dependency on `compat-core`.
- No other mandatory dependency constrains `compat-core`.
- `query-base==1.32.0` with `compat-core==1.8.0` is a concrete
  resolution that satisfies every declared constraint.
- The supplied metadata establishes that concrete resolution only; other
  versions allowed by the declared constraints have not been enumerated.
