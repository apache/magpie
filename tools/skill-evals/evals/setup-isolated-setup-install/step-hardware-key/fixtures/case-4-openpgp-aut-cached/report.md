<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Hardware-key question and the operator's answer

Question asked: "Do you sign commits or authenticate to GitHub with a
hardware security key (YubiKey, Nitrokey, OpenPGP card), or want to
start? Default no."

Operator's answer: "Yes, a YubiKey 5 NFC. Every push and pull makes me
touch it, which is getting old."

Environment:
  OS: Ubuntu 26.04
  git config commit.gpgsign: true
  git config gpg.format: openpgp
  git remote get-url origin: git@github.com:alice/project.git
  SSH_AUTH_SOCK: /run/user/1000/gnupg/S.gpg-agent.ssh

The operator ran `ykman openpgp info` in their own terminal and pasted:

```text
OpenPGP version:            3.4
Application version:        5.7.1
Touch policies:
  Signature key:            Cached
  Decryption key:           Off
  Authentication key:       Cached
  Attestation key:          Off
```
