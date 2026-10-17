"""Dependency-free test runner: ``python3 tests/run_tests.py [pattern]``.

Discovers ``test_*`` functions in ``tests/test_*.py`` and runs them; use pytest when you have it
(``python -m pytest tests -q``), this exists for environments without it.
"""
from __future__ import annotations

import importlib
import pathlib
import sys
import traceback
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def main() -> int:
    pattern = sys.argv[1] if len(sys.argv) > 1 else ""
    passed = failed = skipped = 0
    failures: list[str] = []
    for path in sorted((ROOT / "tests").glob("test_*.py")):
        if pattern and pattern not in path.name:
            continue
        try:
            mod = importlib.import_module(f"tests.{path.stem}")
        except unittest.SkipTest as e:
            skipped += 1
            print(f"SKIP {path.stem}: {e}")
            continue
        for name in sorted(dir(mod)):
            if not name.startswith("test_"):
                continue
            fn = getattr(mod, name)
            if not callable(fn):
                continue
            try:
                fn()
            except unittest.SkipTest as e:
                skipped += 1
                print(f"SKIP {path.stem}.{name}: {e}")
            except Exception:  # noqa: BLE001
                failed += 1
                failures.append(f"{path.stem}.{name}\n{traceback.format_exc()}")
            else:
                passed += 1
    for f in failures:
        print("=" * 80)
        print("FAIL", f)
    print(f"passed={passed} failed={failed} skipped={skipped}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
