<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

**Title:** HTTP operator follows redirects to internal hosts when connection URL is operator-controlled

The Airflow HTTP operator uses `allow_redirects=True` by default. When a
deployment manager configures an HTTP connection whose endpoint URL is
partially controlled by an external party (e.g. a webhook URL sourced from
a third-party SaaS), a crafted HTTP 302 redirect from that party's server
causes the worker to make a follow-up request to an arbitrary internal host
such as `http://10.0.0.1/admin`.

The redirect is followed silently with no allowlist or scheme check in
`airflow/providers/http/hooks/http.py HttpHook.run()`.

This allows the third-party SaaS to pivot the Airflow worker into the
internal network.
