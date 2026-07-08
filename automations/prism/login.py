#!/usr/bin/env python3
"""Log into Prism (PrismONE ID) and save the session — securely, no secret echo.

This is a self-contained Playwright login so the password is typed straight into
the field (page.fill) and never routed through any tool that echoes it. It saves
the logged-in session to a storage-state file that the headless approval agent
loads, so the approval flow itself never logs in or touches the password.

Run it once to establish the session, and on a schedule (every couple of days)
to keep it fresh so headless approvals never hit an expired session.

Env:
  PRISM_URL           login page (https://lvr-ep.prismhr.com/uex/#/auth/login)
  PRISM_USERNAME      your PrismONE ID email
  PRISM_PASSWORD      your password
  PRISM_TOTP_SECRET   base32 secret for the authenticator code
  PRISM_STATE_FILE    where to save the session (default prism_state.json)
  PRISM_HEADED        set to "1" to watch the browser (debugging); default headless

Setup (one time):
  .venv\\Scripts\\pip install playwright
  .venv\\Scripts\\python -m playwright install chromium

Usage:
  .venv\\Scripts\\python automations\\prism\\login.py
"""

from __future__ import annotations

import os
import sys

import pyotp
from playwright.sync_api import sync_playwright

STATE_FILE = os.environ.get("PRISM_STATE_FILE", "prism_state.json")


def _fill_first(page, selectors, value, what):
    """Fill the first selector that exists. Raises if none are found."""
    for sel in selectors:
        loc = page.locator(sel)
        try:
            if loc.count() > 0:
                loc.first.fill(value)
                return
        except Exception:
            continue
    raise RuntimeError(f"Could not find the {what} field (tried: {selectors})")


def _click_first(page, selectors, what, required=True):
    for sel in selectors:
        loc = page.locator(sel)
        try:
            if loc.count() > 0:
                loc.first.click()
                return True
        except Exception:
            continue
    if required:
        raise RuntimeError(f"Could not find the {what} control (tried: {selectors})")
    return False


def main() -> int:
    url = os.environ["PRISM_URL"]
    username = os.environ["PRISM_USERNAME"]
    password = os.environ["PRISM_PASSWORD"]
    secret = os.environ["PRISM_TOTP_SECRET"].replace(" ", "")
    headed = os.environ.get("PRISM_HEADED") == "1"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not headed)
        context = browser.new_context()
        page = context.new_page()
        page.set_default_timeout(45000)

        page.goto(url)
        # Start the PrismONE ID (Azure B2C) login.
        _click_first(page, [
            "text=Sign In with PrismONE ID",
            "button:has-text('PrismONE')",
        ], "PrismONE ID button")

        # Email.
        page.wait_for_load_state("networkidle")
        _fill_first(page, [
            "#signInName", "input[name='loginfmt']", "input[type='email']",
            "input[placeholder*='mail' i]", "#email",
        ], username, "email")
        _click_first(page, ["#next", "button:has-text('Next')", "#continue"],
                     "Next", required=False)

        # Password.
        _fill_first(page, [
            "#password", "input[type='password']", "input[name='passwd']",
        ], password, "password")
        _click_first(page, [
            "#next", "button:has-text('Sign in')", "button:has-text('Sign In')",
            "#continue", "button[type='submit']",
        ], "Sign in")

        # MFA (authenticator code).
        page.wait_for_load_state("networkidle")
        code = pyotp.TOTP(secret).now()
        try:
            _fill_first(page, [
                "#otpCode", "input[name='otc']", "input[type='tel']",
                "input[autocomplete='one-time-code']", "input[placeholder*='code' i]",
            ], code, "one-time code")
            _click_first(page, [
                "button:has-text('Verify')", "button:has-text('Approve')",
                "#verifyCode", "button[type='submit']", "#next",
            ], "Verify", required=False)
        except RuntimeError:
            # No MFA field appeared (already-trusted session) — continue.
            print("No MFA prompt appeared; continuing.")

        # Wait until we're back in the portal.
        try:
            page.wait_for_url("**/ess/**", timeout=45000)
        except Exception:
            page.wait_for_load_state("networkidle")

        context.storage_state(path=STATE_FILE)
        browser.close()
    print(f"SUCCESS: session saved to {STATE_FILE}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # never print secrets in the error
        print(f"LOGIN FAILED: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(1)
