"""Generate the README screenshots in ``docs/img/``.

Each image is a terminal-window mock-up drawn glyph by glyph on a fixed cell grid, so the
box-drawing art is pixel-aligned whatever the viewer's fonts. Needs Pillow and a monospace
font with box-drawing glyphs (macOS Menlo by default; pass ``--font`` for another one).

    python3 tools/readme_assets.py              # writes docs/img/*.png
    python3 tools/readme_assets.py --only hero  # one image
"""
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mermaid_unicode import Color, MermaidStyles, Modifier, RenderOptions, Style, char_width, render  # noqa: E402
from mermaid_unicode.ansi import DEFAULT_STYLES  # noqa: E402
from mermaid_unicode.cli import _trim_rows, convert_markdown  # noqa: E402
from mermaid_unicode.examples import EXAMPLES  # noqa: E402

OUT_DIR = ROOT / "docs" / "img"
SCALE = 2  # render at 2x for crisp display on HiDPI screens; the README shows images at half size

# Catppuccin Mocha, the terminal theme the screenshots imitate.
THEME = {
    "bg": "#1e1e2e",
    "bar": "#181825",
    "frame": "#313244",
    "fg": "#cdd6f4",
    "muted": "#a6adc8",
    "prompt": "#a6e3a1",
    "title": "#bac2de",
    "dots": ("#f38ba8", "#f9e2af", "#a6e3a1"),
    # ANSI names used by mermaid_unicode.Color -> hex
    "ansi": {
        "Black": "#45475a", "Red": "#f38ba8", "Green": "#a6e3a1", "Yellow": "#f9e2af",
        "Blue": "#89b4fa", "Magenta": "#f5c2e7", "Cyan": "#94e2d5", "Gray": "#bac2de",
        "DarkGray": "#7f849c", "LightRed": "#f38ba8", "LightGreen": "#a6e3a1",
        "LightYellow": "#f9e2af", "LightBlue": "#89b4fa", "LightMagenta": "#f5c2e7",
        "LightCyan": "#94e2d5", "White": "#ffffff",
    },
    # source-code highlighting
    "kw": "#cba6f7", "str": "#a6e3a1", "arrow": "#7f849c", "label": "#f9e2af", "comment": "#6c7086",
}

FONT_SIZE = 13 * SCALE
DEFAULT_FONT = "/System/Library/Fonts/Menlo.ttc"


@dataclass
class Run:
    text: str
    color: str = THEME["fg"]
    bold: bool = False
    italic: bool = False


@dataclass
class Pane:
    title: str
    lines: list[list[Run]] = field(default_factory=list)

    @property
    def cols(self) -> int:
        return max((sum(_width(r.text) for r in line) for line in self.lines), default=0)

    @property
    def rows(self) -> int:
        return len(self.lines)


def _width(s: str) -> int:
    return sum(char_width(c) for c in s)


# --- fonts ------------------------------------------------------------------------------------
class Fonts:
    def __init__(self, path: str, size: int):
        def face(index: int):
            try:
                return ImageFont.truetype(path, size, index=index)
            except OSError:
                return ImageFont.truetype(path, size)

        self.regular = face(0)
        self.bold = face(1)
        self.italic = face(2)
        self.bold_italic = face(3)
        self.cell_w = self.regular.getlength("M")
        ascent, descent = self.regular.getmetrics()
        self.ascent = ascent
        self.cell_h = ascent + descent

    def pick(self, bold: bool, italic: bool):
        if bold and italic:
            return self.bold_italic
        if bold:
            return self.bold
        if italic:
            return self.italic
        return self.regular


