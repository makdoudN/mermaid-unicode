"""CLI tests (Typer). Skipped when typer is not installed."""
import os
import unittest

try:
    import typer  # noqa: F401
    from typer.testing import CliRunner
except ImportError:  # pragma: no cover
    raise unittest.SkipTest("typer not installed")

from mermaid_unicode import __version__
from mermaid_unicode.cli import app, convert_markdown, main, strip_fence

runner = CliRunner()


def test_version():
    r = runner.invoke(app, ["--version"])
    assert r.exit_code == 0 and __version__ in r.output


def test_root_help_lists_commands():
    r = runner.invoke(app, ["--help"])
    assert r.exit_code == 0
    for cmd in ("render", "markdown", "inspect", "examples"):
        assert cmd in r.output


def test_render_inline_text_plain():
    r = runner.invoke(app, ["render", "-t", "graph LR; A --> B", "-c", "never"])
    assert r.exit_code == 0, r.output
    assert "│ A ├───▶│ B │" in r.output
    assert "\x1b[" not in r.output


def test_render_color_always_emits_ansi():
    r = runner.invoke(app, ["render", "-t", "graph LR; A --> B", "-c", "always"])
    assert r.exit_code == 0 and "\x1b[" in r.output


def test_render_stdin_and_fence():
    src = "```mermaid\nsequenceDiagram\n  A->>B: hi\n```\n"
    r = runner.invoke(app, ["render", "-c", "never"], input=src)
    assert r.exit_code == 0, r.output
    assert "│ A │" in r.output and "hi" in r.output


def test_render_width_forces_fallback():
    long = "flowchart LR\n A[aaaaaaaaaaaaaaaaaaaa] --> B[bbbbbbbbbbbbbbbbbbbb] --> C[cccccccccccccccccccc]"
    r = runner.invoke(app, ["render", "-t", long, "-w", "40", "-c", "never"])
    assert r.exit_code == 0 and "mermaid: flowchart" in r.output and "too wide" in r.output
    r2 = runner.invoke(app, ["render", "-t", long, "-w", "0", "-c", "never"])
    assert r2.exit_code == 0 and "▶" in r2.output


def test_render_blank_source_exits_1():
    r = runner.invoke(app, ["render", "-t", "   "])
    assert r.exit_code == 1


def test_render_missing_file_is_usage_error():
    r = runner.invoke(app, ["render", "/nonexistent/diagram.mmd"])
    assert r.exit_code == 2


def test_render_output_file(tmp_path=None):
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        out = os.path.join(d, "art.txt")
        r = runner.invoke(app, ["render", "-t", "graph TD; A --> B", "-o", out])
        assert r.exit_code == 0, r.output
        text = open(out, encoding="utf-8").read()
        assert "▼" in text and "\x1b[" not in text


def test_examples_list_and_render():
    r = runner.invoke(app, ["examples"])
    assert r.exit_code == 0 and "flowchart-request" in r.output and "er-orders" in r.output
    r = runner.invoke(app, ["examples", "state-lifecycle", "-c", "never"])
    assert r.exit_code == 0 and "stateDiagram-v2" in r.output and "Idle" in r.output and "●" in r.output
    r = runner.invoke(app, ["examples", "sequence-basic", "--source"])
    assert r.exit_code == 0 and r.output.startswith("sequenceDiagram")
    r = runner.invoke(app, ["examples", "nope"])
    assert r.exit_code == 2


def test_inspect_reports_kind_and_fit():
    r = runner.invoke(app, ["inspect", "-t", "graph TD\n A --> B\n B --> C", "-w", "20"])
    assert r.exit_code == 0, r.output
    assert "flowchart (down)" in r.output and "nodes" in r.output and "fits" in r.output
    r = runner.invoke(app, ["inspect", "-t", "gantt\n title x"])
    assert r.exit_code == 0 and "unsupported" in r.output


def test_markdown_conversion():
    doc = "# T\n\n```mermaid\ngraph LR\n  A --> B\n```\n\n- item\n  ```mermaid\n  sequenceDiagram\n    A->>B: hi\n  ```\n\n```python\nx = 1\n```\n"
    new, count = convert_markdown(doc, None, raw=False)
    assert count == 2
    assert "```mermaid" not in new and "```python\nx = 1\n```" in new
    assert "```text\n┌───┐" in new
    assert "  ```text\n  ┌───┐" in new  # indentation preserved inside the list item
    raw, _ = convert_markdown(doc, None, raw=True)
    assert "```text" not in raw and "┌───┐" in raw


def test_markdown_command_in_place():
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "doc.md")
        with open(p, "w", encoding="utf-8") as f:
            f.write("```mermaid\ngraph TD\n A --> B\n```\n")
        r = runner.invoke(app, ["markdown", p, "-i"])
        assert r.exit_code == 0, r.output
        assert "```text" in open(p, encoding="utf-8").read()


def test_strip_fence_variants():
    assert strip_fence("```mermaid\ngraph TD\n A\n```") == "graph TD\n A"
    assert strip_fence("~~~ mermaid\ngraph TD\n A\n~~~\n") == "graph TD\n A"
    assert strip_fence("graph TD\n A") == "graph TD\n A"


def test_main_defaults_to_render():
    # `main()` inserts the implicit `render` command; Typer exits via SystemExit.
    try:
        main(["-t", "graph LR; A --> B", "-c", "never"])
    except SystemExit as e:
        assert e.code in (0, None)


def test_render_inline_text_with_label_line_breaks():
    r = runner.invoke(app, ["render", "-t", 'flowchart TD\n  A["top\\nbottom"]', "-c", "never"])
    assert r.exit_code == 0, r.output
    rows = [row for row in r.output.split("\n") if row.strip()]
    assert len(rows) == 4, r.output  # border, top, bottom, border
    assert "top" in rows[1] and "bottom" in rows[2] and "\\n" not in r.output
