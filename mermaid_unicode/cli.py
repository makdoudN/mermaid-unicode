"""Typer-based command line for mermaid-unicode.

``mermaid-unicode [SOURCE]`` renders one diagram (``render`` is the default command). Other
commands: ``markdown`` (replace ```` ```mermaid ```` fences in a document), ``inspect`` (which
parser accepted the source, sizes, why it fell back) and ``examples`` (built-in diagrams).
"""
from __future__ import annotations

import os
import re
import shutil
import sys
from enum import Enum
from pathlib import Path
from typing import Optional

import typer

from . import __version__
from .ansi import DEFAULT_STYLES, line_to_ansi
from .examples import EXAMPLES
from .mermaid import MermaidStyles, RenderOptions, render as _render
from .unicode_width import str_width

app = typer.Typer(
    name="mermaid-unicode",
    help=(
        "Render **Mermaid** diagrams as Unicode box-drawing art in the terminal.\n\n"
        "Supports flowchart/graph (TD, LR, RL, BT, subgraphs), stateDiagram, classDiagram, "
        "erDiagram and sequenceDiagram. Other diagram types are shown as their source in a framed box.\n\n"
        "`mermaid-unicode FILE` and `cat FILE | mermaid-unicode` both run the **render** command."
    ),
    rich_markup_mode="markdown",
    context_settings={"help_option_names": ["-h", "--help"]},
    no_args_is_help=False,
)

COMMANDS = ("render", "markdown", "inspect", "examples")


class ColorMode(str, Enum):
    auto = "auto"
    always = "always"
    never = "never"


class Align(str, Enum):
    center = "center"
    left = "left"


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"mermaid-unicode {__version__}")
        raise typer.Exit()


@app.callback()
def _root(
    version: bool = typer.Option(
        False, "--version", "-V", callback=_version_callback, is_eager=True, help="Show the version and exit."
    ),
) -> None:
    pass


# --- helpers ---------------------------------------------------------------------------------
_FENCE_LINE = re.compile(r"^[ \t]*(`{3,}|~{3,})")


def strip_fence(src: str) -> str:
    """Drop a surrounding Markdown code fence (``` or ~~~, any info string) if present."""
    lines = src.split("\n")
    while lines and lines[0].strip() == "":
        lines.pop(0)
    if lines and _FENCE_LINE.match(lines[0]):
        lines = lines[1:]
        while lines and lines[-1].strip() == "":
            lines.pop()
        if lines and _FENCE_LINE.match(lines[-1]):
            lines.pop()
    return "\n".join(lines)


def _read_source(source: Optional[Path], text: Optional[str], ctx: typer.Context) -> str:
    if text is not None:
        return strip_fence(text.replace("\\n", "\n")) if "\n" not in text and "\\n" in text else strip_fence(text)
    if source is None or str(source) == "-":
        if sys.stdin.isatty():
            typer.echo(ctx.get_help())
            typer.echo("\nNothing to render: pass a FILE, use --text, or pipe Mermaid source on stdin.", err=True)
            raise typer.Exit(code=2)
        return strip_fence(sys.stdin.read())
    if not source.exists():
        raise typer.BadParameter(f"file not found: {source}", param_hint="SOURCE")
    return strip_fence(source.read_text(encoding="utf-8"))


def _resolve_width(width: Optional[int], for_tty: bool = True) -> Optional[int]:
    """None → terminal width when stdout is a TTY (else unlimited); 0 or negative → unlimited."""
    if width is None:
        if for_tty and sys.stdout.isatty():
            return shutil.get_terminal_size().columns
        return None
    return None if width <= 0 else width


def _use_color(mode: ColorMode, writing_to_file: bool) -> bool:
    if mode == ColorMode.always:
        return True
    if mode == ColorMode.never or writing_to_file:
        return False
    return sys.stdout.isatty() and not os.environ.get("NO_COLOR")


def _trim_rows(plain: list[str], styled: list) -> tuple[list[str], list]:
    """Drop fully blank leading/trailing canvas rows (layout artifacts of the upstream renderer)."""
    first = 0
    last = len(plain)
    while first < last and plain[first] == "":
        first += 1
    while last > first and plain[last - 1] == "":
        last -= 1
    return plain[first:last], styled[first:last]


