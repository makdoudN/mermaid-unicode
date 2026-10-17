"""Differential test: Python port vs the Rust reference binary on the shared corpus.

    python tools/diff_against_rust.py [--seed N] [--count N] [--show K]
"""
from __future__ import annotations

import argparse
import difflib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import corpus  # noqa: E402
import py_ref  # noqa: E402
import rust_ref  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--count", type=int, default=400)
    ap.add_argument("--show", type=int, default=5)
    ap.add_argument("--widths", default=",".join("none" if w is None else str(w) for w in corpus.WIDTHS))
    ap.add_argument("--no-handwritten", action="store_true")
    args = ap.parse_args()
    widths = [None if w == "none" else int(w) for w in args.widths.split(",")]

    sources = ([] if args.no_handwritten else list(corpus.HANDWRITTEN)) + corpus.generate(args.seed, args.count)
    # sources using the line-break extension (literal \n, <br> in node labels, multi-line quoted
    # labels) differ from upstream by design
    kept = [src for src in sources if not py_ref.deviates_from_upstream(src)]
    skipped_ext = len(sources) - len(kept)
    sources = kept
    cases = [(src, w) for src in sources for w in widths]
    rust = rust_ref.run_rust(cases)
    assert len(rust) == len(cases), (len(rust), len(cases))
    mismatches = 0
    shown = 0
    for (src, w), expected in zip(cases, rust):
        try:
            got = py_ref.dump(src, w)
        except Exception as e:  # noqa: BLE001
            got = f"EXCEPTION {type(e).__name__}: {e}"
        if got != expected:
            mismatches += 1
            if shown < args.show:
                shown += 1
                print("=" * 100)
                print(f"MISMATCH width={w} src={src!r}")
                exp_txt = "NONE" if expected is None else "\n".join(expected[0] + ["--styled--"] + expected[1])
                got_txt = got if isinstance(got, str) else ("NONE" if got is None else "\n".join(got[0] + ["--styled--"] + got[1]))
                for line in difflib.unified_diff(exp_txt.split("\n"), got_txt.split("\n"), "rust", "python", lineterm="", n=2):
                    print(line)
    print(f"cases={len(cases)} sources={len(sources)} mismatches={mismatches} skipped_line_break_ext={skipped_ext}")
    return 1 if mismatches else 0


if __name__ == "__main__":
    sys.exit(main())
