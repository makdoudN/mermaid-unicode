"""Helpers reproducing Rust `str`/`char` semantics exactly (Unicode White_Space, `lines()`, ASCII case, …).

Python's own `str.split()`, `str.strip()`, `str.lower()` differ subtly from the Rust methods the
original renderer relies on, so the port funnels every such call through these helpers.
"""
from __future__ import annotations

from bisect import bisect_right

from . import _uw_tables as T


def _in_ranges(starts, ends, cp: int) -> bool:
    i = bisect_right(starts, cp) - 1
    return i >= 0 and cp <= ends[i]


def is_whitespace(c: str) -> bool:
    """`char::is_whitespace` (Unicode White_Space property)."""
    return _in_ranges(T.STD_IS_WHITESPACE_STARTS, T.STD_IS_WHITESPACE_ENDS, ord(c))


def is_alphanumeric(c: str) -> bool:
    """`char::is_alphanumeric` (Alphabetic or Numeric derived properties)."""
    return _in_ranges(T.STD_IS_ALPHANUMERIC_STARTS, T.STD_IS_ALPHANUMERIC_ENDS, ord(c))


def is_control(c: str) -> bool:
    """`char::is_control` (General_Category=Cc)."""
    cp = ord(c)
    return cp <= 0x1F or 0x7F <= cp <= 0x9F


def is_ascii_alphanumeric(c: str) -> bool:
    return ("a" <= c <= "z") or ("A" <= c <= "Z") or ("0" <= c <= "9")


def trim(s: str) -> str:
    """`str::trim`."""
    return trim_end(trim_start(s))


def trim_start(s: str) -> str:
    i = 0
    n = len(s)
    while i < n and is_whitespace(s[i]):
        i += 1
    return s[i:]


def trim_end(s: str) -> str:
    j = len(s)
    while j > 0 and is_whitespace(s[j - 1]):
        j -= 1
    return s[:j]


def split_whitespace(s: str) -> list[str]:
    """`str::split_whitespace` collected to a list."""
    out: list[str] = []
    cur: list[str] = []
    for c in s:
        if is_whitespace(c):
            if cur:
                out.append("".join(cur))
                cur = []
        else:
            cur.append(c)
    if cur:
        out.append("".join(cur))
    return out


def first_word(s: str) -> str | None:
    """`s.split_whitespace().next()`."""
    n = len(s)
    i = 0
    while i < n and is_whitespace(s[i]):
        i += 1
    if i >= n:
        return None
    j = i
    while j < n and not is_whitespace(s[j]):
        j += 1
    return s[i:j]


def nth_word(s: str, k: int) -> str | None:
    words = split_whitespace(s)
    return words[k] if k < len(words) else None


def contains_whitespace(s: str) -> bool:
    return any(is_whitespace(c) for c in s)


def lines(s: str) -> list[str]:
    """`str::lines`: split on `\\n`; a `\\r` is stripped only when it precedes that `\\n`.

    Mirrors `split_inclusive('\\n')` + `strip_suffix('\\n')` + `strip_suffix('\\r')`: a bare `\\r`
    ending the final (unterminated) line is kept, and there is no phantom empty final line.
    """
    parts = s.split("\n")
    tail = parts.pop()  # text after the last `\n` (empty when the string ends with `\n`)
    out = [p[:-1] if p.endswith("\r") else p for p in parts]
    if tail != "":
        out.append(tail)
    return out


def to_ascii_lowercase(s: str) -> str:
    return "".join(chr(ord(c) + 32) if "A" <= c <= "Z" else c for c in s)


def to_ascii_uppercase(s: str) -> str:
    return "".join(chr(ord(c) - 32) if "a" <= c <= "z" else c for c in s)


def eq_ignore_ascii_case(a: str, b: str) -> bool:
    return to_ascii_lowercase(a) == to_ascii_lowercase(b)


def split_once(s: str, pat: str) -> tuple[str, str] | None:
    i = s.find(pat)
    if i < 0:
        return None
    return s[:i], s[i + len(pat):]


def strip_prefix(s: str, pat: str) -> str | None:
    return s[len(pat):] if s.startswith(pat) else None


def strip_suffix(s: str, pat: str) -> str | None:
    if pat and s.endswith(pat):
        return s[: len(s) - len(pat)]
    if not pat:
        return s
    return None


def trim_end_matches(s: str, ch: str) -> str:
    j = len(s)
    while j > 0 and s[j - 1] == ch:
        j -= 1
    return s[:j]


def trim_start_matches(s: str, chars: str) -> str:
    i = 0
    while i < len(s) and s[i] in chars:
        i += 1
    return s[i:]


def parse_u32(s: str) -> int | None:
    """`s.parse::<u32>()`: optional leading `+`, ASCII digits only, must fit in u32."""
    if s.startswith("+"):
        s = s[1:]
    if not s or not all("0" <= c <= "9" for c in s):
        return None
    v = int(s)
    return v if v <= 0xFFFFFFFF else None


def parse_u32_hex(s: str) -> int | None:
    """`u32::from_str_radix(s, 16)`."""
    if s.startswith("+"):
        s = s[1:]
    if not s or not all(("0" <= c <= "9") or ("a" <= c <= "f") or ("A" <= c <= "F") for c in s):
        return None
    v = int(s, 16)
    return v if v <= 0xFFFFFFFF else None


def char_from_u32(code: int) -> str | None:
    """`char::from_u32`: rejects surrogates and values above U+10FFFF."""
    if code > 0x10FFFF or 0xD800 <= code <= 0xDFFF:
        return None
    return chr(code)


def rust_round(x: float) -> float:
    """`f64::round`: nearest integer, ties away from zero (Python's `round` is half-to-even).

    Computed as floor + exact fractional comparison rather than `floor(x + 0.5)`, which would
    misround 0.5 - 2**-54 (to 1.0) and odd integers in [2**52, 2**53).
    """
    import math

    if x != x or x in (math.inf, -math.inf):
        return x
    if x < 0.0:
        return -rust_round(-x)
    f = math.floor(x)
    frac = x - f  # exact: f is within a factor of two of x (Sterbenz) or x < 1
    return float(f + 1) if frac >= 0.5 else float(f)


def f64_to_usize(x: float) -> int:
    """`x as usize` for a finite f64: saturating, truncating toward zero."""
    if x != x:  # NaN
        return 0
    if x <= 0.0:
        return 0
    if x >= 18446744073709551615.0:
        return 18446744073709551615
    return int(x)
