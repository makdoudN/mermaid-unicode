"""Differential test against the Rust reference binary (skipped when the binary is absent).

Runs under pytest or via ``python3 tests/run_tests.py`` (which understands ``unittest.SkipTest``).
"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))

import corpus  # noqa: E402
import py_ref  # noqa: E402
import rust_ref  # noqa: E402


def _require_binary():
    if not os.path.exists(rust_ref.DEFAULT_BIN):
        raise unittest.SkipTest("Rust reference binary not available (set MERMAID_DUMP_BIN)")


def _run(sources, widths):
    _require_binary()
    # Line breaks in labels are a deliberate extension over upstream (README, "Line breaks in
    # labels"); those sources render differently by design and are not compared.
    sources = [s for s in sources if not py_ref.deviates_from_upstream(s)]
    cases = [(s, w) for s in sources for w in widths]
    expected = rust_ref.run_rust(cases)
    bad = [(s, w) for (s, w), exp in zip(cases, expected) if py_ref.dump(s, w) != exp]
    assert not bad, f"{len(bad)} mismatching cases, first: {bad[0]!r}"


def test_handwritten_corpus_matches_rust():
    _run(corpus.HANDWRITTEN, corpus.WIDTHS)


def test_fuzz_corpus_matches_rust():
    _run(corpus.generate(seed=2026, count=200), corpus.WIDTHS)


def test_probe_corpus_matches_rust():
    import probes  # noqa: E402  (tools/probes.py)

    _run(probes.PROBES, probes.PROBE_WIDTHS)


def test_critic_probes_match_rust():
    """359 reviewer-authored edge-case probes (tools/critic_probes.json.gz) at nine widths."""
    import gzip
    import json

    with gzip.open(os.path.join(os.path.dirname(HERE), "tools", "critic_probes.json.gz"), "rt", encoding="utf-8") as f:
        sources = json.load(f)
    _run(sources, [None, 1, 8, 9, 24, 40, 80, 120, 200])
