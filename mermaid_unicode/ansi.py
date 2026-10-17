"""ANSI SGR rendering for styled lines (the Rust crate delegates this to ratatui/anstyle)."""
from __future__ import annotations

from .mermaid import Color, Line, MermaidStyles, Modifier, Style

_NAMED_FG = {
    "Black": 30, "Red": 31, "Green": 32, "Yellow": 33, "Blue": 34, "Magenta": 35, "Cyan": 36,
    "Gray": 37, "DarkGray": 90, "LightRed": 91, "LightGreen": 92, "LightYellow": 93,
    "LightBlue": 94, "LightMagenta": 95, "LightCyan": 96, "White": 97,
}
_MOD_CODES = (
    (Modifier.BOLD, 1), (Modifier.DIM, 2), (Modifier.ITALIC, 3), (Modifier.UNDERLINED, 4),
    (Modifier.SLOW_BLINK, 5), (Modifier.RAPID_BLINK, 6), (Modifier.REVERSED, 7),
    (Modifier.HIDDEN, 8), (Modifier.CROSSED_OUT, 9),
)

#: A readable default palette: dim borders/edges, bold titles, italic edge labels.
DEFAULT_STYLES = MermaidStyles(
    border=Style(fg=Color.DarkGray),
    node_text=Style(),
    edge=Style(fg=Color.DarkGray),
    edge_label=Style(add_modifier=Modifier.ITALIC),
    title=Style(add_modifier=Modifier.BOLD),
)


def _color_codes(color: Color, base: int) -> list[str]:
    if color.kind == "Reset":
        return [str(base + 9)]
    if color.kind in _NAMED_FG:
        code = _NAMED_FG[color.kind]
        return [str(code + (base - 30))]
    if color.kind == "Indexed":
        return [str(base + 8), "5", str(color.value)]
    if color.kind == "Rgb":
        r, g, b = color.value
        return [str(base + 8), "2", str(r), str(g), str(b)]
    return []


def sgr(style: Style) -> str:
    codes: list[str] = []
    if style.fg is not None:
        codes += _color_codes(style.fg, 30)
    if style.bg is not None:
        codes += _color_codes(style.bg, 40)
    for mod, code in _MOD_CODES:
        if style.add_modifier & mod:
            codes.append(str(code))
    return f"\x1b[{';'.join(codes)}m" if codes else ""


def line_to_ansi(line: Line) -> str:
    out: list[str] = []
    for span in line.spans:
        prefix = sgr(span.style)
        out.append(f"{prefix}{span.content}\x1b[0m" if prefix else span.content)
    return "".join(out)
