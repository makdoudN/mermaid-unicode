"""Self-contained terminal renderer for Mermaid diagrams.

Renders ``graph``/``flowchart``, ``sequenceDiagram``, ``stateDiagram``, ``classDiagram`` and
``erDiagram`` blocks as Unicode box-drawing art. Unsupported diagram types fall back to the raw
source in a framed box.

This is a 1:1 port of ``crates/codegen/xai-grok-markdown/src/mermaid.rs`` from
https://github.com/xai-org/grok-build (Apache-2.0). Function names, constants, algorithms and
evaluation order follow the Rust original so that the output is byte-identical; Rust-specific
string semantics go through :mod:`mermaid_unicode.rstr` and display widths through
:mod:`mermaid_unicode.unicode_width` (a port of the ``unicode-width`` 0.2.0 crate).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum, IntFlag

from . import rstr
from .unicode_width import char_width as _uw_char_width
from .unicode_width import str_width as width

__all__ = [
    "Color",
    "Modifier",
    "Style",
    "Span",
    "Line",
    "MermaidStyles",
    "MermaidArt",
    "render",
]


# ---------------------------------------------------------------------------------------------
# Minimal stand-ins for `ratatui::style::{Style, Modifier}` and `ratatui::text::{Line, Span}`
# ---------------------------------------------------------------------------------------------
class Modifier(IntFlag):
    """`ratatui::style::Modifier` bit flags."""

    BOLD = 0b0000_0000_0001
    DIM = 0b0000_0000_0010
    ITALIC = 0b0000_0000_0100
    UNDERLINED = 0b0000_0000_1000
    SLOW_BLINK = 0b0000_0001_0000
    RAPID_BLINK = 0b0000_0010_0000
    REVERSED = 0b0000_0100_0000
    HIDDEN = 0b0000_1000_0000
    CROSSED_OUT = 0b0001_0000_0000


class Color:
    """`ratatui::style::Color` subset: named ANSI colors, `Indexed(n)` and `Rgb(r, g, b)`."""

    __slots__ = ("kind", "value")

    def __init__(self, kind: str, value=None):
        self.kind = kind
        self.value = value

    def __eq__(self, other):
        return isinstance(other, Color) and (self.kind, self.value) == (other.kind, other.value)

    def __hash__(self):
        return hash((self.kind, self.value))

    def __repr__(self):
        return f"Color.{self.kind}" if self.value is None else f"Color.{self.kind}({self.value})"

    @classmethod
    def indexed(cls, n: int) -> "Color":
        return cls("Indexed", n)

    @classmethod
    def rgb(cls, r: int, g: int, b: int) -> "Color":
        return cls("Rgb", (r, g, b))


for _name in (
    "Reset", "Black", "Red", "Green", "Yellow", "Blue", "Magenta", "Cyan", "Gray", "DarkGray",
    "LightRed", "LightGreen", "LightYellow", "LightBlue", "LightMagenta", "LightCyan", "White",
):
    setattr(Color, _name, Color(_name))


@dataclass(frozen=True)
class Style:
    """`ratatui::style::Style` (fg/bg/underline color + add/sub modifiers)."""

    fg: Color | None = None
    bg: Color | None = None
    underline_color: Color | None = None
    add_modifier: Modifier = Modifier(0)
    sub_modifier: Modifier = Modifier(0)

    def with_fg(self, color: Color | None) -> "Style":
        return Style(color, self.bg, self.underline_color, self.add_modifier, self.sub_modifier)

    def with_bg(self, color: Color | None) -> "Style":
        return Style(self.fg, color, self.underline_color, self.add_modifier, self.sub_modifier)

    def add_modifiers(self, modifier: Modifier) -> "Style":
        """`Style::add_modifier`: adds to `add_modifier`, removes from `sub_modifier`."""
        return Style(
            self.fg,
            self.bg,
            self.underline_color,
            Modifier(self.add_modifier | modifier),
            Modifier(self.sub_modifier & ~modifier),
        )

    def remove_modifiers(self, modifier: Modifier) -> "Style":
        return Style(
            self.fg,
            self.bg,
            self.underline_color,
            Modifier(self.add_modifier & ~modifier),
            Modifier(self.sub_modifier | modifier),
        )


@dataclass
class Span:
    """`ratatui::text::Span`: a run of text with one style."""

    content: str
    style: Style = Style()


@dataclass
class Line:
    """`ratatui::text::Line`: a list of spans."""

    spans: list[Span] = field(default_factory=list)


@dataclass
class MermaidStyles:
    """Theme-derived styles used when painting a diagram."""

    border: Style = Style()
    node_text: Style = Style()
    edge: Style = Style()
    edge_label: Style = Style()
    title: Style = Style()


@dataclass
class MermaidArt:
    """Rendered diagram: styled lines for the TUI and plain lines for ANSI output."""

    styled_lines: list[Line]
    plain_lines: list[str]


# ---------------------------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------------------------
MAX_LABEL = 28
#: Edge labels may be this wide when `UPSTREAM_LAYOUT` is off (upstream: `MAX_LABEL`).
MAX_LABEL_POLISHED = 40
PAD = 1
GAP_X = 3
GAP_Y = 2
#: Node labels wrap to at most this many display columns per line, and at most this many lines
#: (overflow is truncated with an ellipsis).
WRAP_WIDTH = 24
MAX_LINES = 4
#: Identifier-boundary characters preferred as break points when a single word is too wide to
#: fit, so it is not sliced mid-segment.
LABEL_BREAK_CHARS = ("_", "-", ".", "/")
#: Sentinel marking the trailing column of a wide glyph (never emitted).
CONT = chr(0)
MAX_NODES = 128
MAX_EDGES = 512
MAX_GROUPS = 24
MAX_GROUP_DEPTH = 6
MAX_CANVAS_CELLS = 1 << 21

#: True reproduces the upstream Rust layout exactly (the differential harness sets it). False,
#: the default, enables the layout polish described in the README: a space between an arrowhead
#: and its label, wider edge labels that are never dropped when their preferred row is taken,
#: and sequence diagrams that wrap their text to fit the width limit instead of falling back.
UPSTREAM_LAYOUT = False


def _label_cap() -> int:
    return MAX_LABEL if UPSTREAM_LAYOUT else MAX_LABEL_POLISHED


@dataclass(frozen=True)
class RenderOptions:
    """Knobs on top of the upstream defaults, passed to `render(..., options=...)`.

    ``wrap_width``: node, note and participant labels wrap to this many columns (upstream 24).
    ``max_lines``: lines per label paragraph before the ``…`` truncation (upstream 4).
    ``align``: ``"center"`` (upstream) or ``"left"`` for the text inside boxes. Left alignment
    with a wide wrap suits step-by-step pipeline charts whose labels have a title line and a
    detail line.
    """

    wrap_width: int = WRAP_WIDTH
    max_lines: int = MAX_LINES
    align: str = "center"

    def __post_init__(self) -> None:
        if self.wrap_width < 1 or self.max_lines < 1:
            raise ValueError("wrap_width and max_lines must be at least 1")
        if self.align not in ("center", "left"):
            raise ValueError(f"align must be 'center' or 'left', not {self.align!r}")


_DEFAULT_OPTIONS = RenderOptions()
_options = _DEFAULT_OPTIONS


def _opts() -> RenderOptions:
    """The options of the `render` call in progress (the defaults outside one)."""
    return _options


def char_width(c: str) -> int:
    """`UnicodeWidthChar::width(c).unwrap_or(0)`."""
    w = _uw_char_width(c)
    return 0 if w is None else w


class Oversize(Enum):
    WIDTH = "Width"
    CELLS = "Cells"


class OversizeError(Exception):
    """Carrier for `Err(Oversize)`."""

    def __init__(self, kind: Oversize):
        super().__init__(kind)
        self.kind = kind


def render(
    src: str, styles: MermaidStyles, max_width: int | None, options: RenderOptions | None = None
) -> MermaidArt | None:
    """Render a mermaid source block, or ``None`` for blank input."""
    global _options
    if rstr.trim(src) == "":
        return None

    saved = _options
    _options = _DEFAULT_OPTIONS if options is None else options
    try:
        try:
            art = _render_supported(src, styles, max_width)
        except OversizeError as e:
            too_wide = e.kind == Oversize.WIDTH
        else:
            if art is not None:
                return art
            too_wide = False
        return fallback(src, styles, max_width, too_wide)
    finally:
        _options = saved


def _render_supported(src: str, styles: MermaidStyles, max_width: int | None) -> MermaidArt | None:
    """The `parse_graph(...).or_else(...)` chain: the first parser that accepts the source wins."""
    graph = parse_graph(src)
    if graph is not None:
        if not graph.groups:
            return layout_flowchart(graph, styles, max_width)
        return render_grouped(graph, styles, max_width)
    graph = parse_state(src)
    if graph is not None:
        return layout_flowchart(graph, styles, max_width)
    parsed = parse_class(src)
    if parsed is not None:
        graph, infos = parsed
        return render_class(graph, infos, styles, max_width)
    parsed = parse_er(src)
    if parsed is not None:
        graph, infos = parsed
        return render_class(graph, infos, styles, max_width)
    seq = parse_sequence(src)
    if seq is not None:
        return layout_sequence(seq, styles, max_width)
    return None


# ---------------------------------------------------------------------------------------------
# Graph model
# ---------------------------------------------------------------------------------------------
class Shape(Enum):
    RECT = "Rect"
    ROUND = "Round"
    DIAMOND = "Diamond"


@dataclass
class Node:
    label: str
    shape: Shape


class Head(Enum):
    NONE = "None"
    ARROW = "Arrow"
    CIRCLE = "Circle"
    CROSS = "Cross"
    TRIANGLE = "Triangle"
    DIAMOND_FILL = "DiamondFill"
    DIAMOND_OPEN = "DiamondOpen"


class LineKind(Enum):
    SOLID = "Solid"
    DOTTED = "Dotted"
    THICK = "Thick"


@dataclass
class Edge:
    from_: int
    to: int
    label: str | None
    head_to: Head
    head_from: Head
    line: LineKind


class Dir(Enum):
    DOWN = "Down"
    UP = "Up"
    RIGHT = "Right"
    LEFT = "Left"


@dataclass
class Group:
    id: str
    label: str
    parent: int | None


@dataclass
class Graph:
    nodes: list[Node] = field(default_factory=list)
    edges: list[Edge] = field(default_factory=list)
    index: dict[str, int] = field(default_factory=dict)
    groups: list[Group] = field(default_factory=list)
    node_group: list[int | None] = field(default_factory=list)
    cur_group: int | None = None
    over_cap: bool = False
    dir: Dir = Dir.DOWN

    def node_index(self, id: str, label: str | None, shape: Shape) -> int | None:
        i = self.index.get(id)
        if i is not None:
            if label is not None and i < len(self.nodes):
                node = self.nodes[i]
                node.label = label
                node.shape = shape
            return i
        if len(self.nodes) >= MAX_NODES:
            self.over_cap = True
            return None
        label = id if label is None else label
        self.index[id] = len(self.nodes)
        self.nodes.append(Node(label, shape))
        self.node_group.append(self.cur_group)
        return len(self.nodes) - 1

    def node_label(self, id: str, label: str) -> int | None:
        i = self.index.get(id)
        if i is not None:
            if i < len(self.nodes):
                self.nodes[i].label = label
            return i
        return self.node_index(id, label, Shape.ROUND)


def _dir_from_token(tok: str) -> Dir:
    up = rstr.to_ascii_uppercase(tok)
    if up == "LR":
        return Dir.RIGHT
    if up == "RL":
        return Dir.LEFT
    if up == "BT":
        return Dir.UP
    return Dir.DOWN


def _statements(src: str) -> list[str]:
    statements: list[str] = []
    for raw_line in join_quoted_lines(rstr.lines(src)):
        split_statements(raw_line, statements)
    return statements


#: A `"` right after one of these starts a quoted node or edge label (`A["…`, `A(("…`, `-->|"…`).
LABEL_OPENERS = ("[", "(", "{", "|", ">")


def _unclosed_label_quote(text: str) -> bool:
    """True when `text` ends inside a `"…"` that opened right after a label opener.

    Quotes are tracked like `split_statements` does (a `%%` comment outside quotes ends the scan).
    A stray quote elsewhere (`A[5" pipe]`) is not a label opener and never triggers a join.
    """
    in_quotes = False
    open_at = -1
    n = len(text)
    i = 0
    while i < n:
        c = text[i]
        if in_quotes:
            if c == '"':
                in_quotes = False
        elif c == '"':
            in_quotes = True
            open_at = i
        elif c == "%" and i + 1 < n and text[i + 1] == "%":
            break
        i += 1
    if not in_quotes:
        return False
    j = open_at - 1
    while j >= 0 and text[j] in (" ", "\t"):
        j -= 1
    return j >= 0 and text[j] in LABEL_OPENERS


def join_quoted_lines(lines: list[str]) -> list[str]:
    """Merge a quoted label that spans several source lines into one line.

    Extension over upstream (which splits strictly per line): Mermaid accepts a real newline
    inside `"…"`, and it survives here as a hard line break in the label. Only a quote opened
    right after `[`, `(`, `{`, `|` or `>` is joined, and only when a later line closes it;
    otherwise the lines are kept exactly as they are.
    """
    out: list[str] = []
    n = len(lines)
    i = 0
    while i < n:
        line = lines[i]
        if _unclosed_label_quote(line):
            joined = line
            j = i + 1
            while j < n:
                joined = joined + "\n" + lines[j]
                j += 1
                if not _unclosed_label_quote(joined):
                    out.append(joined)
                    i = j
                    break
            else:
                out.append(line)
                i += 1
            continue
        out.append(line)
        i += 1
    return out


def parse_graph(src: str) -> Graph | None:
    statements = _statements(src)

    if not statements:
        return None
    header = statements[0]
    header_tokens = rstr.split_whitespace(header)
    if not header_tokens:
        return None
    kind = rstr.to_ascii_lowercase(header_tokens[0])
    if kind != "graph" and kind != "flowchart":
        return None
    dir = _dir_from_token(header_tokens[1] if len(header_tokens) > 1 else "TB")

    graph = Graph(dir=dir)

    stack: list[int] = []
    for st in statements[1:]:
        first_word = rstr.first_word(st) or ""
        fw = rstr.to_ascii_lowercase(first_word)
        if fw == "subgraph":
            if len(graph.groups) >= MAX_GROUPS or len(stack) >= MAX_GROUP_DEPTH:
                return None
            rest = st[len("subgraph"):]
            id_, label = parse_subgraph_decl(rstr.trim(rest))
            graph.groups.append(Group(id_, label, stack[-1] if stack else None))
            stack.append(len(graph.groups) - 1)
            graph.cur_group = stack[-1] if stack else None
            continue
        if fw == "end":
            if stack:
                stack.pop()
            graph.cur_group = stack[-1] if stack else None
            continue
        if fw in ("classdef", "class", "style", "linkstyle", "click", "direction"):
            continue
        parse_statement(st, graph)
        if graph.over_cap:
            return None

    if not graph.nodes:
        return None
    return graph


def parse_subgraph_decl(rest: str) -> tuple[str, str]:
    q = rstr.strip_prefix(rest, '"')
    if q is not None:
        parts = rstr.split_once(q, '"')
        if parts is not None:
            label = parts[0]
            return label, decode_html_entities(_one_line(label))
    open_ = rest.find("[")
    if open_ >= 0:
        id_ = rstr.trim(rest[:open_])
        label = rstr.trim(rstr.trim_end_matches(rest[open_ + 1:], "]"))
        label = clean_label(label)
        if id_ != "" and label != "":
            return id_, label
    return rest, rest


def split_statements(line: str, out: list[str]) -> None:
    cur: list[str] = []
    in_quotes = False
    n = len(line)
    i = 0
    while i < n:
        c = line[i]
        i += 1
        if in_quotes:
            if c == '"':
                in_quotes = False
            cur.append(c)
        else:
            if c == '"':
                in_quotes = True
                cur.append(c)
            elif c == "%" and i < n and line[i] == "%":
                break
            elif c == ";":
                flush_statement(cur, out)
            else:
                cur.append(c)
    flush_statement(cur, out)


def flush_statement(cur: list[str], out: list[str]) -> None:
    trimmed = rstr.trim("".join(cur))
    if trimmed != "":
        out.append(trimmed)
    cur.clear()


def parse_statement(st: str, graph: Graph) -> None:
    chars = list(st)
    i = 0

    parsed = parse_node_group(chars, i, graph)
    if parsed is None:
        return
    prev, i = parsed

    while True:
        i = skip_spaces(chars, i)
        if i >= len(chars):
            break
        link = parse_link(chars, i)
        if link is None:
            break
        left, right, line, label, ni = link
        i = skip_spaces(chars, ni)
        parsed = parse_node_group(chars, i, graph)
        if parsed is None:
            break
        nxt, i = parsed
        for f in prev:
            for t in nxt:
                if len(graph.edges) >= MAX_EDGES:
                    graph.over_cap = True
                    return
                if left == Head.ARROW and right != Head.ARROW:
                    from_, to, head_to, head_from = t, f, Head.ARROW, right
                else:
                    from_, to, head_to, head_from = f, t, right, left
                graph.edges.append(Edge(from_, to, label, head_to, head_from, line))
        prev = nxt


def parse_node_group(chars: list[str], start: int, graph: Graph) -> tuple[list[int], int] | None:
    parsed = parse_node(chars, start, graph)
    if parsed is None:
        return None
    first, i = parsed
    group = [first]
    while True:
        j = skip_spaces(chars, i)
        if _at(chars, j) != "&":
            break
        parsed = parse_node(chars, j + 1, graph)
        if parsed is None:
            return None
        nxt, k = parsed
        group.append(nxt)
        i = k
    return group, i


def _at(chars: list[str], i: int) -> str | None:
    """`chars.get(i).copied()`."""
    if 0 <= i < len(chars):
        return chars[i]
    return None


def skip_spaces(chars: list[str], i: int) -> int:
    while i < len(chars) and (chars[i] == " " or chars[i] == "\t"):
        i += 1
    return i


def is_id_char(c: str) -> bool:
    return rstr.is_alphanumeric(c) or c == "_"


def parse_node(chars: list[str], start: int, graph: Graph) -> tuple[int, int] | None:
    i = skip_spaces(chars, start)
    id_start = i
    while i < len(chars) and is_id_char(chars[i]):
        i += 1
    if i == id_start:
        return None
    id_ = "".join(chars[id_start:i])

    c = _at(chars, i)
    if c == "[":
        if _at(chars, i + 1) == "[":
            shape, label, after = read_shape(chars, i + 2, "]]", Shape.RECT)
        elif _at(chars, i + 1) == "(":
            shape, label, after = read_shape(chars, i + 2, ")]", Shape.ROUND)
        else:
            shape, label, after = read_shape(chars, i + 1, "]", Shape.RECT)
    elif c == "(":
        if _at(chars, i + 1) == "(":
            shape, label, after = read_shape(chars, i + 2, "))", Shape.ROUND)
        elif _at(chars, i + 1) == "[":
            shape, label, after = read_shape(chars, i + 2, "])", Shape.ROUND)
        else:
            shape, label, after = read_shape(chars, i + 1, ")", Shape.ROUND)
    elif c == "{":
        if _at(chars, i + 1) == "{":
            shape, label, after = read_shape(chars, i + 2, "}}", Shape.DIAMOND)
        else:
            shape, label, after = read_shape(chars, i + 1, "}", Shape.DIAMOND)
    elif c == ">":
        shape, label, after = read_shape(chars, i + 1, "]", Shape.RECT)
    else:
        shape, label, after = None, None, i

    shape = Shape.RECT if shape is None else shape
    idx = graph.node_index(id_, label, shape)
    if idx is None:
        return None
    return idx, after


def read_shape(
    chars: list[str], start: int, closer: str, shape: Shape
) -> tuple[Shape | None, str | None, int]:
    closer_chars = list(closer)
    i = start
    text: list[str] = []
    j = start
    while _at(chars, j) in (" ", "\t"):
        j += 1
    quoted = _at(chars, j) == '"'
    in_quotes = False
    n = len(chars)
    while i < n:
        c = chars[i]
        if quoted and c == '"':
            in_quotes = not in_quotes
            text.append(c)
            i += 1
            continue
        if not in_quotes and chars[i:i + len(closer_chars)] == closer_chars:
            label = clean_label("".join(text), multiline=True)
            return shape, label, i + len(closer_chars)
        text.append(c)
        i += 1
    return shape, clean_label("".join(text), multiline=True), n


def _one_line(text: str) -> str:
    """Collapse line breaks (a literal `\\n` or a real newline) into spaces for single-line text."""
    return text.replace("\\n", " ").replace("\n", " ")


def clean_label(raw: str, multiline: bool = False) -> str:
    """Normalise a raw label: strip tags/quotes/markdown, decode entities.

    Extension over upstream: the two-character sequence `\\n`, as Mermaid users write inside
    quoted labels, is a line break, and so is a real newline (a quoted label spanning source
    lines) or a `<br>` tag. With ``multiline`` the result keeps them as ``"\\n"`` for
    `wrap_label` to honour as hard breaks (node labels); otherwise the text is drawn on one
    line, so they become spaces (edge labels, titles, `<br>` exactly as upstream).
    """
    raw = raw.replace("\\n", "\n")
    stripped = strip_html_tags(rstr.trim(raw), br="\n" if multiline else " ")
    trimmed = rstr.trim(stripped)
    unquoted = None
    t = rstr.strip_prefix(trimmed, '"')
    if t is not None:
        unquoted = rstr.strip_suffix(t, '"')
    if unquoted is None:
        t = rstr.strip_prefix(trimmed, "'")
        if t is not None:
            unquoted = rstr.strip_suffix(t, "'")
    if unquoted is None:
        unquoted = trimmed
    unquoted = rstr.trim(unquoted)
    md = None
    t = rstr.strip_prefix(unquoted, "`")
    if t is not None:
        md = rstr.strip_suffix(t, "`")
    if md is not None:
        text = strip_markdown(rstr.trim(md))
    else:
        text = unquoted
    # Decode after tag-stripping so `<b>` is removed as markup while `&lt;b&gt;` survives as a
    # literal `<b>`. One decode at the single return covers both paths.
    text = decode_html_entities(text)
    return text if multiline else text.replace("\n", " ")


ENTITY_LOOKAHEAD = 10


# Label text decodes HTML entities once: via clean_label for bracketed labels, or explicitly at
# each direct-push sink.
def decode_html_entities(s: str) -> str:
    if "&" not in s:
        return s
    chars = list(s)
    out: list[str] = []
    i = 0
    n = len(chars)
    while i < n:
        c = chars[i]
        if c != "&":
            out.append(c)
            i += 1
            continue
        # Scan window (includes the terminating `;`) so a stray `&` or over-long run stays literal.
        hi = min(i + 1 + ENTITY_LOOKAHEAD, n)
        semi = None
        for j in range(i + 1, hi):
            if chars[j] == ";":
                semi = j
                break
        decoded = None
        if semi is not None:
            body = "".join(chars[i + 1:semi])
            dc = decode_entity_body(body)
            if dc is not None:
                decoded = (dc, semi)
        if decoded is not None:
            # Resume past the `;`; the single pass never re-scans emitted text, so `&amp;lt;`
            # decodes to the literal `&lt;` rather than to `<`
            out.append(decoded[0])
            i = decoded[1] + 1
        else:
            out.append("&")
            i += 1
    return "".join(out)


def decode_entity_body(body: str) -> str | None:
    if body == "lt":
        return "<"
    if body == "gt":
        return ">"
    if body == "amp":
        return "&"
    if body == "quot":
        return '"'
    if body == "apos":
        return "'"
    num = rstr.strip_prefix(body, "#")
    if num is None:
        return None
    if num[:1] in ("x", "X"):
        code = rstr.parse_u32_hex(num[1:])
    else:
        code = rstr.parse_u32(num)
    if code is None:
        return None
    # Reject control chars: NUL collides with the CONT sentinel and ESC would inject ANSI into
    # scrollback.
    c = rstr.char_from_u32(code)
    if c is None or rstr.is_control(c):
        return None
    return c


def strip_markdown(s: str) -> str:
    no_code = "".join(c for c in s if c != "`")
    no_strong = no_code.replace("**", "").replace("__", "")
    chars = list(no_strong)
    out: list[str] = []
    n = len(chars)
    for i, c in enumerate(chars):
        if (c == "*" or c == "_") and not (
            i > 0
            and rstr.is_alphanumeric(chars[i - 1])
            and i + 1 < n
            and rstr.is_alphanumeric(chars[i + 1])
        ):
            continue
        out.append(c)
    return rstr.trim("".join(out))


HTML_FORMAT_TAGS = (
    "b", "strong", "i", "em", "u", "s", "strike", "del", "ins", "mark", "small", "big", "sub",
    "sup", "code", "kbd", "samp", "var", "tt", "span", "font", "q", "abbr", "cite", "pre",
)


def strip_html_tags(s: str, br: str = " ") -> str:
    chars = list(s)
    out: list[str] = []
    i = 0
    n = len(chars)
    while i < n:
        if chars[i] == "<":
            tag = html_tag_at(chars, i)
            if tag is not None:
                name, end = tag
                lower = rstr.to_ascii_lowercase(name)
                if lower == "br":
                    out.append(br)
                    i = end
                    continue
                if lower in HTML_FORMAT_TAGS:
                    i = end
                    continue
        out.append(chars[i])
        i += 1
    return "".join(out)


def html_tag_at(chars: list[str], start: int) -> tuple[str, int] | None:
    i = start + 1
    if _at(chars, i) == "/":
        i += 1
    name_start = i
    while i < len(chars) and rstr.is_ascii_alphanumeric(chars[i]):
        i += 1
    if i == name_start:
        return None
    name = "".join(chars[name_start:i])
    while i < len(chars) and chars[i] != ">":
        if chars[i] == "<":
            return None
        i += 1
    if _at(chars, i) == ">":
        return name, i + 1
    return None


def is_link_char(c: str) -> bool:
    return c in ("-", ".", "=", "<", ">")


def parse_link(chars: list[str], start: int) -> tuple[Head, Head, LineKind, str | None, int] | None:
    i = skip_spaces(chars, start)
    left = Head.NONE
    c = _at(chars, i)
    if c is not None and c in ("o", "x") and _at(chars, i + 1) in ("-", ".", "="):
        left = Head.CIRCLE if c == "o" else Head.CROSS
        i += 1
    op_start = i
    while i < len(chars) and chars[i] in ("-", ".", "=", "<", ">"):
        i += 1
    if i == op_start:
        return None
    op1 = "".join(chars[op_start:i])
    if left == Head.NONE and op1.startswith("<"):
        left = Head.ARROW
    line = line_kind(op1)
    right = Head.ARROW if ">" in op1 else Head.NONE
    if right == Head.NONE:
        th = trailing_head(chars, i)
        if th is not None:
            right, i = th

    if _at(chars, i) == "|":
        i += 1
        l_start = i
        while i < len(chars) and chars[i] != "|":
            i += 1
        label = clean_label("".join(chars[l_start:i]))
        if _at(chars, i) == "|":
            i += 1
        return left, right, line, non_empty(label), i

    if right == Head.NONE:
        text_start = skip_spaces(chars, i)
        j = text_start
        while j < len(chars) and not is_link_char(chars[j]):
            j += 1
        if j < len(chars) and j > text_start and chars[j] in ("-", ".", "=", ">"):
            text = "".join(chars[text_start:j])
            op2_start = j
            while j < len(chars) and is_link_char(chars[j]):
                j += 1
            op2 = "".join(chars[op2_start:j])
            if ">" in op2:
                right = Head.ARROW
            else:
                th = trailing_head(chars, j)
                if th is not None:
                    right, j = th
                else:
                    right = Head.NONE
            if line == LineKind.SOLID:
                line = line_kind(op2)
            return left, right, line, non_empty(clean_label(text)), j

    return left, right, line, None, i


def line_kind(op: str) -> LineKind:
    if "=" in op:
        return LineKind.THICK
    if "." in op:
        return LineKind.DOTTED
    return LineKind.SOLID


def trailing_head(chars: list[str], i: int) -> tuple[Head, int] | None:
    c = _at(chars, i)
    if c == "o":
        head = Head.CIRCLE
    elif c == "x":
        head = Head.CROSS
    else:
        return None
    nxt = _at(chars, i + 1)
    if nxt is None or nxt in (" ", "\t", "|", "&", ";"):
        return head, i + 1
    return None


def non_empty(s: str) -> str | None:
    return None if s == "" else s


# ---------------------------------------------------------------------------------------------
# stateDiagram
# ---------------------------------------------------------------------------------------------
def parse_state(src: str) -> Graph | None:
    statements = _statements(src)
    if not statements:
        return None
    header = statements[0]
    fw = rstr.first_word(header)
    if fw is None or not rstr.to_ascii_lowercase(fw).startswith("statediagram"):
        return None

    graph = Graph(dir=Dir.DOWN)

    in_note = False
    for st in statements[1:]:
        if in_note:
            if rstr.eq_ignore_ascii_case(st, "end note"):
                in_note = False
            continue
        first = rstr.first_word(st) or ""
        lf = rstr.to_ascii_lowercase(first)
        if lf == "direction":
            graph.dir = _dir_from_token(rstr.nth_word(st, 1) or "")
        elif lf == "note":
            if ":" not in st:
                in_note = True
        elif lf == "state":
            if not parse_state_decl(st, graph):
                return None
        elif lf in ("classdef", "class", "hide", "scale", "}", "--"):
            pass
        else:
            if "-->" in st:
                if not parse_transition(st, graph):
                    return None
            else:
                if not parse_state_desc(st, graph):
                    return None
        if graph.over_cap:
            return None

    if not graph.nodes:
        return None
    return graph


def parse_state_decl(st: str, graph: Graph) -> bool:
    rest = rstr.trim(rstr.trim_end_matches(rstr.trim(st[len("state"):]), "{"))
    if rest == "":
        return True
    q = rstr.strip_prefix(rest, '"')
    if q is not None:
        parts = rstr.split_once(q, '"')
        if parts is None:
            return False
        label, after = parts
        stripped = rstr.strip_prefix(rstr.trim(after), "as")
        id_ = rstr.trim(stripped) if stripped is not None else label
        if graph.node_label(id_, decode_html_entities(label)) is None:
            return False
        return True
    shape = Shape.ROUND
    id_ = rest
    stereotyped = False
    pos = rest.find("<<")
    if pos >= 0:
        stereo = rest[pos + 2:]
        while stereo.endswith(">>"):
            stereo = stereo[:-2]
        stereo = rstr.trim(stereo)
        if stereo == "choice":
            shape = Shape.DIAMOND
        id_ = rstr.trim(rest[:pos])
        stereotyped = True
    if id_ == "" or rstr.contains_whitespace(id_):
        return False
    label = id_ if stereotyped else None
    if graph.node_index(id_, label, shape) is None:
        return False
    return True


def parse_transition(st: str, graph: Graph) -> bool:
    rest = st
    prev: int | None = None
    while True:
        parts = rstr.split_once(rest, "-->")
        if parts is None:
            break
        lhs, rhs = parts
        from_id = rstr.trim(rstr.trim_end_matches(rstr.trim_end(lhs), "-"))
        if prev is not None:
            if from_id != "":
                return False
            from_ = prev
        else:
            if from_id == "":
                return False
            from_ = state_endpoint(graph, from_id, True)
            if from_ is None:
                return False
        nxt = rstr.split_once(rhs, "-->")
        if nxt is not None:
            to_part = nxt[0]
            tail = rhs[len(to_part):]
        else:
            to_part, tail = rhs, ""
        lab = rstr.split_once(to_part, ":")
        if lab is not None:
            to_part, l = lab
            label = non_empty(decode_html_entities(rstr.trim(l)))
        else:
            label = None
        to_id = rstr.trim(
            rstr.trim_end_matches(
                rstr.trim_end(rstr.trim_start_matches(rstr.trim_start(to_part), ">")), "-"
            )
        )
        if to_id == "":
            return False
        to = state_endpoint(graph, to_id, False)
        if to is None:
            return False
        if len(graph.edges) >= MAX_EDGES:
            graph.over_cap = True
            return True
        graph.edges.append(Edge(from_, to, label, Head.ARROW, Head.NONE, LineKind.SOLID))
        prev = to
        rest = tail
    return True


def state_endpoint(graph: Graph, id_: str, is_source: bool) -> int | None:
    if id_ == "[*]":
        key = "[*]start" if is_source else "[*]end"
        return graph.node_index(key, "●", Shape.ROUND)
    return graph.node_index(id_, None, Shape.ROUND)


def parse_state_desc(st: str, graph: Graph) -> bool:
    parts = rstr.split_once(st, ":")
    if parts is not None:
        id_ = rstr.trim(parts[0])
        desc = rstr.trim(parts[1])
        if id_ == "" or rstr.contains_whitespace(id_) or desc == "":
            return False
        if graph.node_label(id_, decode_html_entities(desc)) is None:
            return False
    elif not rstr.contains_whitespace(st):
        if graph.node_index(st, None, Shape.ROUND) is None:
            return False
    else:
        return False
    return True


# ---------------------------------------------------------------------------------------------
# classDiagram / erDiagram
# ---------------------------------------------------------------------------------------------
MAX_MEMBERS = 8
CLASS_OPS: tuple[tuple[str, Head, Head, LineKind], ...] = (
    ("<|--", Head.TRIANGLE, Head.NONE, LineKind.SOLID),
    ("--|>", Head.NONE, Head.TRIANGLE, LineKind.SOLID),
    ("<|..", Head.TRIANGLE, Head.NONE, LineKind.DOTTED),
    ("..|>", Head.NONE, Head.TRIANGLE, LineKind.DOTTED),
    ("*--", Head.DIAMOND_FILL, Head.NONE, LineKind.SOLID),
    ("--*", Head.NONE, Head.DIAMOND_FILL, LineKind.SOLID),
    ("o--", Head.DIAMOND_OPEN, Head.NONE, LineKind.SOLID),
    ("--o", Head.NONE, Head.DIAMOND_OPEN, LineKind.SOLID),
    ("<--", Head.ARROW, Head.NONE, LineKind.SOLID),
    ("-->", Head.NONE, Head.ARROW, LineKind.SOLID),
    ("<..", Head.ARROW, Head.NONE, LineKind.DOTTED),
    ("..>", Head.NONE, Head.ARROW, LineKind.DOTTED),
    ("--", Head.NONE, Head.NONE, LineKind.SOLID),
    ("..", Head.NONE, Head.NONE, LineKind.DOTTED),
)


@dataclass
class ClassInfo:
    annotation: str | None = None
    attrs: list[str] = field(default_factory=list)
    methods: list[str] = field(default_factory=list)


def parse_class(src: str) -> tuple[Graph, list[ClassInfo]] | None:
    statements = _statements(src)
    if not statements:
        return None
    header = statements[0]
    fw = rstr.first_word(header)
    if fw is None or not rstr.to_ascii_lowercase(fw).startswith("classdiagram"):
        return None

    graph = Graph(dir=Dir.DOWN)
    infos: list[ClassInfo] = []
    cur_class: int | None = None

    for st in statements[1:]:
        if cur_class is not None:
            if st == "}":
                cur_class = None
            elif cur_class < len(infos):
                push_member(infos[cur_class], st)
            continue
        first = rstr.first_word(st) or ""
        lf = rstr.to_ascii_lowercase(first)
        if lf == "direction":
            graph.dir = _dir_from_token(rstr.nth_word(st, 1) or "")
            continue
        if lf in (
            "note", "callback", "click", "link", "style", "cssclass", "classdef", "namespace", "}",
        ):
            continue
        if lf == "class":
            rest = rstr.trim(st[len("class"):])
            n = rstr.strip_suffix(rest, "{")
            if n is not None:
                name, open_ = rstr.trim(n), True
            else:
                name, open_ = rest, False
            if name == "" or rstr.contains_whitespace(name):
                return None
            idx = graph.node_index(name, None, Shape.RECT)
            if idx is None:
                return None
            sync_infos(graph, infos)
            if open_:
                cur_class = idx
            continue
        ann = rstr.strip_prefix(st, "<<")
        if ann is not None:
            parts = rstr.split_once(ann, ">>")
            if parts is None:
                return None
            ann, rest = parts
            name = rstr.trim(rest)
            if name == "" or rstr.contains_whitespace(name):
                return None
            idx = graph.node_index(name, None, Shape.RECT)
            if idx is None:
                return None
            sync_infos(graph, infos)
            if idx < len(infos):
                infos[idx].annotation = rstr.trim(ann)
            continue
        rel = parse_class_relation(st)
        if rel is not None:
            from_, to, head_from, head_to, line, label = rel
            f = graph.node_index(from_, None, Shape.RECT)
            if f is None:
                return None
            sync_infos(graph, infos)
            t = graph.node_index(to, None, Shape.RECT)
            if t is None:
                return None
            sync_infos(graph, infos)
            if len(graph.edges) >= MAX_EDGES:
                return None
            graph.edges.append(Edge(f, t, label, head_to, head_from, line))
            continue
        parts = rstr.split_once(st, ":")
        if parts is not None:
            id_ = rstr.trim(parts[0])
            member = rstr.trim(parts[1])
            if id_ == "" or rstr.contains_whitespace(id_) or member == "":
                return None
            idx = graph.node_index(id_, None, Shape.RECT)
            if idx is None:
                return None
            sync_infos(graph, infos)
            if idx < len(infos):
                push_member(infos[idx], member)
            continue
        return None

    if not graph.nodes:
        return None
    sync_infos(graph, infos)
    return graph, infos


def sync_infos(graph: Graph, infos: list[ClassInfo]) -> None:
    while len(infos) < len(graph.nodes):
        infos.append(ClassInfo())


def push_member(info: ClassInfo, raw: str) -> None:
    ann = rstr.strip_prefix(raw, "<<")
    if ann is not None:
        parts = rstr.split_once(ann, ">>")
        if parts is not None:
            info.annotation = rstr.trim(parts[0])
        return
    member = decode_html_entities(display_generics(rstr.trim(raw)))
    lst = info.methods if "(" in member else info.attrs
    if len(lst) < MAX_MEMBERS:
        lst.append(member)
    elif len(lst) == MAX_MEMBERS:
        lst.append("…")


def parse_class_relation(
    st: str,
) -> tuple[str, str, Head, Head, LineKind, str | None] | None:
    chars = list(st)
    found = None
    n = len(chars)
    for pos in range(n):
        for op, hf, ht, line in CLASS_OPS:
            if st.startswith(op, pos):
                if op.startswith("o") and pos > 0 and is_id_char(chars[pos - 1]):
                    continue
                if op.endswith("o"):
                    after = _at(chars, pos + len(op))
                    if after is not None and is_id_char(after):
                        continue
                found = (pos, op, hf, ht, line)
                break
        if found is not None:
            break
    if found is None:
        return None
    pos, op, head_from, head_to, line = found
    lhs = rstr.trim(st[:pos])
    rhs = rstr.trim(st[pos + len(op):])

    lhs, card_from = strip_cardinality_suffix(lhs)
    rhs, card_to = strip_cardinality_prefix(rhs)
    parts = rstr.split_once(rhs, ":")
    if parts is not None:
        to_id = rstr.trim(parts[0])
        rel_label = non_empty(decode_html_entities(rstr.trim(parts[1])))
    else:
        to_id, rel_label = rstr.trim(rhs), None
    if (
        lhs == ""
        or to_id == ""
        or rstr.contains_whitespace(lhs)
        or rstr.contains_whitespace(to_id)
    ):
        return None
    label = non_empty(
        " ".join(s for s in (card_from, rel_label if rel_label is not None else "", card_to) if s != "")
    )
    return lhs, to_id, head_from, head_to, line, label


def strip_cardinality_suffix(s: str) -> tuple[str, str]:
    t = rstr.trim_end(s)
    rest = rstr.strip_suffix(t, '"')
    if rest is not None:
        q = rest.rfind('"')
        if q >= 0:
            left = rest[:q]
            right = rest[q + 1:]
            return rstr.trim_end(left), right
    return t, ""


def strip_cardinality_prefix(s: str) -> tuple[str, str]:
    t = rstr.trim_start(s)
    rest = rstr.strip_prefix(t, '"')
    if rest is not None:
        q = rest.find('"')
        if q >= 0:
            right = rest[q + 1:]
            left = rest[:q]
            return rstr.trim_start(right), left
    return t, ""


def display_generics(s: str) -> str:
    out: list[str] = []
    open_ = False
    for c in s:
        if c == "~":
            out.append(">" if open_ else "<")
            open_ = not open_
        else:
            out.append(c)
    return "".join(out)


def parse_er(src: str) -> tuple[Graph, list[ClassInfo]] | None:
    statements = _statements(src)
    if not statements:
        return None
    header = statements[0]
    fw = rstr.first_word(header)
    if fw is None or not rstr.eq_ignore_ascii_case(fw, "erdiagram"):
        return None

    graph = Graph(dir=Dir.DOWN)
    infos: list[ClassInfo] = []
    cur_entity: int | None = None

    for st in statements[1:]:
        if cur_entity is not None:
            if st == "}":
                cur_entity = None
            elif cur_entity < len(infos):
                push_er_attribute(infos[cur_entity], st)
            continue
        split = split_er_relationship(st)
        if split is not None:
            rel, label_part = split
            tokens = rstr.split_whitespace(rel)
            if len(tokens) != 3:
                return None
            lhs, op, rhs = tokens
            parsed_op = parse_er_op(op)
            if parsed_op is None:
                return None
            card_l, card_r, line = parsed_op
            f = er_entity(graph, infos, lhs)
            if f is None:
                return None
            t = er_entity(graph, infos, rhs)
            if t is None:
                return None
            if len(graph.edges) >= MAX_EDGES:
                return None
            rel_label = clean_label(label_part) if label_part is not None else ""
            label = non_empty(" ".join(s for s in (card_l, rel_label, card_r) if s != ""))
            graph.edges.append(Edge(f, t, label, Head.NONE, Head.NONE, line))
            continue
        d = rstr.strip_suffix(st, "{")
        if d is not None:
            decl, open_ = rstr.trim(d), True
        else:
            decl, open_ = st, False
        if decl == "" or len(rstr.split_whitespace(decl)) != 1:
            return None
        idx = er_entity(graph, infos, decl)
        if idx is None:
            return None
        if open_:
            cur_entity = idx

    if not graph.nodes:
        return None
    sync_infos(graph, infos)
    return graph, infos


def er_entity(graph: Graph, infos: list[ClassInfo], token: str) -> int | None:
    open_ = token.find("[")
    if open_ >= 0:
        id_ = token[:open_]
        label = clean_label(rstr.trim_end_matches(token[open_ + 1:], "]"))
        if id_ == "" or label == "":
            return None
        idx = graph.node_label(id_, label)
        if idx is None:
            return None
    else:
        idx = graph.node_index(token, None, Shape.RECT)
        if idx is None:
            return None
    sync_infos(graph, infos)
    return idx


def split_er_relationship(st: str) -> tuple[str, str | None] | None:
    parts = rstr.split_once(st, ":")
    if parts is not None:
        rel, label = parts[0], rstr.trim(parts[1])
    else:
        rel, label = st, None
    has_op = any(parse_er_op(t) is not None for t in rstr.split_whitespace(rel))
    if has_op:
        return rel, label
    return None


def parse_er_op(tok: str) -> tuple[str, str, LineKind] | None:
    if not tok.isascii() or len(tok) != 6:
        return None
    mid = tok[2:4]
    if mid == "--":
        line = LineKind.SOLID
    elif mid == "..":
        line = LineKind.DOTTED
    else:
        return None
    l = er_card(tok[:2])
    if l is None:
        return None
    r = er_card(tok[4:6])
    if r is None:
        return None
    return l, r, line


def er_card(tok: str) -> str | None:
    if tok in ("|o", "o|"):
        return "0..1"
    if tok == "||":
        return "1"
    if tok in ("}o", "o{"):
        return "0..*"
    if tok in ("}|", "|{"):
        return "1..*"
    return None


def push_er_attribute(info: ClassInfo, raw: str) -> None:
    parts: list[str] = []
    for tok in rstr.split_whitespace(raw):
        if tok.startswith('"'):
            break
        parts.append(tok)
    if not parts:
        return
    line = decode_html_entities(" ".join(parts))
    if len(info.attrs) < MAX_MEMBERS:
        info.attrs.append(line)
    elif len(info.attrs) == MAX_MEMBERS:
        info.attrs.append("…")


def render_class(
    graph: Graph, infos: list[ClassInfo], styles: MermaidStyles, max_width: int | None
) -> MermaidArt:
    extras: list = []
    for node, info in zip(graph.nodes, infos):
        title: list[str] = []
        if info.annotation is not None:
            title.append(f"«{info.annotation}»")
        title.append(display_generics(node.label))
        extras.append(NodeExtra.compartments([title, list(info.attrs), list(info.methods)]))
    canvas = layout_canvas(graph, extras, max_width)
    if graph.dir == Dir.UP:
        canvas.flip_vertical()
    elif graph.dir == Dir.LEFT:
        canvas.flip_horizontal()
    styled_lines, plain_lines = canvas.to_lines(styles)
    return MermaidArt(styled_lines, plain_lines)


# ---------------------------------------------------------------------------------------------
# Canvas
# ---------------------------------------------------------------------------------------------
U = 1
D = 2
L = 4
R = 8


class Cls(Enum):
    EMPTY = "Empty"
    BORDER = "Border"
    TEXT = "Text"
    EDGE = "Edge"
    EDGE_LABEL = "EdgeLabel"


STY_DOT = 1
STY_THICK = 2
STY_SOLID = 4


class Canvas:
    __slots__ = ("w", "h", "ch", "cls", "mask", "style", "occupied", "cur_style")

    def __init__(self, w: int, h: int):
        n = w * h
        self.w = w
        self.h = h
        self.ch: list[str] = [" "] * n
        self.cls: list[Cls] = [Cls.EMPTY] * n
        self.mask: list[int] = [0] * n
        self.style: list[int] = [0] * n
        self.occupied: list[bool] = [False] * n
        self.cur_style = STY_SOLID

    def idx(self, x: int, y: int) -> int:
        return y * self.w + x

    def _oob(self, x: int, y: int) -> bool:
        # `x >= self.w || y >= self.h` on usize; a negative Python int would have wrapped to a
        # huge usize in Rust, so it is out of bounds too.
        return x < 0 or y < 0 or x >= self.w or y >= self.h

    def set(self, x: int, y: int, c: str, cls: Cls) -> None:
        if self._oob(x, y):
            return
        i = self.idx(x, y)
        self.ch[i] = c
        self.cls[i] = cls

    def add_bits(self, x: int, y: int, bits: int) -> None:
        if self._oob(x, y):
            return
        i = self.idx(x, y)
        if self.occupied[i]:
            return
        self.mask[i] |= bits
        self.style[i] |= self.cur_style
        if self.cls[i] != Cls.BORDER:
            self.cls[i] = Cls.EDGE

    def blit(self, sub: "Canvas", ox: int, oy: int) -> None:
        for sy in range(sub.h):
            for sx in range(sub.w):
                x, y = ox + sx, oy + sy
                if self._oob(x, y):
                    continue
                si = sub.idx(sx, sy)
                di = self.idx(x, y)
                self.ch[di] = sub.ch[si]
                self.cls[di] = sub.cls[si]
                self.style[di] = sub.style[si]
                self.occupied[di] = True

    def junction(self, x: int, y: int, bits: int) -> None:
        if self._oob(x, y):
            return
        i = self.idx(x, y)
        self.mask[i] |= bits
        if self.cls[i] != Cls.BORDER:
            self.cls[i] = Cls.EDGE

    def seg_v(self, x: int, y0: int, y1: int) -> None:
        a, b = min(y0, y1), max(y0, y1)
        for y in range(a, b + 1):
            bits = 0
            if y > a:
                bits |= U
            if y < b:
                bits |= D
            self.add_bits(x, y, bits)

    def seg_h(self, y: int, x0: int, x1: int) -> None:
        a, b = min(x0, x1), max(x0, x1)
        for x in range(a, b + 1):
            bits = 0
            if x > a:
                bits |= L
            if x < b:
                bits |= R
            self.add_bits(x, y, bits)

    def finalize_mask(self) -> None:
        ch = self.ch
        mask = self.mask
        style = self.style
        for i in range(len(ch)):
            m = mask[i]
            if m != 0 and ch[i] == " ":
                c = mask_char(m)
                s = style[i]
                if s == STY_DOT:
                    drawn = dotted_char(c)
                elif s == STY_THICK:
                    drawn = thick_char(c)
                else:
                    drawn = c
                ch[i] = drawn

    def flip_vertical(self) -> None:
        """Mirror top-to-bottom for `BT` (rows reorder; within-row text is unaffected, so labels
        stay readable). Box-drawing glyphs flip too."""
        for y in range(self.h // 2):
            y2 = self.h - 1 - y
            for x in range(self.w):
                i, j = self.idx(x, y), self.idx(x, y2)
                self.ch[i], self.ch[j] = self.ch[j], self.ch[i]
                self.cls[i], self.cls[j] = self.cls[j], self.cls[i]
        self.ch = [flip_glyph_v(c) for c in self.ch]

    def flip_horizontal(self) -> None:
        """Mirror left-to-right for `RL`. Mirroring reverses each row, so after flipping glyphs
        we reverse each text/label run back to reading order."""
        for y in range(self.h):
            for x in range(self.w // 2):
                x2 = self.w - 1 - x
                i, j = self.idx(x, y), self.idx(x2, y)
                self.ch[i], self.ch[j] = self.ch[j], self.ch[i]
                self.cls[i], self.cls[j] = self.cls[j], self.cls[i]
        self.ch = [flip_glyph_h(c) for c in self.ch]
        for y in range(self.h):
            x = 0
            while x < self.w:
                cls = self.cls[self.idx(x, y)]
                if cls == Cls.TEXT or cls == Cls.EDGE_LABEL:
                    start = self.idx(x, y)
                    while x < self.w and self.cls[self.idx(x, y)] == cls:
                        x += 1
                    end = self.idx(x, y)
                    self.ch[start:end] = self.ch[start:end][::-1]
                else:
                    x += 1

    def to_lines(self, styles: MermaidStyles) -> tuple[list[Line], list[str]]:
        styled: list[Line] = []
        plain: list[str] = []
        for y in range(self.h):
            last = self.w
            for x in range(self.w - 1, -1, -1):
                c = self.ch[self.idx(x, y)]
                if c != " " and c != CONT:
                    last = x + 1
                    break
            spans: list[Span] = []
            plain_row: list[str] = []
            run: list[str] = []
            run_cls = Cls.EMPTY
            for x in range(last):
                i = self.idx(x, y)
                c = self.ch[i]
                if c == CONT:
                    continue
                cls = self.cls[i]
                plain_row.append(c)
                if cls != run_cls and run:
                    spans.append(Span("".join(run), style_for(run_cls, styles)))
                    run = []
                run_cls = cls
                run.append(c)
            if run:
                spans.append(Span("".join(run), style_for(run_cls, styles)))
            styled.append(Line(spans))
            plain.append(rstr.trim_end("".join(plain_row)))
        return styled, plain


def style_for(cls: Cls, styles: MermaidStyles) -> Style:
    if cls == Cls.EMPTY:
        return Style()
    if cls == Cls.BORDER:
        return styles.border
    if cls == Cls.TEXT:
        return styles.node_text
    if cls == Cls.EDGE:
        return styles.edge
    return styles.edge_label


def mask_char(mask: int) -> str:
    if mask == 0:
        return " "
    if mask == U or mask == D or mask == U | D:
        return "│"
    if mask == L or mask == R or mask == L | R:
        return "─"
    if mask == D | R:
        return "┌"
    if mask == D | L:
        return "┐"
    if mask == U | R:
        return "└"
    if mask == U | L:
        return "┘"
    if mask == U | D | R:
        return "├"
    if mask == U | D | L:
        return "┤"
    if mask == D | L | R:
        return "┬"
    if mask == U | L | R:
        return "┴"
    return "┼"


_DOTTED = {"─": "╌", "│": "╎"}
_THICK = {
    "─": "━", "│": "┃", "┌": "┏", "┐": "┓", "└": "┗", "┘": "┛", "├": "┣", "┤": "┫", "┬": "┳",
    "┴": "┻", "┼": "╋",
}
_FLIP_V = {
    "┌": "└", "└": "┌", "┐": "┘", "┘": "┐", "┏": "┗", "┗": "┏", "┓": "┛", "┛": "┓", "╭": "╰",
    "╰": "╭", "╮": "╯", "╯": "╮", "┬": "┴", "┴": "┬", "┳": "┻", "┻": "┳", "▼": "▲", "▲": "▼",
    "▽": "△", "△": "▽",
}
_FLIP_H = {
    "┌": "┐", "┐": "┌", "└": "┘", "┘": "└", "┏": "┓", "┓": "┏", "┗": "┛", "┛": "┗", "╭": "╮",
    "╮": "╭", "╰": "╯", "╯": "╰", "├": "┤", "┤": "├", "┣": "┫", "┫": "┣", "▶": "◄", "◄": "▶",
    "▷": "◁", "◁": "▷",
}


def dotted_char(c: str) -> str:
    return _DOTTED.get(c, c)


def thick_char(c: str) -> str:
    return _THICK.get(c, c)


def flip_glyph_v(c: str) -> str:
    return _FLIP_V.get(c, c)


def flip_glyph_h(c: str) -> str:
    return _FLIP_H.get(c, c)


# ---------------------------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------------------------
@dataclass
class Placed:
    x: int = 0
    y: int = 0
    w: int = 0
    h: int = 0
    cx: int = 0
    cy: int = 0
    rank: int = 0


@dataclass
class NodeSizes:
    box_w: list[int]
    box_h: list[int]
    lay_w: list[int]
    lay_h: list[int]
    extra_h: list[int]
    self_label_w: list[int]


def layout_flowchart(graph: Graph, styles: MermaidStyles, max_width: int | None) -> MermaidArt:
    extras = [NodeExtra.plain() for _ in graph.nodes]
    canvas = layout_canvas(graph, extras, max_width)
    if graph.dir == Dir.UP:
        canvas.flip_vertical()
    elif graph.dir == Dir.LEFT:
        canvas.flip_horizontal()
    styled_lines, plain_lines = canvas.to_lines(styles)
    return MermaidArt(styled_lines, plain_lines)


class NodeExtra:
    """`enum NodeExtra { Plain, Frame(Canvas), Compartments(Vec<Vec<String>>) }`."""

    __slots__ = ("kind", "sub", "sections")
    PLAIN = "Plain"
    FRAME = "Frame"
    COMPARTMENTS = "Compartments"

    def __init__(self, kind: str, sub: Canvas | None = None, sections: list[list[str]] | None = None):
        self.kind = kind
        self.sub = sub
        self.sections = sections

    @classmethod
    def plain(cls) -> "NodeExtra":
        return cls(cls.PLAIN)

    @classmethod
    def frame(cls, sub: Canvas) -> "NodeExtra":
        return cls(cls.FRAME, sub=sub)

    @classmethod
    def compartments(cls, sections: list[list[str]]) -> "NodeExtra":
        return cls(cls.COMPARTMENTS, sections=sections)


def layout_canvas(graph: Graph, extras: list[NodeExtra], max_width: int | None) -> Canvas:
    n = len(graph.nodes)
    if n == 0:
        raise OversizeError(Oversize.CELLS)

    ranks = compute_ranks(graph)
    max_rank = max(ranks) if ranks else 0

    by_rank: list[list[int]] = [[] for _ in range(max_rank + 1)]
    for idx, r in enumerate(ranks):
        if r < len(by_rank):
            by_rank[r].append(idx)
    order_ranks(by_rank, graph.edges, ranks)

    opts = _opts()
    wrapped: list[list[str]] = [wrap_label(node.label, opts.wrap_width, opts.max_lines) for node in graph.nodes]
    box_w: list[int] = []
    for extra, node, wrap in zip(extras, graph.nodes, wrapped):
        if extra.kind == NodeExtra.FRAME:
            sub = extra.sub
            title_w = width(fit_label(node.label, opts.wrap_width))
            box_w.append(max(sub.w + 2, title_w + 4))
        elif extra.kind == NodeExtra.COMPARTMENTS:
            ws = [width(l) for section in extra.sections for l in section]
            box_w.append(max(max(ws) if ws else 1, 1) + 2 * PAD + 2)
        else:
            ws = [width(l) for l in wrap]
            box_w.append(max(max(ws) if ws else 1, 1) + 2 * PAD + 2)
    box_h: list[int] = []
    for extra, wrap in zip(extras, wrapped):
        if extra.kind == NodeExtra.FRAME:
            box_h.append(extra.sub.h + 2)
        elif extra.kind == NodeExtra.COMPARTMENTS:
            sections = extra.sections
            filled = sum(1 for s in sections if s)
            box_h.append(sum(len(s) for s in sections) + max(filled - 1, 0) + 2)
        else:
            box_h.append(len(wrap) + 2)

    extra_h = [0] * n
    self_label_w = [0] * n
    for e in graph.edges:
        if e.from_ == e.to:
            if e.from_ < n:
                extra_h[e.from_] = 2
            if e.label is not None and e.from_ < n:
                self_label_w[e.from_] = max(self_label_w[e.from_], min(width(e.label), _label_cap()))
    for i in range(min(len(box_w), len(extra_h))):
        if extra_h[i] > 0:
            box_w[i] = max(box_w[i], 7)
    lay_w = [w + (2 * (sl + 3) if sl > 0 else 0) for w, sl in zip(box_w, self_label_w)]
    lay_h = [h + e for h, e in zip(box_h, extra_h)]
    sizes = NodeSizes(box_w, box_h, lay_w, lay_h, extra_h, self_label_w)

    placed = [Placed() for _ in range(n)]

    # BT/RL reuse the TD/LR layout, then flip the finished canvas (so text stays readable) into
    # the bottom-up / right-to-left orientation
    vertical = graph.dir in (Dir.DOWN, Dir.UP)
    if vertical:
        plan = place_td(ranks, max_rank, by_rank, sizes, graph, placed)
    else:
        plan = place_lr(ranks, max_rank, by_rank, sizes, graph, placed)
    canvas_w, canvas_h = plan.canvas

    if max_width is not None and canvas_w > max_width:
        raise OversizeError(Oversize.WIDTH)
    if canvas_w * canvas_h > MAX_CANVAS_CELLS:
        raise OversizeError(Oversize.CELLS)

    canvas = Canvas(canvas_w, canvas_h)
    for idx, extra in enumerate(extras):
        if idx >= len(placed):
            continue
        p = placed[idx]
        if extra.kind == NodeExtra.FRAME:
            if idx >= len(graph.nodes):
                continue
            draw_frame(canvas, p, graph.nodes[idx].label, extra.sub)
        elif extra.kind == NodeExtra.COMPARTMENTS:
            draw_class_box(canvas, p, extra.sections)
        else:
            if idx >= len(wrapped) or idx >= len(graph.nodes):
                continue
            draw_box(canvas, p, wrapped[idx], graph.nodes[idx].shape)
    for i, edge in enumerate(graph.edges):
        if edge.line == LineKind.SOLID:
            canvas.cur_style = STY_SOLID
        elif edge.line == LineKind.DOTTED:
            canvas.cur_style = STY_DOT
        else:
            canvas.cur_style = STY_THICK
        if edge.from_ == edge.to:
            if edge.from_ < len(placed):
                route_self(canvas, placed[edge.from_], edge)
            continue
        if edge.from_ >= len(placed) or edge.to >= len(placed):
            continue
        frm = placed[edge.from_]
        to = placed[edge.to]
        adjacent = to.rank == frm.rank + 1
        if frm.rank >= len(plan.band_end):
            continue
        band = plan.band_end[frm.rank]
        if i >= len(plan.edge_bus) or i >= len(plan.edge_lane):
            continue
        edge_bus = plan.edge_bus[i]
        edge_lane = plan.edge_lane[i]
        bus = band + edge_bus
        lane = plan.lane_base + edge_lane
        if vertical and adjacent:
            route_forward(canvas, frm, to, edge, bus)
        elif vertical:
            route_back(canvas, frm, to, edge, lane)
        elif adjacent:
            route_forward_lr(canvas, frm, to, edge, bus)
        else:
            route_back_lr(canvas, frm, to, edge, lane)

    canvas.finalize_mask()
    return canvas


# `enum Item { Node(usize), Group(usize) }` as hashable tuples.
def _item_node(i: int) -> tuple[str, int]:
    return ("Node", i)


def _item_group(g: int) -> tuple[str, int]:
    return ("Group", g)


def render_grouped(graph: Graph, styles: MermaidStyles, max_width: int | None) -> MermaidArt:
    proxy: dict[int, int] = {}
    for gi, g in enumerate(graph.groups):
        ni = graph.index.get(g.id)
        if ni is not None:
            proxy[ni] = gi

    def group_chain(g: int | None) -> list[int]:
        chain: list[int] = []
        cur = g
        while cur is not None:
            chain.append(cur)
            cur = graph.groups[cur].parent if cur < len(graph.groups) else None
        chain.reverse()
        return chain

    def endpoint(nd: int) -> tuple[tuple[str, int], list[int]]:
        gi = proxy.get(nd)
        if gi is not None:
            parent = graph.groups[gi].parent if gi < len(graph.groups) else None
            return _item_group(gi), group_chain(parent)
        ng = graph.node_group[nd] if nd < len(graph.node_group) else None
        return _item_node(nd), group_chain(ng)

    scope_edges: dict[int | None, list[tuple[tuple[str, int], tuple[str, int], int]]] = {}
    referenced = [False] * len(graph.groups)
    for ei, e in enumerate(graph.edges):
        item_f, chain_f = endpoint(e.from_)
        item_t, chain_t = endpoint(e.to)
        k = 0
        for a, b in zip(chain_f, chain_t):
            if a != b:
                break
            k += 1
        scope = chain_f[k - 1] if k >= 1 and k - 1 < len(chain_f) else None
        f = _item_group(chain_f[k]) if k < len(chain_f) else item_f
        t = _item_group(chain_t[k]) if k < len(chain_t) else item_t
        if f[0] == "Group" and f[1] < len(referenced):
            referenced[f[1]] = True
        if t[0] == "Group" and t[1] < len(referenced):
            referenced[t[1]] = True
        scope_edges.setdefault(scope, []).append((f, t, ei))

    direct_nodes: dict[int | None, list[int]] = {}
    for ni, g in enumerate(graph.node_group):
        if ni not in proxy:
            direct_nodes.setdefault(g, []).append(ni)
    keep = [False] * len(graph.groups)
    for gi in range(len(graph.groups) - 1, -1, -1):
        has_nodes = bool(direct_nodes.get(gi))
        has_children = any(
            graph.groups[c].parent == gi and keep[c] for c in range(len(graph.groups))
        )
        keep[gi] = has_nodes or has_children or referenced[gi]

    canvas = build_scope(graph, None, scope_edges, direct_nodes, keep, max_width)
    if graph.dir == Dir.UP:
        canvas.flip_vertical()
    elif graph.dir == Dir.LEFT:
        canvas.flip_horizontal()
    styled_lines, plain_lines = canvas.to_lines(styles)
    return MermaidArt(styled_lines, plain_lines)


def build_scope(
    graph: Graph,
    scope: int | None,
    scope_edges: dict,
    direct_nodes: dict,
    keep: list[bool],
    max_width: int | None,
) -> Canvas:
    items: list[tuple[str, int]] = []
    nodes_here = direct_nodes.get(scope)
    if nodes_here is not None:
        items.extend(_item_node(nd) for nd in nodes_here)
    child_groups = [
        gi
        for gi in range(len(graph.groups))
        if graph.groups[gi].parent == scope and gi < len(keep) and keep[gi]
    ]
    items.extend(_item_group(gi) for gi in child_groups)

    if not items:
        return Canvas(1, 1)

    index_of: dict[tuple[str, int], int] = {}
    nodes: list[Node] = []
    extras: list[NodeExtra] = []
    for item in items:
        index_of[item] = len(nodes)
        if item[0] == "Node":
            ni = item[1]
            if ni >= len(graph.nodes):
                continue
            node = graph.nodes[ni]
            nodes.append(Node(node.label, node.shape))
            extras.append(NodeExtra.plain())
        else:
            gi = item[1]
            sub = build_scope(graph, gi, scope_edges, direct_nodes, keep, None)
            if gi >= len(graph.groups):
                continue
            group = graph.groups[gi]
            nodes.append(Node(group.label, Shape.RECT))
            extras.append(NodeExtra.frame(sub))

    edges: list[Edge] = []
    lst = scope_edges.get(scope)
    if lst is not None:
        for f, t, ei in lst:
            fi = index_of.get(f)
            ti = index_of.get(t)
            if fi is None or ti is None:
                continue
            if ei >= len(graph.edges):
                continue
            e = graph.edges[ei]
            edges.append(Edge(fi, ti, e.label, e.head_to, e.head_from, e.line))

    synth = Graph(nodes=nodes, edges=edges, dir=graph.dir)
    return layout_canvas(synth, extras, max_width)


def draw_class_box(canvas: Canvas, p: Placed, sections: list[list[str]]) -> None:
    draw_box(canvas, p, [], Shape.RECT)
    inner = max(max(p.w - (2 * PAD + 2), 0), 1)
    row = p.y + 1
    first = True
    for si, section in enumerate(sections):
        if not section:
            continue
        if not first:
            canvas.set(p.x, row, "├", Cls.BORDER)
            for x in range(p.x + 1, p.x + p.w - 1):
                canvas.set(x, row, "─", Cls.BORDER)
            canvas.set(p.x + p.w - 1, row, "┤", Cls.BORDER)
            row += 1
        first = False
        for line in section:
            text = fit_label(line, inner)
            if si == 0:
                tx = p.x + 1 + PAD + max(inner - width(text), 0) // 2
            else:
                tx = p.x + 1 + PAD
            draw_seq_text(canvas, text, tx, row, Cls.TEXT)
            row += 1


def draw_frame(canvas: Canvas, p: Placed, title: str, sub: Canvas) -> None:
    draw_box(canvas, p, [], Shape.RECT)
    t = fit_label(title, max(p.w - 4, 0))
    draw_seq_text(canvas, f" {t} ", p.x + 1, p.y, Cls.TEXT)
    ox = p.x + 1 + (p.w - 2 - sub.w) // 2
    oy = p.y + 1 + (p.h - 2 - sub.h) // 2
    canvas.blit(sub, ox, oy)


def bus_spans_td(
    graph: Graph, ranks: list[int], centers: list[int], r: int, exact: bool
) -> list[tuple[int, int, int, int, int]]:
    out: list[tuple[int, int, int, int, int]] = []
    for i, e in enumerate(graph.edges):
        if (
            e.from_ >= len(centers)
            or e.to >= len(centers)
            or e.from_ >= len(ranks)
            or e.to >= len(ranks)
        ):
            continue
        cf = centers[e.from_]
        ct = centers[e.to]
        rf = ranks[e.from_]
        rt = ranks[e.to]
        jogs = (cf != ct) if exact else (abs(cf - ct) > 1)
        if e.from_ != e.to and rf == r and rt == r + 1 and jogs:
            out.append((min(cf, ct), max(cf, ct), e.from_, e.to, i))
    return out


def lane_spans(
    graph: Graph, ranks: list[int], placed: list[Placed], vertical: bool
) -> list[tuple[int, int, int, int, int]]:
    out: list[tuple[int, int, int, int, int]] = []
    for i, e in enumerate(graph.edges):
        if e.from_ == e.to:
            continue
        if e.to >= len(ranks) or e.from_ >= len(ranks):
            continue
        if ranks[e.to] == ranks[e.from_] + 1:
            continue
        if e.from_ >= len(placed) or e.to >= len(placed):
            continue
        pf, pt = placed[e.from_], placed[e.to]
        if vertical:
            a, b = min(pf.cy, pt.cy), max(pf.cy, pt.cy)
        else:
            a, b = min(pf.cx, pt.cx), max(pf.cx, pt.cx)
        out.append((a, b, e.from_, e.to, i))
    return out


@dataclass
class RoutePlan:
    canvas: tuple[int, int]
    band_end: list[int]
    edge_bus: list[int]
    lane_base: int
    edge_lane: list[int]


def place_td(
    ranks: list[int],
    max_rank: int,
    by_rank: list[list[int]],
    sizes: NodeSizes,
    graph: Graph,
    placed: list[Placed],
) -> RoutePlan:
    centers = assign_positions(by_rank, sizes.lay_w, GAP_X, graph.edges, ranks)

    edge_bus = [0] * len(graph.edges)
    bus_tracks = [0] * (max_rank + 1)
    for r in range(max_rank):
        spans = bus_spans_td(graph, ranks, centers, r, False)
        if not spans:
            continue
        assigned, count = assign_tracks(spans)
        for idx, slot in assigned:
            if idx < len(edge_bus):
                edge_bus[idx] = slot
        bus_tracks[r] = count

    rank_h: list[int] = []
    for row in by_rank:
        hs = [sizes.box_h[i] + sizes.extra_h[i] for i in row if i < len(sizes.box_h) and i < len(sizes.extra_h)]
        rank_h.append(max(hs) if hs else 3)
    rank_y = [0] * (max_rank + 1)
    for r in range(1, max_rank + 1):
        prev = r - 1
        if prev >= len(bus_tracks) or prev >= len(rank_y) or prev >= len(rank_h):
            continue
        prev_bus = bus_tracks[prev]
        prev_y = rank_y[prev]
        prev_h = rank_h[prev]
        gap = max(GAP_Y, prev_bus + 1)
        rank_y[r] = prev_y + prev_h + gap
    canvas_h = (rank_y[max_rank] if max_rank < len(rank_y) else 0) + (
        rank_h[max_rank] if max_rank < len(rank_h) else 0
    )
    band_end = [rank_y[r] + rank_h[r] for r in range(max_rank + 1) if r < len(rank_y) and r < len(rank_h)]

    diagram_w = 1
    for r, row in enumerate(by_rank):
        for idx in row:
            if idx >= len(sizes.box_w) or idx >= len(sizes.box_h) or idx >= len(centers):
                continue
            w = sizes.box_w[idx]
            h = sizes.box_h[idx]
            cx = centers[idx]
            extra = sizes.extra_h[idx] if idx < len(sizes.extra_h) else 0
            if r >= len(rank_y) or r >= len(rank_h):
                continue
            ry = rank_y[r]
            rh = rank_h[r]
            x = max(cx - w // 2, 0)
            y = ry + (rh - h - extra) // 2
            if idx < len(placed):
                placed[idx] = Placed(x, y, w, h, cx, y + h // 2, r)
            diagram_w = max(diagram_w, x + w)
            if extra > 0 and idx < len(sizes.self_label_w):
                sl = sizes.self_label_w[idx]
                if sl > 0:
                    diagram_w = max(diagram_w, x + w + 2 + sl)

    content_w = diagram_w
    for e in graph.edges:
        if e.from_ == e.to:
            continue
        if e.label is not None:
            lw = min(width(e.label), _label_cap())
            adjacent = (
                e.to < len(ranks) and e.from_ < len(ranks) and ranks[e.to] == ranks[e.from_] + 1
            )
            if adjacent:
                if e.to < len(placed):
                    p = placed[e.to]
                    # polished layout leaves one blank column between the arrowhead and the label
                    content_w = max(content_w, p.cx + (2 if UPSTREAM_LAYOUT else 3) + lw)
            else:
                content_w = max(content_w, diagram_w + lw + 1)

    edge_lane = [0] * len(graph.edges)
    lanes = lane_spans(graph, ranks, placed, True)
    if not lanes:
        canvas_w, lane_base = content_w, 0
    else:
        assigned, count = assign_tracks(lanes)
        for idx, slot in assigned:
            if idx < len(edge_lane):
                edge_lane[idx] = slot
        canvas_w, lane_base = content_w + 1 + count, content_w + 1

    return RoutePlan((canvas_w, canvas_h), band_end, edge_bus, lane_base, edge_lane)


def place_lr(
    ranks: list[int],
    max_rank: int,
    by_rank: list[list[int]],
    sizes: NodeSizes,
    graph: Graph,
    placed: list[Placed],
) -> RoutePlan:
    col_w: list[int] = []
    for row in by_rank:
        ws = [sizes.box_w[i] for i in row if i < len(sizes.box_w)]
        col_w.append(max(ws) if ws else 0)

    label_ws: list[int] = []
    for e in graph.edges:
        adj = e.to < len(ranks) and e.from_ < len(ranks) and ranks[e.to] == ranks[e.from_] + 1
        if (e.from_ == e.to or adj) and e.label is not None:
            label_ws.append(min(width(e.label), _label_cap()))
    max_label = max(label_ws) if label_ws else 0
    base_gap = max(GAP_X + 1, max_label + 3)

    centers = assign_positions(by_rank, sizes.lay_h, 1, graph.edges, ranks)

    edge_bus = [0] * len(graph.edges)
    bus_tracks = [0] * (max_rank + 1)
    for r in range(max_rank):
        spans = bus_spans_td(graph, ranks, centers, r, True)
        if not spans:
            continue
        assigned, count = assign_tracks(spans)
        for idx, slot in assigned:
            if idx < len(edge_bus):
                edge_bus[idx] = slot
        bus_tracks[r] = count

    rank_x = [0] * (max_rank + 1)
    for r in range(1, max_rank + 1):
        prev = r - 1
        if prev >= len(bus_tracks) or prev >= len(rank_x) or prev >= len(col_w):
            continue
        prev_bus = bus_tracks[prev]
        prev_x = rank_x[prev]
        prev_w = col_w[prev]
        gap = max(base_gap, prev_bus + 1)
        rank_x[r] = prev_x + prev_w + gap
    extra_rights: list[int] = []
    if max_rank < len(by_rank):
        for i in by_rank[max_rank]:
            eh = sizes.extra_h[i] if i < len(sizes.extra_h) else 0
            sl = sizes.self_label_w[i] if i < len(sizes.self_label_w) else 0
            if eh > 0 and sl > 0 and i < len(sizes.self_label_w):
                extra_rights.append(2 + sizes.self_label_w[i])
    extra_right = max(extra_rights) if extra_rights else 0
    canvas_w = (
        (rank_x[max_rank] if max_rank < len(rank_x) else 0)
        + (col_w[max_rank] if max_rank < len(col_w) else 0)
        + extra_right
    )
    band_end = [rank_x[r] + col_w[r] for r in range(max_rank + 1) if r < len(rank_x) and r < len(col_w)]

    diagram_h = 1
    for r, row in enumerate(by_rank):
        if r >= len(rank_x):
            continue
        x = rank_x[r]
        for idx in row:
            if idx >= len(sizes.box_w) or idx >= len(sizes.box_h) or idx >= len(centers):
                continue
            w = sizes.box_w[idx]
            h = sizes.box_h[idx]
            cy = centers[idx]
            extra = sizes.extra_h[idx] if idx < len(sizes.extra_h) else 0
            y = max(cy - (h + extra) // 2, 0)
            if idx < len(placed):
                placed[idx] = Placed(x, y, w, h, x + w // 2, y + h // 2, r)
            diagram_h = max(diagram_h, y + h + extra)

    edge_lane = [0] * len(graph.edges)
    lanes = lane_spans(graph, ranks, placed, False)
    if not lanes:
        canvas_h, lane_base = diagram_h, 0
    else:
        assigned, count = assign_tracks(lanes)
        for idx, slot in assigned:
            if idx < len(edge_lane):
                edge_lane[idx] = slot
        canvas_h, lane_base = diagram_h + 1 + count, diagram_h + 1

    return RoutePlan((canvas_w, canvas_h), band_end, edge_bus, lane_base, edge_lane)


def assign_tracks(spans: list[tuple[int, int, int, int, int]]) -> tuple[list[tuple[int, int]], int]:
    sorted_spans = sorted(spans)
    tracks: list[list[tuple[int, int, int, int]]] = []
    out: list[tuple[int, int]] = []
    for s, e, f, t, idx in sorted_spans:
        slot = None
        for ti, members in enumerate(tracks):
            if all(e2 + 2 <= s or e + 2 <= s2 or f2 == f or t2 == t for s2, e2, f2, t2 in members):
                slot = ti
                break
        if slot is None:
            tracks.append([])
            slot = len(tracks) - 1
        tracks[slot].append((s, e, f, t))
        out.append((idx, slot))
    return out, len(tracks)


def order_ranks(by_rank: list[list[int]], edges: list[Edge], ranks: list[int]) -> None:
    """Reorder nodes within each rank to minimize edge crossings (Sugiyama-style barycenter
    sweeps). Alternate down/up passes sort each rank by the mean position of its forward
    neighbours. The pass keeps the ordering with the fewest crossings between adjacent ranks."""
    n = len(ranks)
    if len(by_rank) < 2 or n < 3:
        return
    parents: list[list[int]] = [[] for _ in range(n)]
    children: list[list[int]] = [[] for _ in range(n)]
    for e in edges:
        if e.from_ != e.to and e.to < n and e.from_ < n and ranks[e.to] > ranks[e.from_]:
            parents[e.to].append(e.from_)
            children[e.from_].append(e.to)

    pos = [0] * n

    def set_pos(rows: list[list[int]]) -> None:
        for row in rows:
            for i, v in enumerate(row):
                if v < n:
                    pos[v] = i

    set_pos(by_rank)

    best = [list(row) for row in by_rank]
    best_crossings = count_crossings(edges, ranks, pos)
    if best_crossings == 0:
        return

    for it in range(8):
        if it % 2 == 0:
            for row in by_rank[1:]:
                sort_by_barycenter(row, parents, pos)
                for i, v in enumerate(row):
                    if v < n:
                        pos[v] = i
        else:
            prefix = by_rank[: len(by_rank) - 1]
            for row in reversed(prefix):
                sort_by_barycenter(row, children, pos)
                for i, v in enumerate(row):
                    if v < n:
                        pos[v] = i
        crossings = count_crossings(edges, ranks, pos)
        if crossings < best_crossings:
            best_crossings = crossings
            best = [list(row) for row in by_rank]
        if best_crossings == 0:
            break

    for row, b in zip(by_rank, best):
        row[:] = b


def sort_by_barycenter(row: list[int], neigh: list[list[int]], pos: list[int]) -> None:
    keyed: list[tuple[float, int]] = []
    for v in row:
        ns = neigh[v] if v < len(neigh) else None
        if ns:
            # Explicit left-to-right f64 accumulation: Python's `sum()` uses compensated
            # summation for floats, which would not match Rust's `Iterator::sum`.
            acc = 0.0
            for u in ns:
                if u < len(pos):
                    acc += float(pos[u])
            key = acc / float(len(ns))
        else:
            key = float(pos[v] if v < len(pos) else 0)
        keyed.append((key, v))
    keyed.sort(key=lambda kv: kv[0])
    for i, (_, v) in enumerate(keyed):
        row[i] = v


def count_crossings(edges: list[Edge], ranks: list[int], pos: list[int]) -> int:
    adjacent: list[tuple[int, int, int]] = []
    for e in edges:
        if e.from_ == e.to:
            continue
        if e.to >= len(ranks) or e.from_ >= len(ranks) or ranks[e.to] != ranks[e.from_] + 1:
            continue
        if e.from_ >= len(pos) or e.to >= len(pos):
            continue
        adjacent.append((ranks[e.from_], pos[e.from_], pos[e.to]))
    crossings = 0
    for i, a in enumerate(adjacent):
        for b in adjacent[i + 1:]:
            if a[0] == b[0] and ((a[1] < b[1] and a[2] > b[2]) or (a[1] > b[1] and a[2] < b[2])):
                crossings += 1
    return crossings


def assign_positions(
    by_rank: list[list[int]], size: list[int], sep: int, edges: list[Edge], ranks: list[int]
) -> list[int]:
    """Assign a center coordinate (along the cross-axis) to every node so nodes line up under
    their neighbours. Iterative barycenter relaxation straightens chains and centers branches.
    Each node drifts toward the average of its forward neighbours while ranks keep order and a
    minimum `sep` between boxes."""
    n = len(size)
    parents: list[list[int]] = [[] for _ in range(n)]
    children: list[list[int]] = [[] for _ in range(n)]
    for e in edges:
        if (
            e.from_ != e.to
            and e.to < len(ranks)
            and e.from_ < len(ranks)
            and ranks[e.to] > ranks[e.from_]
        ):
            if e.to < n:
                parents[e.to].append(e.from_)
            if e.from_ < n:
                children[e.from_].append(e.to)

    pos = [0.0] * n
    for row in by_rank:
        x = 0.0
        for v in row:
            half = float(size[v] if v < n else 0) / 2.0
            x += half
            if v < n:
                pos[v] = x
            x += half + float(sep)

    for it in range(10):
        if it % 2 == 0:
            for row in by_rank:
                relax_rank(row, parents, pos, size, sep)
        else:
            for row in reversed(by_rank):
                relax_rank(row, children, pos, size, sep)

    min_left = float("inf")
    for v in range(n):
        min_left = min(min_left, pos[v] - float(size[v]) / 2.0)
    if not math.isfinite(min_left):
        min_left = 0.0
    return [rstr.f64_to_usize(max(rstr.rust_round(pos[v] - min_left), 0.0)) for v in range(n)]


def relax_rank(
    nodes: list[int], neigh: list[list[int]], pos: list[float], size: list[int], sep: int
) -> None:
    n = len(nodes)
    if n == 0:
        return
    desired: list[float] = []
    for v in nodes:
        ns = neigh[v] if v < len(neigh) else None
        if ns:
            acc = 0.0
            for u in ns:
                if u < len(pos):
                    acc += pos[u]
            desired.append(acc / float(len(ns)))
        else:
            desired.append(pos[v] if v < len(pos) else 0.0)

    def half(i: int) -> float:
        if i < n and nodes[i] < len(size):
            return float(size[nodes[i]]) / 2.0
        return 0.0

    fsep = float(sep)
    left = [0.0] * n
    right = [0.0] * n
    for i in range(n):
        d = desired[i]
        if i == 0:
            val = d
        else:
            prev = left[i - 1]
            val = _f64_max(d, prev + half(i - 1) + fsep + half(i))
        left[i] = val
    for i in range(n - 1, -1, -1):
        d = desired[i]
        if i == n - 1:
            val = d
        else:
            nxt = right[i + 1]
            val = _f64_min(d, nxt - half(i + 1) - fsep - half(i))
        right[i] = val
    for i in range(n):
        ni = nodes[i]
        if ni < len(pos):
            pos[ni] = (left[i] + right[i]) / 2.0
    for i in range(1, n):
        prev_n = nodes[i - 1]
        cur_n = nodes[i]
        if prev_n >= len(pos) or cur_n >= len(pos):
            continue
        prev_p = pos[prev_n]
        min_p = prev_p + half(i - 1) + fsep + half(i)
        if pos[cur_n] < min_p:
            pos[cur_n] = min_p


def _f64_max(a: float, b: float) -> float:
    """`f64::max` (NaN-ignoring)."""
    if a != a:
        return b
    if b != b:
        return a
    return a if a >= b else b


def _f64_min(a: float, b: float) -> float:
    if a != a:
        return b
    if b != b:
        return a
    return a if a <= b else b


# ---------------------------------------------------------------------------------------------
# Labels, boxes and edge routing
# ---------------------------------------------------------------------------------------------
def _rfind_break(chunk: str) -> int:
    """`chunk.rfind(LABEL_BREAK_CHARS)`: index of the last break char, or -1."""
    for i in range(len(chunk) - 1, -1, -1):
        if chunk[i] in LABEL_BREAK_CHARS:
            return i
    return -1


def wrap_label(label: str, width_: int, max_lines: int) -> list[str]:
    """Word-wrap a node label to ``width_`` columns, at most ``max_lines`` lines per paragraph.

    Extension over upstream: a ``"\\n"`` in the label is a hard break (see `clean_label`). Each
    segment wraps on its own, so an author who broke the text by hand gets exactly those lines,
    while a segment that is still too long wraps and truncates like an unbroken label would.
    """
    if "\n" in label:
        lines: list[str] = []
        for segment in label.split("\n"):
            lines.extend(_wrap_segment(segment, width_, max_lines))
        return lines
    return _wrap_segment(label, width_, max_lines)


def _wrap_segment(label: str, width_: int, max_lines: int) -> list[str]:
    width_ = max(width_, 1)

    def char_w(c: str) -> int:
        return max(char_width(c), 1)

    lines: list[str] = []
    cur = ""
    cur_w = 0
    for word in rstr.split_whitespace(label):
        ww = width(word)
        if ww > width_:
            if cur != "":
                lines.append(cur)
                cur = ""
            chunk = ""
            chunk_w = 0
            for ch in word:
                cw = char_w(ch)
                if chunk_w + cw > width_ and chunk != "":
                    # Prefer breaking after the last identifier boundary so a long token is not
                    # sliced mid-segment; fall back to a per-char break
                    p = _rfind_break(chunk)
                    if p >= 0:
                        carry = chunk[p + 1:]
                        chunk = chunk[: p + 1]
                    else:
                        carry = ""
                    lines.append(chunk)
                    chunk_w = 0
                    for cc in carry:
                        chunk_w += char_w(cc)
                    chunk = carry
                chunk += ch
                chunk_w += cw
            cur = chunk
            cur_w = chunk_w
        elif cur == "":
            cur += word
            cur_w = ww
        elif cur_w + 1 + ww <= width_:
            cur += " "
            cur += word
            cur_w += 1 + ww
        else:
            lines.append(cur)
            cur = word
            cur_w = ww
    if cur != "":
        lines.append(cur)
    if not lines:
        lines.append("")
    if len(lines) > max_lines:
        del lines[max_lines:]
        target = max(max(width_ - 1, 0), 1)
        last = lines[-1]
        s = ""
        sw = 0
        for ch in last:
            cw = char_w(ch)
            if sw + cw > target:
                break
            s += ch
            sw += cw
        s += "…"
        lines[-1] = s
    return lines


def fit_label(label: str, inner: int) -> str:
    if "\n" in label:
        label = label.replace("\n", " ")
    if width(label) <= inner:
        return label
    out = ""
    used = 0
    for c in label:
        cw = char_width(c)
        if used + cw + 1 > inner:
            break
        out += c
        used += cw
    out += "…"
    return out


def draw_box(canvas: Canvas, p: Placed, lines: list[str], shape: Shape) -> None:
    x, y, w, h = p.x, p.y, p.w, p.h
    right = x + w - 1
    bottom = y + h - 1

    if shape == Shape.ROUND or shape == Shape.DIAMOND:
        tl, tr, bl, br = "╭", "╮", "╰", "╯"
    else:
        tl, tr, bl, br = "┌", "┐", "└", "┘"
    canvas.set(x, y, tl, Cls.BORDER)
    canvas.set(right, y, tr, Cls.BORDER)
    canvas.set(x, bottom, bl, Cls.BORDER)
    canvas.set(right, bottom, br, Cls.BORDER)

    for cx in range(x + 1, right):
        canvas.add_bits(cx, y, L | R)
        canvas.add_bits(cx, bottom, L | R)
    for cy in range(y + 1, bottom):
        canvas.add_bits(x, cy, U | D)
        canvas.add_bits(right, cy, U | D)

    for cy in range(y, bottom + 1):
        for cx in range(x, right + 1):
            if 0 <= cx < canvas.w and 0 <= cy < canvas.h:
                canvas.occupied[canvas.idx(cx, cy)] = True

    inner = max(max(w - (2 * PAD + 2), 0), 1)
    for li, line in enumerate(lines):
        row = y + 1 + li
        text = fit_label(line, inner)
        tw = width(text)
        text_x = x + 1 + PAD + (max(inner - tw, 0) // 2 if _opts().align == "center" else 0)
        cur = text_x
        for c in text:
            cw = max(char_width(c), 1)
            canvas.set(cur, row, c, Cls.TEXT)
            # Wide glyphs (CJK, emoji) own a second column; mark it as a continuation so the
            # line builder doesn't emit a stray space
            for k in range(1, cw):
                canvas.set(cur + k, row, CONT, Cls.TEXT)
            cur += cw


def route_forward(canvas: Canvas, frm: Placed, to: Placed, edge: Edge, bus: int) -> None:
    tx = to.cx
    bx = tx if abs(frm.cx - tx) <= 1 else frm.cx
    by = frm.y + frm.h - 1
    head_row = to.y - 1

    canvas.junction(bx, by, D)
    canvas.seg_v(bx, by, bus)
    if bx == tx:
        canvas.seg_v(bx, bus, head_row)
    else:
        canvas.seg_h(bus, bx, tx)
        canvas.seg_v(tx, bus, head_row)

    if edge.head_to == Head.NONE:
        canvas.add_bits(tx, head_row, U)
    else:
        canvas.set(tx, head_row, head_glyph(edge.head_to, "▼"), Cls.EDGE)
    if edge.head_from != Head.NONE:
        canvas.set(bx, by, head_glyph(edge.head_from, "▲"), Cls.EDGE)

    if edge.label is not None:
        if UPSTREAM_LAYOUT:
            place_label(canvas, edge.label, head_row, tx + 1)
        else:
            # one blank column after the arrowhead; if a neighbour blocks that side, try the left
            lw = width(fit_label(edge.label, _label_cap()))
            place_label_clear(canvas, edge.label, [(head_row, tx + 2), (head_row, tx - 1 - lw)])


_TRIANGLE = {"▼": "▽", "▲": "△", "◄": "◁", "▶": "▷"}


def head_glyph(head: Head, arrow: str) -> str:
    if head == Head.CIRCLE:
        return "o"
    if head == Head.CROSS:
        return "×"
    if head == Head.DIAMOND_FILL:
        return "◆"
    if head == Head.DIAMOND_OPEN:
        return "◇"
    if head == Head.TRIANGLE:
        return _TRIANGLE.get(arrow, arrow)
    return arrow


def route_self(canvas: Canvas, p: Placed, edge: Edge) -> None:
    bottom = p.y + p.h - 1
    exit_x = p.cx + 1
    ret_x = p.x + p.w - 2
    if ret_x <= exit_x or bottom + 2 >= canvas.h:
        return
    if edge.line == LineKind.DOTTED:
        v, h, bl, br = "╎", "╌", "╰", "╯"
    elif edge.line == LineKind.THICK:
        v, h, bl, br = "┃", "━", "┗", "┛"
    else:
        v, h, bl, br = "│", "─", "╰", "╯"
    canvas.junction(exit_x, bottom, D)
    canvas.set(exit_x, bottom + 1, v, Cls.EDGE)
    canvas.set(exit_x, bottom + 2, bl, Cls.EDGE)
    for x in range(exit_x + 1, ret_x):
        canvas.set(x, bottom + 2, h, Cls.EDGE)
    canvas.set(ret_x, bottom + 2, br, Cls.EDGE)
    canvas.set(ret_x, bottom + 1, head_glyph(edge.head_to, "▲"), Cls.EDGE)
    if edge.label is not None:
        place_label(canvas, edge.label, bottom + 1, p.x + p.w + 1)


def route_back(canvas: Canvas, frm: Placed, to: Placed, edge: Edge, lane_x: int) -> None:
    sx = frm.x + frm.w - 1
    sy = frm.cy
    tx = to.x + to.w - 1
    tyc = to.cy

    canvas.junction(sx, sy, R)
    canvas.seg_h(sy, sx, lane_x)
    canvas.seg_v(lane_x, sy, tyc)
    canvas.seg_h(tyc, tx + 1, lane_x)

    if edge.head_to == Head.NONE:
        canvas.add_bits(tx + 1, tyc, R)
    else:
        canvas.set(tx + 1, tyc, head_glyph(edge.head_to, "◄"), Cls.EDGE)
    if edge.head_from != Head.NONE:
        canvas.set(sx, sy, head_glyph(edge.head_from, "◄"), Cls.EDGE)

    if edge.label is not None:
        if UPSTREAM_LAYOUT:
            place_label(
                canvas,
                edge.label,
                max(tyc - 1, 0),
                max(lane_x - (width(edge.label) + 1), 0),
            )
        else:
            # Right-align the (capped) label to the lane. Upstream measured the uncapped label
            # here, so a long label started inside the target box and was silently dropped.
            # Prefer the row above the arrow, then below, then one further out each way.
            lw = width(fit_label(edge.label, _label_cap()))
            start_x = max(lane_x - (lw + 1), 0)
            rows = [max(tyc - 1, 0), tyc + 1, max(tyc - 2, 0), tyc + 2]
            place_label_clear(canvas, edge.label, [(r, start_x) for r in rows])


def route_forward_lr(canvas: Canvas, frm: Placed, to: Placed, edge: Edge, bus: int) -> None:
    rx = frm.x + frm.w - 1
    ry = frm.cy
    ly = to.cy
    head_col = to.x - 1

    canvas.junction(rx, ry, R)
    canvas.seg_h(ry, rx, bus)
    if ry == ly:
        canvas.seg_h(ry, bus, head_col)
    else:
        canvas.seg_v(bus, ry, ly)
        canvas.seg_h(ly, bus, head_col)

    if edge.head_to == Head.NONE:
        canvas.add_bits(head_col, ly, R)
    else:
        canvas.set(head_col, ly, head_glyph(edge.head_to, "▶"), Cls.EDGE)
    if edge.head_from != Head.NONE:
        canvas.set(rx, ry, head_glyph(edge.head_from, "◄"), Cls.EDGE)

    if edge.label is not None:
        place_label(canvas, edge.label, max(ly - 1, 0), bus + 1)


def route_back_lr(canvas: Canvas, frm: Placed, to: Placed, edge: Edge, lane_y: int) -> None:
    sx = frm.cx
    sy = frm.y + frm.h - 1
    tx = to.cx
    ty = to.y + to.h - 1

    canvas.junction(sx, sy, D)
    canvas.seg_v(sx, sy, lane_y)
    canvas.seg_h(lane_y, sx, tx)
    canvas.seg_v(tx, lane_y, ty + 1)

    if edge.head_to == Head.NONE:
        canvas.add_bits(tx, ty + 1, D)
    else:
        canvas.set(tx, ty + 1, head_glyph(edge.head_to, "▲"), Cls.EDGE)
    if edge.head_from != Head.NONE:
        canvas.set(sx, sy, head_glyph(edge.head_from, "▲"), Cls.EDGE)

    if edge.label is not None:
        place_label(canvas, edge.label, max(lane_y - 1, 0), (sx + tx) // 2)


def _label_free(canvas: Canvas, text: str, row: int, start_x: int) -> bool:
    """True when `text` fits at (start_x, row) without touching any drawn cell."""
    if row < 0 or row >= canvas.h or start_x < 0:
        return False
    x = start_x
    for c in text:
        cw = max(char_width(c), 1)
        if x + cw > canvas.w:
            return False
        for k in range(cw):
            i = canvas.idx(x + k, row)
            if canvas.ch[i] != " " or canvas.mask[i] != 0 or canvas.occupied[i]:
                return False
        x += cw
    return True


def place_label_clear(canvas: Canvas, label: str, candidates: list[tuple[int, int]]) -> None:
    """Draw `label` at the first `(row, start_x)` where it fits untouched.

    Falls back to the upstream behaviour at the first candidate (draw until blocked) when none
    of them is free, so a label is never worse off than before.
    """
    text = fit_label(label, _label_cap())
    for row, start_x in candidates:
        if _label_free(canvas, text, row, start_x):
            place_label(canvas, label, row, start_x)
            return
    row, start_x = candidates[0]
    place_label(canvas, label, row, max(start_x, 0))


def place_label(canvas: Canvas, label: str, row: int, start_x: int) -> None:
    if row >= canvas.h:
        return
    text = fit_label(label, _label_cap())
    x = start_x
    for c in text:
        cw = max(char_width(c), 1)
        if x + cw > canvas.w:
            break
        blocked = False
        for k in range(cw):
            i = canvas.idx(x + k, row)
            if canvas.ch[i] != " " or canvas.mask[i] != 0 or canvas.occupied[i]:
                blocked = True
                break
        if blocked:
            break
        canvas.set(x, row, c, Cls.EDGE_LABEL)
        for k in range(1, cw):
            canvas.set(x + k, row, CONT, Cls.EDGE_LABEL)
        x += cw


def compute_ranks(graph: Graph) -> list[int]:
    n = len(graph.nodes)
    children: list[list[int]] = [[] for _ in range(n)]
    indeg = [0] * n
    for e in graph.edges:
        if e.from_ != e.to:
            if e.from_ < n:
                children[e.from_].append(e.to)
            if e.to < n:
                indeg[e.to] += 1

    color = [0] * n
    dag: list[list[int]] = [[] for _ in range(n)]
    order: list[int] = []

    roots = [i for i in range(n) if indeg[i] == 0]
    for start in roots + list(range(n)):
        if start < n and color[start] == 0:
            dfs_dag(start, children, color, dag, order)

    rank = [0] * n
    for u in reversed(order):
        if u >= len(dag):
            continue
        for v in dag[u]:
            if u >= len(rank):
                continue
            ru = rank[u]
            if v < len(rank):
                rank[v] = max(rank[v], ru + 1)
    return rank


def dfs_dag(
    start: int, children: list[list[int]], color: list[int], dag: list[list[int]], order: list[int]
) -> None:
    stack: list[list[int]] = [[start, 0]]
    if start < len(color):
        color[start] = 1
    while stack:
        frame = stack[-1]
        u = frame[0]
        kids = children[u] if u < len(children) else []
        if frame[1] < len(kids):
            v = kids[frame[1]]
            frame[1] += 1
            if v < len(color) and color[v] == 1:
                continue
            if u < len(dag):
                dag[u].append(v)
            if v < len(color) and color[v] == 0:
                color[v] = 1
                stack.append([v, 0])
        else:
            if u < len(color):
                color[u] = 2
            order.append(u)
            stack.pop()


# ---------------------------------------------------------------------------------------------
# sequenceDiagram
# ---------------------------------------------------------------------------------------------
SEQ_GAP = 5


class SeqHead(Enum):
    ARROW = "Arrow"
    CROSS = "Cross"


SEQ_OPS: tuple[tuple[str, bool, SeqHead], ...] = (
    ("-->>", True, SeqHead.ARROW),
    ("->>", False, SeqHead.ARROW),
    ("--x", True, SeqHead.CROSS),
    ("-x", False, SeqHead.CROSS),
    ("--)", True, SeqHead.ARROW),
    ("-)", False, SeqHead.ARROW),
    ("-->", True, SeqHead.ARROW),
    ("->", False, SeqHead.ARROW),
)


@dataclass
class NoteAnchor:
    """`enum NoteAnchor { Over(usize, usize), Left(usize), Right(usize) }`."""

    kind: str  # "Over" | "Left" | "Right"
    a: int
    b: int = 0

    @classmethod
    def over(cls, l: int, r: int) -> "NoteAnchor":
        return cls("Over", l, r)

    @classmethod
    def left(cls, i: int) -> "NoteAnchor":
        return cls("Left", i)

    @classmethod
    def right(cls, i: int) -> "NoteAnchor":
        return cls("Right", i)


@dataclass
class SeqMessage:
    from_: int
    to: int
    text: str | None
    dashed: bool
    head: SeqHead


@dataclass
class SeqNote:
    anchor: NoteAnchor
    text: str


@dataclass
class SeqDivider:
    text: str


@dataclass
class Sequence:
    labels: list[str] = field(default_factory=list)
    index: dict[str, int] = field(default_factory=dict)
    items: list = field(default_factory=list)

    def participant(self, id_: str, label: str | None) -> int | None:
        i = self.index.get(id_)
        if i is not None:
            if label is not None and i < len(self.labels):
                self.labels[i] = label
            return i
        if len(self.labels) >= MAX_NODES:
            return None
        self.index[id_] = len(self.labels)
        self.labels.append(id_ if label is None else label)
        return len(self.labels) - 1


def parse_sequence(src: str) -> Sequence | None:
    statements = _statements(src)
    if not statements:
        return None
    header = statements[0]
    fw = rstr.first_word(header)
    if fw is None or not rstr.eq_ignore_ascii_case(fw, "sequencediagram"):
        return None

    seq = Sequence()
    autonumber = False
    msg_count = 0
    blocks: list[bool] = []

    for st in statements[1:]:
        first = rstr.first_word(st) or ""
        lf = rstr.to_ascii_lowercase(first)
        if lf in ("participant", "actor"):
            rest = rstr.trim(st[len(first):])
            if rest == "":
                return None
            parts = rstr.split_once(rest, " as ")
            if parts is not None:
                id_, label = rstr.trim(parts[0]), clean_label(parts[1])
            else:
                id_, label = rest, None
            if seq.participant(id_, label) is None:
                return None
        elif lf == "autonumber":
            autonumber = True
        elif lf in (
            "activate", "deactivate", "create", "destroy", "title", "acctitle", "accdescr",
            "links", "link", "properties",
        ):
            pass
        elif lf == "note":
            rest = rstr.trim(st[len(first):])
            parsed = parse_note_anchor(rest, seq)
            if parsed is None:
                return None
            text_part, anchor = parsed
            if len(seq.items) >= MAX_EDGES:
                return None
            seq.items.append(SeqNote(anchor, text_part))
        elif lf in ("loop", "alt", "opt", "par", "critical", "break", "else", "and", "option"):
            if lf in ("else", "and", "option"):
                if not (blocks and blocks[-1] is True):
                    continue
            else:
                blocks.append(True)
            if len(seq.items) >= MAX_EDGES:
                return None
            seq.items.append(SeqDivider(decode_html_entities(st)))
        elif lf in ("rect", "box"):
            blocks.append(False)
        elif lf == "end":
            popped = blocks.pop() if blocks else None
            if popped is True:
                if len(seq.items) >= MAX_EDGES:
                    return None
                seq.items.append(SeqDivider("end"))
        else:
            parsed = parse_seq_message(st, seq)
            if parsed is None:
                return None
            from_, to, text, dashed, head = parsed
            if autonumber:
                msg_count += 1
                text = f"{msg_count}. {text}" if text is not None else f"{msg_count}."
            if len(seq.items) >= MAX_EDGES:
                return None
            seq.items.append(SeqMessage(from_, to, text, dashed, head))

    if not seq.labels:
        return None
    return seq


def parse_note_anchor(rest: str, seq: Sequence) -> tuple[str, NoteAnchor] | None:
    lower = rstr.to_ascii_lowercase(rest)
    if lower.startswith("over "):
        ids_and_text, kind = rest[len("over "):], 0
    elif lower.startswith("left of "):
        ids_and_text, kind = rest[len("left of "):], 1
    elif lower.startswith("right of "):
        ids_and_text, kind = rest[len("right of "):], 2
    else:
        return None
    parts = rstr.split_once(ids_and_text, ":")
    if parts is None:
        return None
    ids, text = parts
    text = decode_html_entities(rstr.trim(text))
    id_list = [p for p in (rstr.trim(x) for x in ids.split(",")) if p != ""]
    if not id_list:
        return None
    a = seq.participant(id_list[0], None)
    if a is None:
        return None
    if kind == 0:
        if len(id_list) > 1:
            b = seq.participant(id_list[1], None)
            if b is None:
                return None
        else:
            b = a
        anchor = NoteAnchor.over(min(a, b), max(a, b))
    elif kind == 1:
        anchor = NoteAnchor.left(a)
    else:
        anchor = NoteAnchor.right(a)
    return text, anchor


def parse_seq_message(st: str, seq: Sequence) -> tuple[int, int, str | None, bool, SeqHead] | None:
    found = None
    for pos in range(len(st)):
        for op, dashed, head in SEQ_OPS:
            if st.startswith(op, pos):
                found = (pos, op, dashed, head)
                break
        if found is not None:
            break
    if found is None:
        return None
    pos, op, dashed, head = found
    from_id = rstr.trim(st[:pos])
    if from_id == "":
        return None
    rest = rstr.trim_start_matches(rstr.trim_start(st[pos + len(op):]), "+-")
    parts = rstr.split_once(rest, ":")
    if parts is not None:
        to_id = rstr.trim(parts[0])
        text = non_empty(decode_html_entities(rstr.trim(parts[1])))
    else:
        to_id, text = rstr.trim(rest), None
    if to_id == "":
        return None
    from_ = seq.participant(from_id, None)
    if from_ is None:
        return None
    to = seq.participant(to_id, None)
    if to is None:
        return None
    return from_, to, text, dashed, head


def note_geometry(xs: list[int], anchor: NoteAnchor, text_w: int) -> tuple[int, int] | None:
    if anchor.kind == "Over":
        l, r = anchor.a, anchor.b
        if l >= len(xs) or r >= len(xs):
            return None
        xl = xs[l]
        xr = xs[r]
        center = (xl + xr) // 2
        w = max(xr - xl + 5, text_w + 2 * PAD + 2)
        return max(center - w // 2, 0), w
    if anchor.kind == "Left":
        i = anchor.a
        w = text_w + 2 * PAD + 2
        if i >= len(xs):
            return None
        return max(xs[i] - (2 + w - 1), 0), w
    i = anchor.a
    if i >= len(xs):
        return None
    return xs[i] + 2, text_w + 2 * PAD + 2


def _div_ceil(a: int, b: int) -> int:
    return -(-a // b)


#: Wrap widths tried in turn when a sequence diagram is wider than the width limit
#: (`UPSTREAM_LAYOUT` off): message, note and participant text wraps to that many columns.
SEQ_WRAP_STEPS = (40, 32, 24, 20, 16, 12, 10, 8)
SEQ_TEXT_MAX_LINES = 6


@dataclass
class SeqGeometry:
    """Everything `layout_sequence` draws from, computed for one wrap width."""

    labels: list[list[str]]
    box_w: list[int]
    box_h: int
    xs: list[int]
    texts: list[list[str] | None]
    rows: list[int]
    bottom_top: int
    canvas_w: int
    canvas_h: int


def _lines_w(lines: list[str] | None) -> int:
    return max((width(l) for l in lines), default=0) if lines is not None else 0


def _seq_geometry(seq: Sequence, wrap_w: int | None) -> SeqGeometry:
    """Measure the diagram. ``wrap_w=None`` is the upstream single-line layout; otherwise text
    wraps to ``wrap_w`` columns (a message crossing several lifelines may use all of its span)."""
    n = len(seq.labels)
    label_w = _opts().wrap_width
    if wrap_w is None:
        labels = [[fit_label(l, label_w)] for l in seq.labels]
    else:
        labels = [wrap_label(l, min(label_w, wrap_w), 3) for l in seq.labels]
    box_w = [max(_lines_w(l), 1) + 2 * PAD + 2 for l in labels]
    box_h = 2 + max((len(l) for l in labels), default=1)

    texts: list[list[str] | None] = []
    for item in seq.items:
        if isinstance(item, SeqMessage):
            text = item.text
        elif isinstance(item, SeqNote):
            text = item.text
        else:
            text = item.text
        if text is None:
            texts.append(None)
        elif wrap_w is None or isinstance(item, SeqDivider):
            texts.append([text])
        else:
            texts.append(wrap_label(text, wrap_w, SEQ_TEXT_MAX_LINES))

    gaps: list[int] = []
    for i in range(max(n - 1, 0)):
        if i < len(box_w) and i + 1 < len(box_w):
            gaps.append(max(SEQ_GAP, _div_ceil(box_w[i], 2) + _div_ceil(box_w[i + 1], 2) + 1))

    # (left, right, columns needed, item index when its text may re-wrap to the span, else -1)
    reqs: list[tuple[int, int, int, int]] = []
    for k, item in enumerate(seq.items):
        if isinstance(item, SeqMessage):
            tw = _lines_w(texts[k])
            if item.from_ != item.to:
                l, r = min(item.from_, item.to), max(item.from_, item.to)
                rewrap = k if (wrap_w is not None and texts[k] is not None and r - l > 1) else -1
                reqs.append((l, r, max(tw + 2, 4), rewrap))
            elif item.from_ + 1 < n:
                reqs.append((item.from_, item.from_ + 1, 5 + tw + 2, -1))
        elif isinstance(item, SeqNote):
            tw = _lines_w(texts[k])
            anc = item.anchor
            if anc.kind == "Over" and anc.a < anc.b:
                reqs.append((anc.a, anc.b, max(tw - 1, 0), -1))
            elif anc.kind == "Over":
                i = anc.a
                half = _div_ceil(tw + 4, 2) + 2
                if i > 0:
                    reqs.append((i - 1, i, half, -1))
                if i + 1 < n:
                    reqs.append((i, i + 1, half, -1))
            elif anc.kind == "Left" and anc.a > 0:
                reqs.append((anc.a - 1, anc.a, tw + 7, -1))
            elif anc.kind == "Right" and anc.a + 1 < n:
                reqs.append((anc.a, anc.a + 1, tw + 7, -1))
    reqs.sort(key=lambda lrn: lrn[1] - lrn[0])
    for l, r, need, k in reqs:
        if l > r or r > len(gaps):
            continue
        cur = 0
        for g in gaps[l:r]:
            cur += g
        if k >= 0 and wrap_w is not None and cur - 2 > wrap_w:
            # the lifelines this message crosses already leave more room than the wrap width
            lines = wrap_label(seq.items[k].text, cur - 2, SEQ_TEXT_MAX_LINES)
            texts[k] = lines
            need = max(_lines_w(lines) + 2, 4)
        if cur < need and r >= 1 and r - 1 < len(gaps):
            gaps[r - 1] += need - cur

    xs = [0] * n
    if n > 0 and box_w:
        xs[0] = box_w[0] // 2
    for i in range(1, n):
        prev = i - 1
        if prev >= len(xs) or prev >= len(gaps):
            continue
        xs[i] = xs[prev] + gaps[prev]

    if xs and box_w:
        canvas_w = xs[-1] + _div_ceil(box_w[-1], 2) + 1
    else:
        canvas_w = 1
    for k, item in enumerate(seq.items):
        if isinstance(item, SeqMessage) and item.from_ == item.to:
            if item.from_ < len(xs):
                canvas_w = max(canvas_w, xs[item.from_] + 5 + _lines_w(texts[k]) + 1)
        elif isinstance(item, SeqNote):
            geo = note_geometry(xs, item.anchor, _lines_w(texts[k]))
            if geo is not None:
                canvas_w = max(canvas_w, geo[0] + geo[1] + 1)
        elif isinstance(item, SeqDivider):
            canvas_w = max(canvas_w, width(item.text) + 4)

    rows: list[int] = []
    y = box_h + 1
    for k, item in enumerate(seq.items):
        rows.append(y)
        if isinstance(item, SeqMessage):
            n_lines = len(texts[k]) if texts[k] is not None else 0
            if item.from_ == item.to:
                y += 3 + max(n_lines, 1)
            else:
                y += 2 + n_lines
        elif isinstance(item, SeqNote):
            y += 3 + len(texts[k] or [])
        else:
            y += 2
    bottom_top = y
    canvas_h = bottom_top + box_h
    return SeqGeometry(labels, box_w, box_h, xs, texts, rows, bottom_top, canvas_w, canvas_h)


def layout_sequence(seq: Sequence, styles: MermaidStyles, max_width: int | None) -> MermaidArt:
    steps: list[int | None] = [None]
    if max_width is not None and not UPSTREAM_LAYOUT:
        steps.extend(SEQ_WRAP_STEPS)
    geo: SeqGeometry | None = None
    for wrap_w in steps:
        candidate = _seq_geometry(seq, wrap_w)
        if max_width is None or candidate.canvas_w <= max_width:
            geo = candidate
            break
    if geo is None:
        raise OversizeError(Oversize.WIDTH)
    if geo.canvas_w * geo.canvas_h > MAX_CANVAS_CELLS:
        raise OversizeError(Oversize.CELLS)

    n = len(seq.labels)
    xs, box_w, box_h, labels, texts, rows, bottom_top = (
        geo.xs, geo.box_w, geo.box_h, geo.labels, geo.texts, geo.rows, geo.bottom_top,
    )
    canvas_w = geo.canvas_w
    canvas = Canvas(canvas_w, geo.canvas_h)
    for i in range(n):
        if i >= len(xs) or i >= len(box_w) or i >= len(labels):
            continue
        xi = xs[i]
        wi = box_w[i]
        # a shorter label sits vertically centred in a box sized for the tallest one
        lines = [""] * ((box_h - 2 - len(labels[i])) // 2) + labels[i]
        for by in (0, bottom_top):
            p = Placed(max(xi - wi // 2, 0), by, wi, box_h, xi, by + 1, 0)
            draw_box(canvas, p, lines, Shape.RECT)
    for k, (item, r) in enumerate(zip(seq.items, rows)):
        if isinstance(item, SeqNote):
            lines = texts[k] or [""]
            geo_n = note_geometry(xs, item.anchor, _lines_w(lines))
            if geo_n is None:
                continue
            x, w = geo_n
            h = 2 + len(lines)
            p = Placed(x, r, w, h, x + w // 2, r + 1, 0)
            draw_box(canvas, p, lines, Shape.RECT)
    for x in xs:
        canvas.junction(x, box_h - 1, D)
        canvas.seg_v(x, box_h, bottom_top - 1)
        canvas.junction(x, bottom_top, U)

    for k, (item, r) in enumerate(zip(seq.items, rows)):
        if isinstance(item, SeqMessage):
            line_ch = "╌" if item.dashed else "─"
            lines = texts[k]
            if item.from_ == item.to:
                if item.from_ >= len(xs):
                    continue
                x = xs[item.from_]
                n_lines = max(len(lines), 1) if lines is not None else 1
                canvas.junction(x, r, R)
                canvas.set(x + 1, r, line_ch, Cls.EDGE)
                canvas.set(x + 2, r, line_ch, Cls.EDGE)
                canvas.set(x + 3, r, "╮", Cls.EDGE)
                for j in range(n_lines):
                    canvas.set(x + 3, r + 1 + j, "│", Cls.EDGE)
                end = r + 1 + n_lines
                canvas.set(x + 1, end, "×" if item.head == SeqHead.CROSS else "◄", Cls.EDGE)
                canvas.set(x + 2, end, line_ch, Cls.EDGE)
                canvas.set(x + 3, end, "╯", Cls.EDGE)
                if lines is not None:
                    for j, t in enumerate(lines):
                        draw_seq_text(canvas, t, x + 5, r + 1 + j, Cls.TEXT)
            else:
                if item.from_ >= len(xs) or item.to >= len(xs):
                    continue
                x0, x1 = xs[item.from_], xs[item.to]
                rightward = x1 > x0
                n_lines = len(lines) if lines is not None else 0
                arrow_row = r + n_lines
                lo, hi = min(x0, x1), max(x0, x1)
                canvas.junction(x0, arrow_row, R if rightward else L)
                for x in range(lo + 1, hi):
                    canvas.set(x, arrow_row, line_ch, Cls.EDGE)
                if item.head == SeqHead.CROSS:
                    head_ch = "×"
                elif rightward:
                    head_ch = "▶"
                else:
                    head_ch = "◄"
                head_x = x1 - 1 if rightward else x1 + 1
                canvas.set(head_x, arrow_row, head_ch, Cls.EDGE)
                if lines is not None:
                    span = hi - lo - 1
                    for j, line in enumerate(lines):
                        t = fit_label(line, max(span, 1))
                        tx = lo + 1 + max(span - width(t), 0) // 2
                        draw_seq_text(canvas, t, tx, r + j, Cls.TEXT)
        elif isinstance(item, SeqNote):
            pass
        else:
            for x in range(canvas_w):
                canvas.set(x, r, "─", Cls.EDGE)
            t = fit_label(item.text, max(canvas_w - 4, 0))
            draw_seq_text(canvas, f" {t} ", 2, r, Cls.EDGE_LABEL)

    canvas.finalize_mask()
    styled_lines, plain_lines = canvas.to_lines(styles)
    return MermaidArt(styled_lines, plain_lines)


def draw_seq_text(canvas: Canvas, text: str, x: int, y: int, cls: Cls) -> None:
    cur = x
    for c in text:
        cw = max(char_width(c), 1)
        for k in range(cw):
            if 0 <= cur + k < canvas.w and 0 <= y < canvas.h:
                canvas.mask[canvas.idx(cur + k, y)] = 0
            canvas.set(cur + k, y, c if k == 0 else CONT, cls)
        cur += cw


# ---------------------------------------------------------------------------------------------
# Fallback (unsupported / over-wide diagrams)
# ---------------------------------------------------------------------------------------------
TOO_WIDE_HINT = "This diagram is too wide to display here — open the image to view it in full."


def fallback(src: str, styles: MermaidStyles, max_width: int | None, too_wide: bool) -> MermaidArt:
    header = first_word(src)
    title = f" mermaid: {header} "
    limit = max(max(max_width - 4, 0), 8) if max_width is not None else None
    body: list[str] = []
    skipping = True
    for l in rstr.lines(src):
        l = rstr.trim_end(l)
        if skipping and l == "":
            continue
        skipping = False
        body.extend(chunk_line(l, limit))
    content_w = max([width(l) for l in body] + [width(title)])
    inner = content_w + 2

    styled: list[Line] = []
    plain: list[str] = []

    fill = max(inner - width(title), 0)
    top = "╭" + title + "─" * fill + "╮"
    styled.append(
        Line(
            [
                Span("╭", styles.border),
                Span(title, styles.title),
                Span("─" * fill + "╮", styles.border),
            ]
        )
    )
    plain.append(top)

    for line in body:
        pad = max(content_w - width(line), 0)
        styled.append(
            Line(
                [
                    Span("│ ", styles.border),
                    Span(line, styles.node_text),
                    Span(" " * pad + " │", styles.border),
                ]
            )
        )
        plain.append(f"│ {line}{' ' * pad} │")

    bottom = "╰" + "─" * inner + "╯"
    styled.append(Line([Span(bottom, styles.border)]))
    plain.append(bottom)

    if too_wide:
        hint_style = styles.border.add_modifiers(Modifier.ITALIC)
        for chunk in wrap_words(TOO_WIDE_HINT, max_width):
            styled.append(Line([Span(chunk, hint_style)]))
            plain.append(chunk)

    return MermaidArt(styled, plain)


def chunk_line(line: str, limit: int | None) -> list[str]:
    if limit is None:
        return [line]
    if width(line) <= limit:
        return [line]
    out: list[str] = []
    cur = ""
    cur_w = 0
    for c in line:
        cw = max(char_width(c), 1)
        if cur_w + cw > limit and cur != "":
            out.append(cur)
            cur = ""
            cur_w = 0
        cur += c
        cur_w += cw
    if cur != "":
        out.append(cur)
    return out


def wrap_words(text: str, limit: int | None) -> list[str]:
    if limit is None:
        return [text]
    lines: list[str] = []
    cur = ""
    for word in (w for w in text.split(" ") if w != ""):
        if cur == "":
            cur += word
        elif width(cur) + 1 + width(word) <= limit:
            cur += " "
            cur += word
        else:
            lines.append(cur)
            cur = word
    if cur != "":
        lines.append(cur)
    out: list[str] = []
    for l in lines:
        out.extend(chunk_line(l, limit))
    return out


def first_word(src: str) -> str:
    w = rstr.first_word(src)
    return "diagram" if w is None else w
