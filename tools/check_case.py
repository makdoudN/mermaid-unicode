"""Check one Mermaid source against the Rust reference.

    python tools/check_case.py SOURCE_FILE [--width N|none ...]
    python tools/check_case.py --src 'graph TD\n A --> B' --width 80

Prints MATCH or MISMATCH (with a unified diff) for each width; exit code 1 on any mismatch.
"""
from __future__ import annotations

import argparse
import difflib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import py_ref  # noqa: E402
import rust_ref  # noqa: E402


def fmt(res) -> str:
    if res is None:
        return "NONE"
    if isinstance(res, str):
        return res
    return "\n".join(res[0] + ["--styled--"] + res[1])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("file", nargs="?")
    ap.add_argument("--src", help="inline source; \\n escapes are expanded")
    ap.add_argument("--width", nargs="*", default=["none", "40", "80", "120"])
    args = ap.parse_args()
    if args.src is not None:
        src = args.src.encode("utf-8").decode("unicode_escape").encode("latin-1").decode("utf-8") if "\\" in args.src else args.src
    elif args.file:
        src = open(args.file, encoding="utf-8").read()
    else:
        src = sys.stdin.read()
    widths = [None if w == "none" else int(w) for w in args.width]
    cases = [(src, w) for w in widths]
    rust = rust_ref.run_rust(cases)
    bad = 0
    for (s, w), expected in zip(cases, rust):
        try:
            got = py_ref.dump(s, w)
        except Exception as e:  # noqa: BLE001
            got = f"EXCEPTION {type(e).__name__}: {e}"
        if got == expected:
            print(f"width={w}: MATCH")
        else:
            bad += 1
            print(f"width={w}: MISMATCH")
            for line in difflib.unified_diff(fmt(expected).split("\n"), fmt(got).split("\n"), "rust", "python", lineterm="", n=2):
                print("  " + line)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