# --- converting rendered art and source text into runs ------------------------------------------
def art_runs(src: str, styles: MermaidStyles = DEFAULT_STYLES, width: int | None = None,
             options: RenderOptions | None = None) -> list[list[Run]]:
    art = render(src, styles, width, options)
    assert art is not None, "blank source"
    _, styled = _trim_rows(art.plain_lines, art.styled_lines)
    lines: list[list[Run]] = []
    for line in styled:
        runs = []
        for span in line.spans:
            st: Style = span.style
            color = THEME["fg"]
            if st.fg is not None:
                if st.fg.kind == "Rgb":
                    color = "#%02x%02x%02x" % st.fg.value
                elif st.fg.kind in THEME["ansi"]:
                    color = THEME["ansi"][st.fg.kind]
            if st.add_modifier & Modifier.DIM:
                color = THEME["ansi"]["DarkGray"]
            runs.append(Run(span.content, color, bool(st.add_modifier & Modifier.BOLD), bool(st.add_modifier & Modifier.ITALIC)))
        lines.append(runs)
    return lines


_KEYWORDS = {
    "graph", "flowchart", "sequenceDiagram", "stateDiagram", "stateDiagram-v2", "classDiagram", "erDiagram",
    "subgraph", "end", "loop", "alt", "else", "opt", "par", "and", "critical", "break", "Note", "over",
    "participant", "actor", "as", "autonumber", "class", "direction",
}
_DIRECTIONS = {"TD", "TB", "LR", "RL", "BT"}
_DIRECTION_AFTER = {"graph", "flowchart", "direction"}
_TOKEN = re.compile(
    r'(?P<comment>%%.*$)'
    r'|(?P<str>"[^"\n]*"?)'
    r'|(?P<label>\|[^|\n]*\|)'
    r'|(?P<arrow>-->>|-->|<-->|---|-\.->|==>|--o|--x|-x|->>|->|<\|--|\*--|o--|\.\.>|\.\.|\|\|--|\|\|\.\.|}o--|}o\.\.|}\||o\{|\|\{|<<|>>|:)'
    r'|(?P<word>[A-Za-z][\w-]*)'
)


def source_runs(src: str) -> list[list[Run]]:
    lines: list[list[Run]] = []
    for raw in src.rstrip("\n").split("\n"):
        runs: list[Run] = []
        pos = 0
        prev_word = ""
        for m in _TOKEN.finditer(raw):
            if m.start() > pos:
                runs.append(Run(raw[pos:m.start()]))
            kind = m.lastgroup
            text = m.group(0)
            if kind == "word":
                is_kw = text in _KEYWORDS or (text in _DIRECTIONS and prev_word in _DIRECTION_AFTER)
                runs.append(Run(text, THEME["kw"], bold=True) if is_kw else Run(text))
                prev_word = text
            elif kind == "comment":
                runs.append(Run(text, THEME["comment"], italic=True))
            else:
                runs.append(Run(text, THEME[kind]))
            pos = m.end()
        if pos < len(raw):
            runs.append(Run(raw[pos:]))
        lines.append(runs)
    return lines


def prompt(cmd: str) -> list[Run]:
    return [Run("$ ", THEME["prompt"], bold=True), Run(cmd, THEME["fg"])]


def shell_pane(title: str, cmd: str, output: list[list[Run]]) -> Pane:
    return Pane(title, [prompt(cmd), []] + output)


def markdown_runs(doc: str) -> list[list[Run]]:
    """Very small Markdown highlighter for the before/after screenshot."""
    lines = []
    in_fence = False
    for raw in doc.rstrip("\n").split("\n"):
        if raw.lstrip().startswith("```"):
            in_fence = not in_fence or raw.strip() != "```"
            in_fence = raw.strip() != "```" if not in_fence else in_fence
            lines.append([Run(raw, THEME["comment"])])
            continue
        if raw.startswith("#"):
            lines.append([Run(raw, THEME["kw"], bold=True)])
        elif in_fence:
            lines.append([Run(raw, THEME["muted"])])
        else:
            lines.append([Run(raw)])
    return lines


