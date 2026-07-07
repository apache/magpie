<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

**Title:** Authenticated user can crash the DAG processor with a cyclic DAG import

An authenticated user with DAG-upload access can submit a DAG file that
imports itself, causing infinite recursion during DAG parsing. The DAG
processor hangs indefinitely and must be restarted manually. While it is
hung, no other DAGs are scheduled.

```python
# cycle.py
import cycle  # imports itself
from airflow import DAG
dag = DAG("cycle", schedule=None)
```

Uploading this file to the DAGs folder (or via the API on deployments that
expose DAG upload) brings down the DAG processor for all other tenants
sharing the deployment. Tested on Airflow 2.10.0.