def _render_text(src: str, width: Optional[int], color: bool, options: Optional[RenderOptions] = None) -> Optional[str]:
    art = _render(src, DEFAULT_STYLES if color else MermaidStyles(), width, options)
    if art is None:
        return None
    plain, styled = _trim_rows(art.plain_lines, art.styled_lines)
    if color:
        return "\n".join(line_to_ansi(line) for line in styled)
    return "\n".join(plain)


def _emit(text: str) -> None:
    """Write art to stdout verbatim; `typer.echo` would strip ANSI codes when piped."""
    sys.stdout.write(text + "\n")
    sys.stdout.flush()


def _is_fallback(plain_first_line: str) -> bool:
    return plain_first_line.startswith("╭ mermaid: ")


WIDTH_HELP = "Maximum width in columns. Default: the terminal width on a TTY, unlimited when piped. 0 = unlimited."
COLOR_HELP = "Colorize with ANSI escapes: auto (TTY only, honours NO_COLOR), always or never."
WRAP_HELP = "Wrap node, note and participant labels at N columns (default 24). Try 48 for step charts with a title and a detail line."
ALIGN_HELP = "Text alignment inside boxes: center (default) or left."


def _options(wrap: Optional[int], align: Align) -> RenderOptions:
    wrap_width = RenderOptions().wrap_width if wrap is None or wrap <= 0 else wrap
    return RenderOptions(wrap_width=wrap_width, align=align.value)


# --- render -----------------------------------------------------------------------------------
@app.command()
def render(
    ctx: typer.Context,
    source: Optional[Path] = typer.Argument(
        None,
        metavar="[SOURCE]",
        help="Mermaid file (raw or inside a ```mermaid fence), or '-' for stdin. Defaults to stdin when piped.",
        show_default=False,
    ),
    text: Optional[str] = typer.Option(None, "--text", "-t", help="Inline Mermaid source instead of a file (a literal \\n is expanded when the text has no real newline).", show_default=False),
    width: Optional[int] = typer.Option(None, "--width", "-w", help=WIDTH_HELP, show_default=False),
    color: ColorMode = typer.Option(ColorMode.auto, "--color", "-c", help=COLOR_HELP, case_sensitive=False),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Write to this file instead of stdout.", show_default=False),
    wrap: Optional[int] = typer.Option(None, "--wrap", "-W", help=WRAP_HELP, show_default=False),
    align: Align = typer.Option(Align.center, "--align", help=ALIGN_HELP, case_sensitive=False),
    ansi: bool = typer.Option(False, "--ansi", hidden=True, help="Alias for --color always."),
) -> None:
    """Render one diagram as box art (the default command).

    Blank leading/trailing canvas rows are trimmed. Examples:

    ```
    mermaid-unicode diagram.mmd
    cat diagram.mmd | mermaid-unicode -w 80
    mermaid-unicode -t 'graph LR; A --> B --> C'
    pbpaste | mermaid-unicode -c never | pbcopy
    ```
    """
    src = _read_source(source, text, ctx)
    if ansi:
        color = ColorMode.always
    out = _render_text(src, _resolve_width(width), _use_color(color, output is not None), _options(wrap, align))
    if out is None:
        typer.echo("Blank Mermaid source: nothing to render.", err=True)
        raise typer.Exit(code=1)
    if output is not None:
        output.write_text(out + "\n", encoding="utf-8")
        typer.echo(f"Wrote {output}", err=True)
    else:
        _emit(out)


# --- markdown ---------------------------------------------------------------------------------
_FENCE_BLOCK = re.compile(
    r"^(?P<indent>[ \t]*)(?P<fence>`{3,}|~{3,})[ \t]*(?P<info>[^\n]*)\n"
    r"(?P<body>(?:.*\n)*?)"
    r"(?P=indent)(?P=fence)[`~]*[ \t]*$",
    re.M,
)


