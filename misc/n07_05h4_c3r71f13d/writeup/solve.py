#!/usr/bin/env python3
"""
n07_05h4_c3r71f13d solver.

The intended path, scripted end to end:

  1. Load the fixed ladder (writeup/ladder.txt) and parse it into the server's
     rung/node JSON, exactly as the app's parseLadder() does in the browser.
  2. POST it to /api/solve. The server runs the engine on our rungs and hands
     back one letter per coil whose logic is now correct (the letters are never
     in the client bundle). A correct ladder yields all six.
  3. Assemble the word from those letters in coil-slot order -> SAFETY.
  4. POST the word to /api/flag to get the flag.

Usage:
    python3 solve.py                        # local http://127.0.0.1:8080
    python3 solve.py http://HOST:8080       # deployed instance
    python3 solve.py http://HOST:8080 path/to/ladder.txt
"""
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

base = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8080").rstrip("/")
ladder_path = sys.argv[2] if len(sys.argv) > 2 else os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "ladder.txt"
)

# coil -> slot index in the assembled word (from the challenge definitions in
# src/ctf.ts). Letters land in slot order, spelling the final word.
SLOT = {"ALARM": 5, "INLET": 4, "DOSE": 1, "FILL": 2, "WASTE": 3, "BLOWER": 0}
CHALLENGE_COIL = {"01": "ALARM", "02": "INLET", "03": "DOSE",
                  "04": "FILL", "05": "WASTE", "06": "BLOWER"}

KINDS = {
    "NO", "NC", "ONS", "OSR", "OSF", "OTE", "OTL", "OTU",
    "TON", "TOF", "RTO", "RES", "CTU", "CTD",
    "ADD", "SUB", "MUL", "DIV", "MOD", "MOV",
    "EQU", "NEQ", "GRT", "GEQ", "LES", "LEQ", "WIRE",
}

_uid = 0


def uid():
    global _uid
    _uid += 1
    return f"n{_uid:04d}"


def op_from(s):
    try:
        n = int(s)
        if str(n) == s:
            return {"const": n}
    except ValueError:
        pass
    return {"tag": s}


def parse_instr(toks, i):
    kind = toks[i[0]] if i[0] < len(toks) else None
    if kind not in KINDS:
        return None
    i[0] += 1
    ins = {"id": uid(), "kind": kind}
    while i[0] < len(toks) and toks[i[0]] not in ("[", "]") and toks[i[0]] not in KINDS:
        t = toks[i[0]]
        i[0] += 1
        if t.startswith("A:"):
            ins["a"] = op_from(t[2:])
        elif t.startswith("B:"):
            ins["b"] = op_from(t[2:])
        elif t.startswith("DEST:"):
            ins["dest"] = op_from(t[5:])
        elif "tag" not in ins:
            ins["tag"] = t
    return ins


def parse_series(toks, i):
    nodes = []
    while i[0] < len(toks) and toks[i[0]] != "]":
        if toks[i[0]] == "[":
            paths = []
            while i[0] < len(toks) and toks[i[0]] == "[":
                i[0] += 1
                path = parse_series(toks, i)
                if path is None or i[0] >= len(toks) or toks[i[0]] != "]":
                    return None
                i[0] += 1
                paths.append(path)
            nodes.append({"id": uid(), "or": paths})
        else:
            ins = parse_instr(toks, i)
            if ins is None:
                return None
            nodes.append(ins)
    return nodes


def parse_ladder(raw):
    rungs = []
    for line in raw.rstrip("\n").split("\n"):
        line = line.rstrip("\r")
        toks = re.findall(r"\[|\]|[^\s\[\]]+", line)
        if not toks:
            rungs.append({"id": uid(), "nodes": []})
            continue
        i = [0]
        nodes = parse_series(toks, i)
        if nodes is None or i[0] != len(toks):
            raise ValueError(f"parse error on rung: {line!r}")
        rungs.append({"id": uid(), "nodes": nodes})
    return rungs


def api(path, payload):
    req = urllib.request.Request(
        base + path,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.status, r.read().decode(errors="replace")


def main():
    with open(ladder_path, encoding="utf-8") as f:
        rungs = parse_ladder(f.read())

    # 1+2) upload the ladder; the server grades it and returns earned letters
    status, body = api("/api/solve", {"rungs": rungs})
    letters = json.loads(body).get("letters", {}) if status == 200 else {}
    print(f"[*] /api/solve -> {letters}")

    missing = [cid for cid in CHALLENGE_COIL if cid not in letters]
    if missing:
        print(f"[-] ladder did not satisfy challenges {missing}; cannot build word")
        sys.exit(1)

    # 3) assemble the word in coil-slot order
    word = "".join(
        letters[cid]
        for cid in sorted(letters, key=lambda c: SLOT[CHALLENGE_COIL[c]])
    )
    print(f"[*] assembled word: {word}")

    # 4) submit the word for the flag (one try; endpoint is rate-limited)
    for _ in range(3):
        status, body = api("/api/flag", {"word": word})
        if status == 429:
            wait = 5
            print(f"[!] rate-limited, waiting {wait}s")
            time.sleep(wait)
            continue
        break
    print(body.strip())


if __name__ == "__main__":
    main()
