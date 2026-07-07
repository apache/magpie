<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Category being checked: Code quality

Diff excerpt:
```diff
diff --git a/airflow/core/serde.py b/airflow/core/serde.py
index 2a1b4c3..7d8e9f2 100644
--- a/airflow/core/serde.py
+++ b/airflow/core/serde.py
@@ -142,7 +142,11 @@ def deserialize(data: dict) -> Any:
     """Deserialize a value from its JSON-compatible representation."""
     cls_name = data.get("__type")
     if cls_name is None:
-        return data
+        raise TypeError(
+            f"Cannot deserialize object without '__type' key; got keys: "
+            f"{list(data.keys())!r}"
+        )
     cls = _REGISTRY.get(cls_name)
```

The change replaces a silent `return data` with a proper `TypeError` that includes context. The exception is raised with a descriptive message (includes the actual keys present) so the caller can diagnose the problem. No exception is swallowed; the error path is clean and informative.
