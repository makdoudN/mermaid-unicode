"""Run the Rust reference (`mermaid_dump` binary built from grok-build) on a batch of cases.

Case format shared with the Rust driver::

    @@CASE <width|none>
    <mermaid source lines>
    @@END

Result per case: ``None`` (render returned None) or ``(plain_lines, styled_tagged_lines)`` where a
styled line is ``<B>text</><T>text</>…`` with tags B=border T=node_text E=edge L=edge_label
I=title _=default, followed by modifier letters (b/d/i/u).
"""
from __future__ import annotations

import os
import subprocess

DEFAULT_BIN = os.environ.get(
    "MERMAID_DUMP_BIN",
    "/private/tmp/claude-502/-Users-n-makdoud/f54d52cb-5ebc-483b-88cc-fdae8a830856/scratchpad/grok-build/target/release/mermaid_dump",
)


def encode_cases(cases: list[tuple[str, int | None]]) -> str:
    out = []
    for src, width in cases:
        out.append(f"@@CASE {'none' if width is None else width}\n{src}\n@@END\n")
    return "".join(out)


def parse_results(text: str) -> list[tuple[list[str], list[str]] | None]:
    results: list[tuple[list[str], list[str]] | None] = []
    lines = text.split("\n")
    i = 0
    while i < len(lines):
        if lines[i] != "@@CASE":
            i += 1
            continue
        i += 1
        if lines[i] == "@@NONE":
            results.append(None)
            i += 2  # skip @@END
            continue
        plain: list[str] = []
        while lines[i] != "@@STYLED":
            plain.append(lines[i])
            i += 1
        i += 1
        styled: list[str] = []
        while lines[i] != "@@END":
            styled.append(lines[i])
            i += 1
        i += 1
        results.append((plain, styled))
    return results


def run_rust(cases: list[tuple[str, int | None]], binary: str = DEFAULT_BIN):
    # Binary I/O: text mode would apply universal-newline translation and turn a bare `\r`
    # inside a rendered line into `\n`, splitting one Rust line into two.
    proc = subprocess.run([binary], input=encode_cases(cases).encode("utf-8"), capture_output=True, check=True)
    return parse_results(proc.stdout.decode("utf-8"))
