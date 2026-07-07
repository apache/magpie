<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

From: "T. Nguyen" <t.nguyen@independent.example>
Subject: Re: Fwd: [SECURITY] Airflow API: missing rate limiting on login endpoint

Hi,

The Airflow login endpoint at /login does not implement rate limiting. An
attacker can attempt passwords in a tight loop without any throttling or
lockout mechanism. I confirmed this on a default Airflow installation.

I did not note which version I tested — it was installed from the latest
Docker Hub image a few weeks ago.

Thanks,
T. Nguyen
