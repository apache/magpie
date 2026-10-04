# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
# mypy: ignore-errors
"""Regenerate the static OpenPGP fixtures in this directory.

Not run by the test suite. The fixtures are produced without gpg-agent
(which a sandboxed test run cannot start) by writing OpenPGP v4 EdDSA
packets directly with the `cryptography` package. Both private keys
live only in memory and are discarded; only the public keys and the
detached signatures are written:

- ``KEYS``            — public key of "Test RM" (the project trust anchor)
- ``OTHER.pub``       — public key of "Other Signer" (not in KEYS)
- ``artefact.tar.gz`` — the signed payload
- ``artefact.tar.gz.asc``       — good signature by Test RM
- ``other.tar.gz`` + ``.asc``   — good signature by Other Signer

Run with:  python3 generate.py   (needs `cryptography`)
"""

from __future__ import annotations

import base64
import hashlib
import struct
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

HERE = Path(__file__).parent
CREATED = 1758326400
ED25519_OID = bytes.fromhex("2B06010401DA470F01")


def packet(tag: int, body: bytes) -> bytes:
    n = len(body)
    if n < 192:
        hdr = bytes([n])
    elif n < 8384:
        n -= 192
        hdr = bytes([(n >> 8) + 192, n & 0xFF])
    else:
        hdr = b"\xff" + struct.pack(">I", n)
    return bytes([0xC0 | tag]) + hdr + body


def mpi(data: bytes) -> bytes:
    data = data.lstrip(b"\x00") or b"\x00"
    return struct.pack(">H", int.from_bytes(data, "big").bit_length()) + data


def crc24(data: bytes) -> int:
    crc = 0xB704CE
    for b in data:
        crc ^= b << 16
        for _ in range(8):
            crc <<= 1
            if crc & 0x1000000:
                crc ^= 0x1864CFB
    return crc & 0xFFFFFF


def armor(kind: str, data: bytes) -> str:
    b64 = base64.b64encode(data).decode()
    lines = [b64[i : i + 64] for i in range(0, len(b64), 64)]
    crc = base64.b64encode(crc24(data).to_bytes(3, "big")).decode()
    return f"-----BEGIN PGP {kind}-----\n\n" + "\n".join(lines) + f"\n={crc}\n-----END PGP {kind}-----\n"


class Key:
    def __init__(self, uid: str) -> None:
        self.sk = Ed25519PrivateKey.generate()
        raw = self.sk.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
        self.body = b"\x04" + struct.pack(">I", CREATED) + bytes([22, len(ED25519_OID)]) + ED25519_OID + mpi(b"\x40" + raw)
        self.fpr = hashlib.sha1(b"\x99" + struct.pack(">H", len(self.body)) + self.body).digest()
        self.uid = uid.encode()

    def _sign(self, sigtype: int, prefix: bytes, extra_hashed: bytes = b"") -> bytes:
        hashed_sub = (
            bytes([5, 2])
            + struct.pack(">I", CREATED)  # signature creation time
            + bytes([22, 33, 4])
            + self.fpr  # issuer fingerprint
            + extra_hashed
        )
        hashed = bytes([4, sigtype, 22, 8]) + struct.pack(">H", len(hashed_sub)) + hashed_sub
        trailer = b"\x04\xff" + struct.pack(">I", len(hashed))
        digest = hashlib.sha256(prefix + hashed + trailer).digest()
        sig = self.sk.sign(digest)
        unhashed = bytes([9, 16]) + self.fpr[-8:]  # issuer key id
        body = hashed + struct.pack(">H", len(unhashed)) + unhashed + digest[:2] + mpi(sig[:32]) + mpi(sig[32:])
        return packet(2, body)

    def public_block(self) -> str:
        key_prefix = b"\x99" + struct.pack(">H", len(self.body)) + self.body
        uid_prefix = b"\xb4" + struct.pack(">I", len(self.uid)) + self.uid
        selfsig = self._sign(0x13, key_prefix + uid_prefix, extra_hashed=bytes([2, 27, 0x03]))
        return armor("PUBLIC KEY BLOCK", packet(6, self.body) + packet(13, self.uid) + selfsig)

    def detach_sign(self, data: bytes) -> str:
        return armor("SIGNATURE", self._sign(0x00, data))


def main() -> None:
    rm = Key("Test RM <rm@example.org>")
    other = Key("Other Signer <other@example.org>")
    (HERE / "KEYS").write_text(rm.public_block())
    (HERE / "OTHER.pub").write_text(other.public_block())
    payload = b"release-verify fixture payload\n"
    (HERE / "artefact.tar.gz").write_bytes(payload)
    (HERE / "artefact.tar.gz.asc").write_text(rm.detach_sign(payload))
    (HERE / "other.tar.gz").write_bytes(payload)
    (HERE / "other.tar.gz.asc").write_text(other.detach_sign(payload))
    (HERE / "FINGERPRINTS").write_text(f"rm {rm.fpr.hex().upper()}\nother {other.fpr.hex().upper()}\n")


if __name__ == "__main__":
    main()
