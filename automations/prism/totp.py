#!/usr/bin/env python3
"""Print the current Prism MFA one-time passcode.

Lever1/Prism uses TOTP (time-based one-time passcodes) — the same kind an
authenticator app generates. Instead of giving Alfred your 1Password, you
enroll a NEW authenticator entry for this machine and store its secret here.

How to get the secret (one time):
  1. In Prism, start "set up authenticator app" / re-add MFA.
  2. When it shows the QR code, click "enter code manually" / "can't scan" to
     reveal the base32 secret key (looks like "JBSWY3DPEHPK3PXP...").
  3. Add that same account to your 1Password AND set it here:
        setx PRISM_TOTP_SECRET "JBSWY3DPEHPK3PXP..."
  4. Prism will ask you to confirm a code to finish enrollment — run this
     script to get one.

The browser automation calls this at the MFA prompt to get a fresh code, so
codes are always generated on demand (they expire every 30s).

Dependency: pip install pyotp
"""

from __future__ import annotations

import os
import sys


def main() -> int:
    secret = os.environ.get("PRISM_TOTP_SECRET", "").replace(" ", "")
    if not secret:
        print("ERROR: PRISM_TOTP_SECRET is not set.", file=sys.stderr)
        return 1
    import pyotp

    print(pyotp.TOTP(secret).now())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
