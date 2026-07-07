<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Probe results:
  ssh_status:       fail  (✗ socket file at SSH_AUTH_SOCK not stat-able from inside sandbox;
                           SSH_AUTH_SOCK=/run/user/1000/gnupg/S.gpg-agent.ssh)
  localhost_status: fail  (✗ bind ok, loopback GET: urllib.error.URLError:
                           <urlopen error [Errno 111] Connection refused>)
  docker_status:    skip  (docker not on PATH; podman not on PATH)
  has_failures:     true
