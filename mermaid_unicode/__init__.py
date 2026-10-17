"""Mermaid → Unicode box-drawing art, a 1:1 Python port of grok-build's ``mermaid.rs``.

>>> from mermaid_unicode import render, MermaidStyles
>>> art = render("graph LR\\n  A --> B", MermaidStyles(), max_width=80)
>>> print("\\n".join(art.plain_lines))
"""
from .mermaid import (
    Color,
    Line,
    MermaidArt,
    MermaidStyles,
    Modifier,
    RenderOptions,
    Span,
    Style,
    render,
)
from .unicode_width import char_width, str_width

__all__ = [
    "Color",
    "Line",
    "MermaidArt",
    "MermaidStyles",
    "Modifier",
    "RenderOptions",
    "Span",
    "Style",
    "render",
    "render_plain",
    "render_ansi",
    "char_width",
    "str_width",
]

__version__ = "0.4.0"


def render_plain(src: str, max_width: int | None = None, options: RenderOptions | None = None) -> str | None:
    """Render to plain text (no styling), or ``None`` for blank input."""
    art = render(src, MermaidStyles(), max_width, options)
    return None if art is None else "\n".join(art.plain_lines)


def render_ansi(
    src: str,
    max_width: int | None = None,
    styles: MermaidStyles | None = None,
    options: RenderOptions | None = None,
) -> str | None:
    """Render to a string with ANSI SGR escapes derived from each span's :class:`Style`."""
    from .ansi import DEFAULT_STYLES, line_to_ansi

    art = render(src, DEFAULT_STYLES if styles is None else styles, max_width, options)
    return None if art is None else "\n".join(line_to_ansi(line) for line in art.styled_lines)
