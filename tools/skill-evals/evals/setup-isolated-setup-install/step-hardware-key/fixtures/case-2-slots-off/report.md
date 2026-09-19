<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Hardware-key question and the operator's answer

Question asked: "Do you sign commits or authenticate to GitHub with a
hardware security key (YubiKey, Nitrokey, OpenPGP card), or want to
start? Default no."

Operator's answer: "Yes — a YubiKey 5C, I use it for work SSO already."

Environment:
  OS: macOS 15
  git config commit.gpgsign: true
  git config gpg.format: ssh
  git config user.signingkey: /Users/alice/.ssh/id_yubikey.pub
  SSH_AUTH_SOCK: /Users/alice/.gnupg/S.gpg-agent.ssh

The operator ran `ykman openpgp info` in their own terminal and pasted:

```text
OpenPGP version:            3.4
Application version:        5.7.1
PIN tries remaining:        3
Reset code tries remaining: 0
Admin PIN tries remaining:  3
Require PIN for signature:  Once
Touch policies:
  Signature key:            Off
  Decryption key:           Off
  Authentication key:       Cached
  Attestation key:          Off
```