# --- drawing ----------------------------------------------------------------------------------
def draw_pane(canvas: Image.Image, fonts: Fonts, x: int, y: int, pane: Pane, min_cols: int = 0, min_rows: int = 0) -> tuple[int, int]:
    pad_x = int(fonts.cell_w * 1.5)
    pad_y = int(fonts.cell_h * 0.6)
    bar_h = int(fonts.cell_h * 1.3)
    radius = 10 * SCALE
    cols = max(pane.cols, min_cols)
    rows = max(pane.rows, min_rows)
    w = int(cols * fonts.cell_w) + 2 * pad_x
    h = bar_h + int(rows * fonts.cell_h) + 2 * pad_y

    d = ImageDraw.Draw(canvas)
    d.rounded_rectangle((x, y, x + w, y + h), radius=radius, fill=THEME["bg"], outline=THEME["frame"], width=SCALE)
    # title bar: rounded on top only
    d.rounded_rectangle((x, y, x + w, y + bar_h + radius), radius=radius, fill=THEME["bar"], outline=THEME["frame"], width=SCALE)
    d.rectangle((x + SCALE, y + bar_h, x + w - SCALE, y + bar_h + radius), fill=THEME["bg"])
    d.line((x, y + bar_h, x + w, y + bar_h), fill=THEME["frame"], width=SCALE)
    r = 6 * SCALE
    cy = y + bar_h // 2
    for i, c in enumerate(THEME["dots"]):
        cx = x + pad_x + i * (r * 2 + 6 * SCALE)
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=c)
    tw = fonts.regular.getlength(pane.title)
    d.text((x + (w - tw) / 2, cy), pane.title, font=fonts.regular, fill=THEME["title"], anchor="lm")

    ox = x + pad_x
    oy = y + bar_h + pad_y
    for row, runs in enumerate(pane.lines):
        col = 0
        for run in runs:
            font = fonts.pick(run.bold, run.italic)
            for ch in run.text:
                cw = char_width(ch)
                if cw == 0:
                    continue
                d.text((ox + col * fonts.cell_w, oy + row * fonts.cell_h), ch, font=font, fill=run.color, anchor="la")
                col += cw
    return w, h


def compose(panes: list[Pane], out: Path, gap_cols: float = 2.0, fonts: Fonts | None = None, equal_height: bool = False) -> None:
    fonts = fonts or Fonts(DEFAULT_FONT, FONT_SIZE)
    margin = 4 * SCALE
    gap = int(gap_cols * fonts.cell_w)
    rows = max(p.rows for p in panes) if equal_height else 0
    # measure
    sizes = []
    for p in panes:
        pad_x = int(fonts.cell_w * 1.5)
        pad_y = int(fonts.cell_h * 0.6)
        bar_h = int(fonts.cell_h * 1.3)
        w = int(p.cols * fonts.cell_w) + 2 * pad_x
        h = bar_h + int(max(p.rows, rows) * fonts.cell_h) + 2 * pad_y
        sizes.append((w, h))
    total_w = sum(w for w, _ in sizes) + gap * (len(panes) - 1) + 2 * margin
    total_h = max(h for _, h in sizes) + 2 * margin
    canvas = Image.new("RGBA", (total_w, total_h), (0, 0, 0, 0))
    x = margin
    for p, (w, h) in zip(panes, sizes):
        draw_pane(canvas, fonts, x, margin, p, min_rows=rows)
        x += w + gap
    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out, optimize=True)
    print(f"wrote {out.relative_to(ROOT)}  {total_w // SCALE}x{total_h // SCALE}@{SCALE}x")


# --- the images -------------------------------------------------------------------------------
SHOWCASE = MermaidStyles(
    border=Style(fg=Color.rgb(137, 180, 250)),
    node_text=Style(fg=Color.rgb(205, 214, 244)),
    edge=Style(fg=Color.rgb(148, 226, 213)),
    edge_label=Style(fg=Color.rgb(249, 226, 175), add_modifier=Modifier.ITALIC),
    title=Style(fg=Color.rgb(250, 179, 135), add_modifier=Modifier.BOLD),
)

MARKDOWN_DOC = """# Release checklist

Ship only when the pipeline is green:

```mermaid
flowchart LR
    A[Lint] --> B[Test] --> C{Green?}
    C -->|yes| D[Release]
    C -->|no| E[Fix it]
```

Tag the release once `Release` is reached.
"""