def convert_markdown(
    doc: str, width: Optional[int], raw: bool, options: Optional[RenderOptions] = None
) -> tuple[str, int]:
    """Replace every ```mermaid fence in `doc` with rendered art; returns (new_doc, count)."""
    count = 0

    def repl(m: re.Match) -> str:
        nonlocal count
        info = m.group("info").strip().split()
        if not info or info[0].lower() != "mermaid":
            return m.group(0)
        indent = m.group("indent")
        body_lines = m.group("body").split("\n")
        if body_lines and body_lines[-1] == "":
            body_lines.pop()
        body = "\n".join(l[len(indent):] if l.startswith(indent) else l for l in body_lines)
        art = _render(body, MermaidStyles(), width, options)
        if art is None:
            return m.group(0)
        count += 1
        plain, _ = _trim_rows(art.plain_lines, art.styled_lines)
        art_lines = [indent + l if l else l for l in plain]
        if raw:
            return "\n".join(art_lines)
        return "\n".join([indent + "```text", *art_lines, indent + "```"])

    return _FENCE_BLOCK.sub(repl, doc), count


@app.command()
def markdown(
    file: Path = typer.Argument(..., help="Markdown document containing ```mermaid fences.", exists=True, dir_okay=False),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Write the converted document here (default: stdout).", show_default=False),
    in_place: bool = typer.Option(False, "--in-place", "-i", help="Overwrite FILE with the converted document."),
    width: int = typer.Option(0, "--width", "-w", help="Maximum diagram width in columns (0 = unlimited)."),
    raw: bool = typer.Option(False, "--raw", help="Insert the art as plain text instead of wrapping it in a ```text fence."),
    wrap: Optional[int] = typer.Option(None, "--wrap", "-W", help=WRAP_HELP, show_default=False),
    align: Align = typer.Option(Align.center, "--align", help=ALIGN_HELP, case_sensitive=False),
) -> None:
    """Replace every ```mermaid fence in a Markdown file with rendered box art.

    Handy for READMEs, tickets and commit messages viewed where Mermaid is not rendered.
    """
    if in_place and output is not None:
        raise typer.BadParameter("use either --in-place or --output, not both", param_hint="--output")
    doc = file.read_text(encoding="utf-8")
    new_doc, count = convert_markdown(doc, None if width <= 0 else width, raw, _options(wrap, align))
    if in_place:
        file.write_text(new_doc, encoding="utf-8")
        typer.echo(f"Converted {count} diagram(s) in {file}", err=True)
    elif output is not None:
        output.write_text(new_doc, encoding="utf-8")
        typer.echo(f"Converted {count} diagram(s) → {output}", err=True)
    else:
        sys.stdout.write(new_doc)
        if not new_doc.endswith("\n"):
            sys.stdout.write("\n")


