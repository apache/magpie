<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Hardware-key question and the operator's answer

Question asked: "Do you sign commits or authenticate to GitHub with a
hardware security key (YubiKey, Nitrokey, OpenPGP card), or want to
start? Default no."

Operator's answer: "No, I don't have one."

Environment:
  OS: Ubuntu 24.04
  git config commit.gpgsign: (unset)
  SSH_AUTH_SOCK: /run/user/1000/keyring/ssh
