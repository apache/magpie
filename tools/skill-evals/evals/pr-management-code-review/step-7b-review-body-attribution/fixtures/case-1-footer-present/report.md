<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

**REQUEST_CHANGES**

- [major] airflow/api/client.py: removing the public `schedule` parameter
  breaks existing callers; keep it through a deprecation cycle.

---

> *This review was drafted by an AI-assisted tool and confirmed by an
> Airflow maintainer. After you've addressed the points above and pushed an
> update, an Airflow maintainer — a real person — will take the next look at
> the PR. The findings cite the project's review criteria; if you think one
> of them is mis-applied, please reply on the PR and a maintainer will weigh
> in.*
>
> *More on how Airflow handles maintainer review:*
> [contributing-docs/05_pull_requests.rst](https://github.com/apache/airflow/blob/main/contributing-docs/05_pull_requests.rst).
