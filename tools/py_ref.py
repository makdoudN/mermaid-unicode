"""Python-side twin of the Rust `mermaid_dump` driver: same styles, same tagged output."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mermaid_unicode import mermaid as _mermaid  # noqa: E402
from mermaid_unicode import rstr  # noqa: E402
from mermaid_unicode.mermaid import (  # noqa: E402
    Color, MermaidStyles, Modifier, Style, join_quoted_lines, parse_graph, render,
)


STYLES = MermaidStyles(
    border=Style(fg=Color.indexed(1)),
    node_text=Style(fg=Color.indexed(2)),
    edge=Style(fg=Color.indexed(3)),
    edge_label=Style(fg=Color.indexed(4)),
    title=Style(fg=Color.indexed(5)),
)
_TAG = {1: "B", 2: "T", 3: "E", 4: "L", 5: "I"}


def tag_for(style: Style) -> str:
    if style.fg is None:
        tag = "_"
    elif style.fg.kind == "Indexed" and style.fg.value in _TAG:
        tag = _TAG[style.fg.value]
    else:
        tag = "?"
    mods = ""
    if style.add_modifier & Modifier.BOLD:
        mods += "b"
    if style.add_modifier & Modifier.DIM:
        mods += "d"
    if style.add_modifier & Modifier.ITALIC:
        mods += "i"
    if style.add_modifier & Modifier.UNDERLINED:
        mods += "u"
    return tag + mods


def dump(src: str, width: int | None):
    """Render with the upstream layout (the polish described in README, "Layout polish", off)."""
    saved = _mermaid.UPSTREAM_LAYOUT
    _mermaid.UPSTREAM_LAYOUT = True
    try:
        art = render(src, STYLES, width)
    finally:
        _mermaid.UPSTREAM_LAYOUT = saved
    if art is None:
        return None
    styled = ["".join(f"<{tag_for(sp.style)}>{sp.content}</>" for sp in line.spans) for line in art.styled_lines]
    return art.plain_lines, styled


def deviates_from_upstream(src: str) -> bool:
    """True when ``src`` uses the port's one extension over the Rust reference: line breaks in
    labels (a literal ``\\n``, a ``<br>`` in a node label, or a quoted label spanning source
    lines). Such cases render differently by design, so the differential test leaves them out.
    """
    if "\\n" in src:
        return True
    lines = rstr.lines(src)
    if join_quoted_lines(lines) != lines:
        return True
    graph = parse_graph(src)
    return graph is not None and any("\n" in node.label for node in graph.nodes)