# --- inspect ----------------------------------------------------------------------------------
@app.command()
def inspect(
    ctx: typer.Context,
    source: Optional[Path] = typer.Argument(None, metavar="[SOURCE]", help="Mermaid file or '-' for stdin.", show_default=False),
    text: Optional[str] = typer.Option(None, "--text", "-t", help="Inline Mermaid source instead of a file.", show_default=False),
    width: Optional[int] = typer.Option(None, "--width", "-w", help="Width to test the diagram against. " + WIDTH_HELP, show_default=False),
) -> None:
    """Explain how a diagram is parsed: kind, element counts, canvas size and whether it fits.

    Use it when the output is the framed source box instead of a diagram: it tells you which
    parser rejected the source or that the canvas is wider than the width limit.
    """
    from . import mermaid as m

    src = _read_source(source, text, ctx)
    kind = "unsupported (falls back to framed source)"
    details: list[tuple[str, str]] = []
    g = m.parse_graph(src)
    if g is not None:
        kind = f"flowchart ({g.dir.value.lower()})"
        details = [("nodes", str(len(g.nodes))), ("edges", str(len(g.edges))), ("subgraphs", str(len(g.groups)))]
    elif (g := m.parse_state(src)) is not None:
        kind = f"stateDiagram ({g.dir.value.lower()})"
        details = [("states", str(len(g.nodes))), ("transitions", str(len(g.edges)))]
    elif (c := m.parse_class(src)) is not None:
        kind = f"classDiagram ({c[0].dir.value.lower()})"
        details = [("classes", str(len(c[0].nodes))), ("relations", str(len(c[0].edges)))]
    elif (e := m.parse_er(src)) is not None:
        kind = "erDiagram"
        details = [("entities", str(len(e[0].nodes))), ("relationships", str(len(e[0].edges)))]
    elif (s := m.parse_sequence(src)) is not None:
        kind = "sequenceDiagram"
        details = [("participants", str(len(s.labels))), ("items", str(len(s.items)))]
    art = _render(src, MermaidStyles(), None)
    rows: list[tuple[str, str]] = [("kind", kind), *details]
    if art is None:
        rows.append(("render", "blank source, nothing to render"))
    else:
        w = max((str_width(l) for l in art.plain_lines), default=0)
        rows.append(("canvas", f"{w} × {len(art.plain_lines)} (columns × rows)"))
        limit = _resolve_width(width)
        if limit is not None:
            if w <= limit:
                verdict = "fits"
            else:
                limited = _render(src, MermaidStyles(), limit)
                if limited is not None and not _is_fallback(limited.plain_lines[0]):
                    lw = max((str_width(l) for l in limited.plain_lines), default=0)
                    verdict = f"fits by wrapping text ({lw} × {len(limited.plain_lines)})"
                else:
                    verdict = "too wide → framed source with hint"
            rows.append(("width limit", f"{limit}: {verdict}"))
        if _is_fallback(art.plain_lines[0]):
            rows.append(("note", "rendered as framed source (unsupported type or unparseable statement)"))
    label_w = max(len(k) for k, _ in rows)
    for k, v in rows:
        typer.echo(f"{k.ljust(label_w)}  {v}")


# --- examples ---------------------------------------------------------------------------------
@app.command()
def examples(
    name: Optional[str] = typer.Argument(None, help="Example to show; omit to list them all.", show_default=False),
    source_only: bool = typer.Option(False, "--source", "-s", help="Print only the Mermaid source (pipe it back into render)."),
    width: Optional[int] = typer.Option(None, "--width", "-w", help=WIDTH_HELP, show_default=False),
    color: ColorMode = typer.Option(ColorMode.auto, "--color", "-c", help=COLOR_HELP, case_sensitive=False),
    wrap: Optional[int] = typer.Option(None, "--wrap", "-W", help=WRAP_HELP, show_default=False),
    align: Align = typer.Option(Align.center, "--align", help=ALIGN_HELP, case_sensitive=False),
) -> None:
    """List the built-in example diagrams, or render one by name (source first, then the art)."""
    if name is None:
        name_w = max(len(n) for n in EXAMPLES)
        for n, (desc, _) in EXAMPLES.items():
            typer.echo(f"{n.ljust(name_w)}  {desc}")
        typer.echo("\nRun `mermaid-unicode examples NAME` to render one, or add --source to get the Mermaid text.")
        return
    if name not in EXAMPLES:
        close = [n for n in EXAMPLES if name.lower() in n]
        hint = f" Did you mean: {', '.join(close)}?" if close else ""
        raise typer.BadParameter(f"unknown example '{name}'.{hint} Run `mermaid-unicode examples` to list them.", param_hint="NAME")
    _, src = EXAMPLES[name]
    if source_only:
        sys.stdout.write(src)
        return
    typer.echo(src.rstrip("\n"))
    typer.echo()
    _emit(_render_text(src, _resolve_width(width), _use_color(color, False), _options(wrap, align)) or "")


# --- entry point -----------------------------------------------------------------------------
_ROOT_FLAGS = ("--help", "-h", "--version", "-V", "--install-completion", "--show-completion")


def main(argv: Optional[list[str]] = None) -> None:
    """Console-script entry point: `mermaid-unicode [SOURCE]` implies the `render` command."""
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or (args[0] not in COMMANDS and not any(args[0] == f or args[0].startswith(f + "=") for f in _ROOT_FLAGS)):
        args.insert(0, "render")
    app(args=args, prog_name="mermaid-unicode")


if __name__ == "__main__":
    main()