def ex(name: str) -> str:
    return EXAMPLES[name][1]


def build(only: str | None, font_path: str) -> None:
    fonts = Fonts(font_path, FONT_SIZE)
    images: dict[str, callable] = {}

    def image(name):
        def deco(fn):
            images[name] = fn
            return fn
        return deco

    @image("hero")
    def _hero():
        src = ex("flowchart-request")
        compose([
            Pane("api.mmd", source_runs(src)),
            shell_pane("zsh", "mermaid-unicode api.mmd", art_runs(src)),
        ], OUT_DIR / "hero.png", fonts=fonts)

    @image("sequence")
    def _sequence():
        src = ex("sequence-full")
        compose([
            Pane("checkout.mmd", source_runs(src)),
            shell_pane("zsh", "mermaid-unicode checkout.mmd", art_runs(src)),
        ], OUT_DIR / "sequence.png", fonts=fonts)

    @image("state")
    def _state():
        src = ex("state-lifecycle")
        compose([
            Pane("loader.mmd", source_runs(src)),
            shell_pane("zsh", "mermaid-unicode loader.mmd", art_runs(src)),
        ], OUT_DIR / "state.png", fonts=fonts)

    @image("class")
    def _class():
        src = ex("class-animals")
        compose([
            Pane("animals.mmd", source_runs(src)),
            shell_pane("zsh", "mermaid-unicode animals.mmd", art_runs(src)),
        ], OUT_DIR / "class.png", fonts=fonts)

    @image("er")
    def _er():
        src = ex("er-orders")
        compose([
            Pane("orders.mmd", source_runs(src)),
            shell_pane("zsh", "mermaid-unicode orders.mmd", art_runs(src)),
        ], OUT_DIR / "er.png", fonts=fonts)

    @image("subgraphs")
    def _subgraphs():
        src = ex("flowchart-subgraphs")
        compose([
            Pane("platform.mmd", source_runs(src)),
            shell_pane("zsh", "mermaid-unicode platform.mmd", art_runs(src)),
        ], OUT_DIR / "subgraphs.png", fonts=fonts)

    @image("pipeline")
    def _pipeline():
        src = ex("flowchart-pipeline")
        compose([
            shell_pane("zsh", "mermaid-unicode attention.mmd -W 44 --align left",
                       art_runs(src, options=RenderOptions(wrap_width=44, align="left"))),
        ], OUT_DIR / "pipeline.png", fonts=fonts)

    @image("multiline")
    def _multiline():
        src = ex("flowchart-multiline")
        compose([
            Pane("fulfilment.mmd", source_runs(src)),
            shell_pane("zsh", "mermaid-unicode fulfilment.mmd", art_runs(src)),
        ], OUT_DIR / "multiline.png", fonts=fonts)

    @image("markdown")
    def _markdown():
        converted, _ = convert_markdown(MARKDOWN_DOC, None, False)
        compose([
            Pane("RELEASE.md", markdown_runs(MARKDOWN_DOC)),
            shell_pane("zsh", "mermaid-unicode markdown RELEASE.md", markdown_runs(converted)),
        ], OUT_DIR / "markdown.png", fonts=fonts)

    @image("width")
    def _width():
        src = ex("sequence-full")
        compose([
            shell_pane("zsh", "mermaid-unicode checkout.mmd -w 44", art_runs(src, width=44)),
        ], OUT_DIR / "width.png", fonts=fonts)

    @image("styled")
    def _styled():
        src = ex("flowchart-styles")
        compose([
            shell_pane("python", "python themed.py", art_runs(src, styles=SHOWCASE)),
        ], OUT_DIR / "styled.png", fonts=fonts)

    for name, fn in images.items():
        if only is None or name == only:
            fn()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", help="generate a single image by name")
    ap.add_argument("--font", default=DEFAULT_FONT, help="monospace font file with box-drawing glyphs")
    ns = ap.parse_args()
    build(ns.only, ns.font)
