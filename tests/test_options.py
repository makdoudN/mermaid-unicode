"""`RenderOptions` (wrap width, line cap, alignment) through the API and the CLI."""
import unittest

from mermaid_unicode import MermaidStyles, RenderOptions, render, render_plain
from mermaid_unicode import mermaid as m

STEP = 'flowchart TD\n  A["Join the mapping\\nfeature → risk factor · one long detail line"] --> B[Done]'


def _rows(src, width=None, **kw):
    art = render_plain(src, width, RenderOptions(**kw) if kw else None)
    assert art is not None
    return art.split("\n")


def test_default_options_are_the_upstream_layout():
    plain = render(STEP, MermaidStyles(), 80)
    explicit = render(STEP, MermaidStyles(), 80, RenderOptions())
    assert plain is not None and explicit is not None
    assert plain.plain_lines == explicit.plain_lines
    assert RenderOptions() == RenderOptions(wrap_width=24, max_lines=4, align="center")


def test_wrap_width_keeps_a_long_detail_line_whole():
    narrow = "\n".join(_rows(STEP))
    wide = "\n".join(_rows(STEP, wrap_width=48))
    assert "feature → risk factor · one long detail line" not in narrow
    assert "│ feature → risk factor · one long detail line │" in wide, wide


def test_left_alignment_starts_every_line_at_the_same_column():
    rows = _rows(STEP, wrap_width=48, align="left")
    box = [r for r in rows if r.startswith("│ ") and "Join" in r or "feature" in r]
    assert box[0].startswith("│ Join the mapping ") and box[1].startswith("│ feature → risk"), rows
    centered = _rows(STEP, wrap_width=48)
    assert any(r.startswith("│    ") and "Join the mapping" in r for r in centered), centered


def test_max_lines_caps_each_paragraph():
    src = "flowchart TD\n  A[" + " ".join(["word"] * 30) + "]"
    assert sum("word" in r for r in _rows(src)) == 4
    assert sum("word" in r for r in _rows(src, max_lines=2)) == 2
    rows = _rows(src, max_lines=8, wrap_width=24)
    assert sum("word" in r for r in rows) == 6 and "…" not in "\n".join(rows)  # 5 words per line


def test_sequence_participants_follow_the_wrap_width():
    src = "sequenceDiagram\n  participant A as A participant with a rather long name\n  A->>A: ping\n"
    assert "…" in "\n".join(_rows(src))
    assert "A participant with a rather long name" in "\n".join(_rows(src, wrap_width=48))


def test_invalid_options_are_rejected():
    tc = unittest.TestCase()
    with tc.assertRaises(ValueError):
        RenderOptions(align="right")
    with tc.assertRaises(ValueError):
        RenderOptions(wrap_width=0)


def test_options_do_not_leak_between_calls():
    render(STEP, MermaidStyles(), None, RenderOptions(wrap_width=60, align="left"))
    assert m._opts() == RenderOptions()
    assert "feature → risk factor · one long detail line" not in "\n".join(_rows(STEP))


def test_cli_wrap_and_align():
    try:
        from typer.testing import CliRunner
    except ImportError:  # pragma: no cover
        raise unittest.SkipTest("typer not installed")
    from mermaid_unicode.cli import app

    runner = CliRunner()
    r = runner.invoke(app, ["render", "-t", STEP, "-c", "never", "-W", "48", "--align", "left"])
    assert r.exit_code == 0, r.output
    assert "│ feature → risk factor · one long detail line " in r.output, r.output
    r = runner.invoke(app, ["examples", "flowchart-pipeline", "-c", "never", "-W", "44", "--align", "left"])
    assert r.exit_code == 0 and "│ Raw events " in r.output, r.output
    r = runner.invoke(app, ["render", "-t", STEP, "--align", "middle"])
    assert r.exit_code == 2
